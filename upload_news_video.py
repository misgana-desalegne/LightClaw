#!/usr/bin/env python3
"""
Upload the latest generated news compilation video to YouTube.

This script:
1. Finds the latest news_vertical_*.mp4 file
2. Uploads it to YouTube with appropriate metadata
3. Confirms the upload was successful

Prerequisites:
- YouTube authentication completed (GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET set)
- Token stored in token_store (authenticate via /admin interface)
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.skills.youtube_upload.skill import YouTubeUploadSkill
from src.integrations.youtube import YouTubeProvider
from src.agent.context import Context


def get_latest_news_video():
    """Find the latest news_vertical_*.mp4 video."""
    output_dir = Path(__file__).parent / "src" / "skills" / "NewsExtractor" / "output_videos"
    
    if not output_dir.exists():
        print(f"❌ Output directory not found: {output_dir}")
        return None
    
    # Find all news_vertical_*.mp4 files
    videos = sorted(output_dir.glob("news_vertical_*.mp4"), reverse=True)
    
    if not videos:
        print(f"❌ No news_vertical_*.mp4 files found in {output_dir}")
        return None
    
    # Return the most recent one
    latest = videos[0]
    return latest


def main():
    print("=" * 70)
    print("UPLOAD NEWS COMPILATION TO YOUTUBE")
    print("=" * 70)
    
    # Initialize YouTube provider and skill
    provider = YouTubeProvider()
    skill = YouTubeUploadSkill(provider)
    context = Context()
    
    # Check authentication
    print("\n🔐 Checking YouTube authentication...")
    auth_result = skill.execute("check_auth", {}, context)
    print(auth_result.message)
    
    if not provider.is_authenticated():
        print("\n⚠️  To authenticate:")
        print("1. Ensure GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are set")
        print("2. Start the LightClaw server (python src/main.py)")
        print("3. Navigate to http://localhost:5000/admin")
        print("4. Click 'Connect Google Account' and grant YouTube permissions")
        print("5. Run this script again")
        return 1
    
    # Find latest video
    print("\n📂 Finding latest news compilation video...")
    video_path = get_latest_news_video()
    
    if not video_path:
        print("\n❌ No video found to upload. Run the automation pipeline first:")
        print("   python test_automation.py")
        return 1
    
    file_size_mb = video_path.stat().st_size / (1024 * 1024)
    print(f"✅ Found: {video_path.name}")
    print(f"   Size: {file_size_mb:.1f} MB")
    print(f"   Path: {video_path}")
    
    # Prepare metadata
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"News Highlights - {timestamp}"
    description = (
        "Daily news compilation featuring highlights from:\n"
        "• BBC News\n"
        "• Reuters\n"
        "• CNN\n"
        "• Sky News\n"
        "• Al Jazeera\n\n"
        "This is an automated compilation of 20-second clips from each news source, "
        "formatted for vertical viewing (1080x1920).\n\n"
        f"Generated: {timestamp}"
    )
    tags = [
        "news",
        "news highlights",
        "daily news",
        "news compilation",
        "bbc news",
        "reuters",
        "cnn",
        "sky news",
        "al jazeera",
        "shorts",
        "vertical video"
    ]
    
    # Ask for privacy setting
    print(f"\n📋 Video Metadata:")
    print(f"   Title: {title}")
    print(f"   Tags: {', '.join(tags[:5])}...")
    print(f"\n🔒 Privacy Options:")
    print("   1. private   - Only you can see it")
    print("   2. unlisted  - Anyone with the link can see it")
    print("   3. public    - Everyone can see it")
    
    privacy_choice = input("\nChoose privacy (1/2/3) [default: 2-unlisted]: ").strip()
    privacy_map = {"1": "private", "2": "unlisted", "3": "public", "": "unlisted"}
    privacy = privacy_map.get(privacy_choice, "unlisted")
    
    print(f"\n✅ Privacy set to: {privacy}")
    
    # Confirm upload
    print(f"\n⚠️  Ready to upload:")
    print(f"   File: {video_path.name}")
    print(f"   Size: {file_size_mb:.1f} MB")
    print(f"   Privacy: {privacy}")
    print(f"\n   This may take several minutes depending on file size and connection speed.")
    
    confirm = input("\nProceed with upload? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Upload cancelled")
        return 0
    
    # Upload the video
    print("\n" + "=" * 70)
    print("UPLOADING TO YOUTUBE")
    print("=" * 70)
    
    upload_result = skill.execute("upload", {
        "video_path": str(video_path),
        "title": title,
        "description": description,
        "tags": tags,
        "privacy": privacy,
        "category_id": "25",  # 25 = News & Politics
        "made_for_kids": False
    }, context)
    
    print("\n" + "=" * 70)
    if upload_result.success:
        print("✅ UPLOAD SUCCESSFUL!")
        print("=" * 70)
        print(upload_result.message)
        
        # Show next steps
        print("\n" + "=" * 70)
        print("NEXT STEPS")
        print("=" * 70)
        print("1. Check your YouTube Studio: https://studio.youtube.com")
        print("2. Verify the video uploaded correctly")
        print("3. Update title/description/thumbnail if needed")
        print("4. Change privacy settings if desired")
        
        if privacy == "private":
            print("5. Your video is PRIVATE - publish it when ready")
        elif privacy == "unlisted":
            print("5. Your video is UNLISTED - share the link with others")
        else:
            print("5. Your video is PUBLIC - it's live!")
        
        return 0
    else:
        print("❌ UPLOAD FAILED")
        print("=" * 70)
        print(upload_result.message)
        print("\n💡 Common issues:")
        print("   - Token expired: Re-authenticate via /admin")
        print("   - API quota exceeded: Try again later")
        print("   - File too large: Check file size limits")
        return 1


if __name__ == "__main__":
    sys.exit(main())
