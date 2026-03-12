#!/usr/bin/env python3
"""
Automated Video Pipeline Scheduler

Runs every 30 minutes to:
1. Fetch viral tech/news videos
2. Create short clips
3. Upload to YouTube

Can be run as a systemd service or cron job.
"""

import os
import sys
import time
import logging
import schedule
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.skills.news_extractor.skill import NewsExtractorSkill
from src.skills.youtube_upload.skill import YouTubeUploadSkill
from src.integrations.youtube import YouTubeProvider
from src.integrations.facebook import FacebookProvider
from src.integrations.instagram import InstagramProvider
from src.utils.cdn_uploader import get_uploader
from src.agent.context import Context


# Configuration
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "automation.log"
STATE_FILE = Path(".automation_state.json")

# Pipeline settings
FETCH_CATEGORIES = ["news"]  # Only news videos
VIDEOS_PER_FETCH = 1  # Fetch 1 video per run
CLIPS_PER_VIDEO = 1  # Create 1 clip per video
CLIP_DURATION = 20  # seconds
MAX_UPLOADS_PER_RUN = 1  # Upload 1 video every 30 minutes
PRIVACY_STATUS = "unlisted"  # Start with unlisted, can change later


class AutomationPipeline:
    """Automated video pipeline."""
    
    def __init__(self):
        self.context = Context()
        self.news_skill = NewsExtractorSkill()
        self.youtube_provider = YouTubeProvider()
        self.youtube_skill = YouTubeUploadSkill(self.youtube_provider)
        self.facebook_provider = FacebookProvider()
        self.instagram_provider = InstagramProvider()
        
        # Setup logging
        LOG_DIR.mkdir(exist_ok=True)
        self.setup_logging()
        
        self.logger = logging.getLogger(__name__)
        self.run_count = 0
        self.uploaded_today = 0
        self.last_category = "tech"
    
    def setup_logging(self):
        """Configure logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(LOG_FILE),
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    def check_authentication(self) -> bool:
        """Check if YouTube, Facebook, and Instagram are authenticated."""
        # Check YouTube
        auth_result = self.youtube_skill.execute("check_auth", {}, self.context)
        
        if not auth_result.success:
            self.logger.error("YouTube not authenticated!")
            self.logger.error("Please set up OAuth credentials and authenticate via /admin")
            return False
        
        self.logger.info("✅ YouTube authentication verified")
        
        # Check Facebook (optional - warn but don't fail)
        if not self.facebook_provider.is_authenticated():
            self.logger.warning("⚠️  Facebook not authenticated - videos will only upload to YouTube")
            self.logger.warning("Set FACEBOOK_PAGE_ACCESS_TOKEN and FACEBOOK_PAGE_ID to enable Facebook uploads")
        else:
            self.logger.info("✅ Facebook authentication verified")
        
        # Check Instagram (optional - warn but don't fail)
        if not self.instagram_provider.is_authenticated():
            self.logger.warning("⚠️  Instagram not authenticated - videos will only upload to YouTube")
            self.logger.warning("Set FACEBOOK_PAGE_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ACCOUNT_ID to enable Instagram uploads")
        else:
            self.logger.info("✅ Instagram authentication verified")
        
        return True
    
    def check_daily_quota(self) -> bool:
        """Check if we've exceeded daily upload quota."""
        # YouTube default quota allows ~6 uploads/day
        # We'll be conservative and limit to 15 clips per day (5 runs)
        if self.uploaded_today >= 15:
            self.logger.warning(f"Daily quota reached: {self.uploaded_today} uploads today")
            return False
        return True
    
    def fetch_videos(self) -> List[Dict[str, Any]]:
        """Fetch viral videos."""
        # Alternate between categories
        category = "news" if self.last_category == "tech" else "tech"
        self.last_category = category
        
        action = "fetch_tech" if category == "tech" else "fetch_news"
        
        self.logger.info(f"📥 Fetching {category} videos...")
        
        result = self.news_skill.execute(action, {
            "max_results": VIDEOS_PER_FETCH
        }, self.context)
        
        if not result.success:
            self.logger.error(f"Failed to fetch videos: {result.message}")
            return []
        
        videos = result.data.get("videos", [])
        self.logger.info(f"✅ Fetched {len(videos)} {category} videos")
        
        return videos
    
    def create_clips(self, video_url: str, video_title: str) -> List[Path]:
        """Create clips from a video URL using the NewsExtractor clipper."""
        self.logger.info(f"🎬 Creating clips from: {video_title[:50]}...")
        
        # We'll use a simplified approach - call the clipper via subprocess
        # In a production system, you'd refactor clipper.py into a library
        
        try:
            import subprocess
            
            clips_dir = Path("src/skills/NewsExtractor/shorts_from_youtube")
            clips_dir.mkdir(parents=True, exist_ok=True)
            
            # Count existing clips
            existing_clips = list(clips_dir.glob("*.mp4"))
            before_count = len(existing_clips)
            
            # Create a simple Python script that uses the clipper functions
            clipper_path = Path("src/skills/NewsExtractor/clipper.py")
            
            # Import the necessary functions
            sys.path.insert(0, str(clipper_path.parent))
            
            # Try to import and use clipper functions
            try:
                from clipper import create_clips_from_video_optimized, get_video_info
                
                # Get video info first
                info = get_video_info(video_url)
                if not info:
                    self.logger.error("Could not get video info")
                    return []
                
                self.logger.info(f"Video duration: {info['duration']}s")
                
                # Create clips
                success = create_clips_from_video_optimized(
                    video_url,
                    num_clips=CLIPS_PER_VIDEO,
                    clip_duration=CLIP_DURATION
                )
                
                if not success:
                    self.logger.error("Failed to create clips")
                    return []
                
                # Get newly created clips
                new_clips = list(clips_dir.glob("*.mp4"))
                after_count = len(new_clips)
                
                created_clips = sorted(new_clips)[before_count:after_count]
                
                self.logger.info(f"✅ Created {len(created_clips)} clips")
                return created_clips
                
            except ImportError as e:
                self.logger.error(f"Could not import clipper: {e}")
                return []
        
        except Exception as e:
            self.logger.error(f"Error creating clips: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return []
    
    def upload_clips(self, clips: List[Path], source_title: str) -> int:
        """Upload clips to YouTube."""
        uploaded_count = 0
        
        for i, clip_path in enumerate(clips[:MAX_UPLOADS_PER_RUN], 1):
            if not self.check_daily_quota():
                self.logger.warning("Daily quota reached, stopping uploads")
                break
            
            try:
                # Generate title
                timestamp = datetime.now().strftime("%Y-%m-%d")
                title = f"Viral {self.last_category.title()} #{self.run_count}-{i} | {timestamp}"
                
                description = (
                    f"🔥 Auto-generated viral short from tech/news content\n\n"
                    f"Source: {source_title[:100]}\n"
                    f"Created: {timestamp}\n"
                    f"Category: {self.last_category}\n\n"
                    f"#shorts #viral #{self.last_category} #trending #automated"
                )
                
                self.logger.info(f"📤 Uploading clip {i}/{len(clips)}: {clip_path.name}")
                
                result = self.youtube_skill.execute("upload", {
                    "video_path": str(clip_path),
                    "title": title[:100],
                    "description": description[:5000],
                    "tags": ["shorts", "viral", self.last_category, "trending", "automated"],
                    "privacy": PRIVACY_STATUS,
                    "category_id": "28" if self.last_category == "tech" else "25",  # Tech or News
                }, self.context)
                
                if result.success:
                    video_url = result.data.get("url", "")
                    self.logger.info(f"✅ Uploaded to YouTube: {video_url}")
                    uploaded_count += 1
                    self.uploaded_today += 1
                    
                    # Upload to Facebook and Instagram
                    self.upload_to_social_media(clip_path, title, description, video_url)
                else:
                    self.logger.error(f"❌ Upload failed: {result.message}")
                
                # Sleep between uploads to avoid rate limiting
                time.sleep(5)
            
            except Exception as e:
                self.logger.error(f"Error uploading {clip_path}: {e}")
        
        return uploaded_count
    
    def upload_to_social_media(
        self,
        video_path: Path,
        title: str,
        description: str,
        youtube_url: str
    ):
        """
        Upload video to Facebook and Instagram after YouTube upload.
        
        Args:
            video_path: Path to video file
            title: Video title
            description: Video description
            youtube_url: YouTube URL (for sharing)
        """
        # Upload to Facebook
        if self.facebook_provider.is_authenticated():
            try:
                self.logger.info(f"📱 Uploading to Facebook: {video_path.name}")
                
                # Use title and description with YouTube link
                fb_description = f"{title}\n\n{description}\n\n🎥 Watch on YouTube: {youtube_url}"
                
                fb_result = self.facebook_provider.post_video(
                    video_path=str(video_path),
                    title=title[:80],  # Facebook title limit
                    description=fb_description[:5000],
                    tags=[self.last_category, "viral", "shorts", "trending"],
                    published=True
                )
                
                if fb_result.get("success"):
                    fb_url = fb_result.get("url", "")
                    self.logger.info(f"✅ Uploaded to Facebook: {fb_url}")
                else:
                    error = fb_result.get("error", "Unknown error")
                    self.logger.error(f"❌ Facebook upload failed: {error}")
                
            except Exception as e:
                self.logger.error(f"Error uploading to Facebook: {e}")
        
        # Upload to Instagram
        if self.instagram_provider.is_authenticated():
            try:
                self.logger.info(f"📷 Uploading to Instagram: {video_path.name}")
                
                # Upload to CDN to get public URL
                try:
                    uploader = get_uploader()
                    public_url = uploader.upload(str(video_path))
                    
                    # Create Instagram caption
                    ig_caption = f"{title}\n\n{description[:2000]}\n\n🎥 {youtube_url}"
                    
                    # Post as reel
                    ig_result = self.instagram_provider.post_reel(
                        video_url=public_url,
                        caption=ig_caption,
                        share_to_feed=True
                    )
                    
                    if ig_result.get("success"):
                        ig_url = ig_result.get("url", "")
                        self.logger.info(f"✅ Uploaded to Instagram: {ig_url}")
                    else:
                        error = ig_result.get("error", "Unknown error")
                        self.logger.error(f"❌ Instagram upload failed: {error}")
                
                except Exception as upload_error:
                    self.logger.error(f"Failed to upload to CDN/Instagram: {upload_error}")
                    self.logger.info(f"   To enable Instagram uploads:")
                    self.logger.info(f"   1. Set CDN_BACKEND=local (for testing with local server)")
                    self.logger.info(f"   2. Or set up S3/Cloudflare R2 for production")
                    self.logger.info(f"   3. Ensure FILE_SERVER_PORT is accessible (default: 8080)")
                
            except Exception as e:
                self.logger.error(f"Error with Instagram upload: {e}")
    
    def cleanup_old_clips(self, keep_latest: int = 10):
        """Clean up old clips to save disk space."""
        try:
            clips_dir = Path("src/skills/NewsExtractor/shorts_from_youtube")
            
            if not clips_dir.exists():
                return
            
            clips = sorted(clips_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
            
            if len(clips) <= keep_latest:
                return
            
            old_clips = clips[:-keep_latest]
            
            for clip in old_clips:
                try:
                    clip.unlink()
                    self.logger.info(f"🗑️  Cleaned up: {clip.name}")
                except Exception as e:
                    self.logger.warning(f"Could not delete {clip.name}: {e}")
        
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def run_pipeline(self):
        """Run the complete pipeline."""
        self.run_count += 1
        
        self.logger.info("=" * 70)
        self.logger.info(f"🚀 Starting pipeline run #{self.run_count}")
        self.logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 70)
        
        try:
            # Check authentication
            if not self.check_authentication():
                return
            
            # Check quota
            if not self.check_daily_quota():
                self.logger.info("Skipping run due to quota limits")
                return
            
            # Step 1: Fetch videos
            videos = self.fetch_videos()
            
            if not videos:
                self.logger.warning("No videos fetched, skipping run")
                return
            
            # Step 2: Create clips from first video
            # (Creating clips from all videos would be too much)
            video = videos[0]
            video_url = video.get("url")
            video_title = video.get("title", "Unknown")
            
            clips = self.create_clips(video_url, video_title)
            
            if not clips:
                self.logger.warning("No clips created, skipping upload")
                return
            
            # Step 3: Upload clips
            uploaded = self.upload_clips(clips, video_title)
            
            self.logger.info(f"✅ Pipeline complete: {uploaded} clips uploaded")
            
            # Step 4: Cleanup old clips
            self.cleanup_old_clips(keep_latest=20)
            
        except Exception as e:
            self.logger.error(f"Pipeline error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        
        finally:
            self.logger.info("=" * 70)
            self.logger.info("")
    
    def reset_daily_counter(self):
        """Reset daily upload counter (called at midnight)."""
        self.logger.info("🔄 Resetting daily upload counter")
        self.uploaded_today = 0


def main():
    """Main function - runs the scheduler."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automated Video Pipeline')
    parser.add_argument('--once', action='store_true', help='Run once and exit (for cron)')
    args = parser.parse_args()
    
    print("=" * 70)
    print("AUTOMATED VIDEO PIPELINE SCHEDULER")
    print("Fetch → Create Clips → Upload to YouTube")
    if not args.once:
        print("Runs every 30 minutes")
    else:
        print("Running once (cron mode)")
    print("=" * 70)
    print()
    
    # Create pipeline
    pipeline = AutomationPipeline()
    
    # Check authentication before starting
    if not pipeline.check_authentication():
        print("\n❌ Authentication failed. Please set up YouTube OAuth first.")
        print("See YOUTUBE_UPLOAD_SKILL.md for setup instructions.")
        sys.exit(1)
    
    print("✅ Authentication verified")
    print()
    print("📋 Configuration:")
    print(f"   • Fetch categories: {', '.join(FETCH_CATEGORIES)}")
    print(f"   • Videos per fetch: {VIDEOS_PER_FETCH}")
    print(f"   • Clips per video: {CLIPS_PER_VIDEO}")
    print(f"   • Clip duration: {CLIP_DURATION}s")
    print(f"   • Max uploads per run: {MAX_UPLOADS_PER_RUN}")
    print(f"   • Privacy: {PRIVACY_STATUS}")
    print(f"   • Log file: {LOG_FILE}")
    print()
    
    # Run once mode (for cron)
    if args.once:
        print("🚀 Running pipeline once...")
        pipeline.run_pipeline()
        print("✅ Pipeline complete!")
        return
    
    # Schedule tasks
    schedule.every(30).minutes.do(pipeline.run_pipeline)
    schedule.every().day.at("00:00").do(pipeline.reset_daily_counter)
    
    print("⏰ Scheduler started!")
    print("   • Pipeline runs every 30 minutes")
    print("   • Daily counter resets at midnight")
    print()
    print("Press Ctrl+C to stop")
    print()
    
    # Run immediately on start
    print("🚀 Running initial pipeline...")
    pipeline.run_pipeline()
    
    # Main loop
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Scheduler stopped by user")
        pipeline.logger.info("Scheduler stopped by user")
    
    except Exception as e:
        print(f"\n\n❌ Scheduler error: {e}")
        pipeline.logger.error(f"Scheduler error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
