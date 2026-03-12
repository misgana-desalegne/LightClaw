# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import random
from pathlib import Path

# Force UTF-8 encoding for console output
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuration - HARDCODED FOR AUTOMATION
TEMP_DIR = "temp_videos"
OUTPUT_DIR = "output_videos"
CLIP_DURATION = 20  # seconds - extract 20 seconds from each video
DOWNLOAD_DURATION = 20  # seconds - download only 20 seconds from middle

# FFmpeg paths - cross-platform
import shutil
FFMPEG_PATH = shutil.which('ffmpeg') or 'ffmpeg'
FFPROBE_PATH = shutil.which('ffprobe') or 'ffprobe'

def setup_directories():
    """Create necessary directories"""
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def check_dependencies():
    """Check if yt-dlp and ffmpeg are installed"""
    try:
        # Check ffmpeg
        result = subprocess.run([FFMPEG_PATH, '-version'], capture_output=True, timeout=5)
        if result.returncode == 0:
            print(f"✓ ffmpeg is installed")
        else:
            print(f"✗ ffmpeg not found in PATH")
            return False
    except Exception:
        print(f"✗ ffmpeg not found. Please install: sudo apt-get install ffmpeg")
        return False
    
    try:
        # Check yt-dlp - try user install first
        yt_dlp_path = os.path.expanduser('~/.local/bin/yt-dlp')
        if os.path.exists(yt_dlp_path):
            subprocess.run([yt_dlp_path, '--version'], capture_output=True, check=True)
            print("✓ yt-dlp is installed (user)")
        else:
            subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
            print("✓ yt-dlp is installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ yt-dlp not found. Installing...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--user', 'yt-dlp'], capture_output=True)
        print("✓ yt-dlp installed")
    
    return True

def download_video(url, index):
    """Download only 20 seconds from the middle of the video using yt-dlp"""
    output_path = os.path.join(TEMP_DIR, f"video_{index}.mp4")
    
    try:
        print(f"[{index}] Downloading 20 seconds from middle: {url}")
        
        # Use latest yt-dlp with Android client workaround
        yt_dlp_path = os.path.expanduser('~/.local/bin/yt-dlp')
        if not os.path.exists(yt_dlp_path):
            yt_dlp_path = 'yt-dlp'
        
        # First, get video info to find the middle point
        info_cmd = [
            yt_dlp_path,
            '--no-warnings',
            '-j',  # JSON output
            url
        ]
        
        info_result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)
        
        if info_result.returncode == 0:
            import json
            video_info = json.loads(info_result.stdout)
            duration = video_info.get('duration', 0)
            
            if duration > 0:
                # Calculate middle point
                middle_point = duration / 2
                start_time = max(0, middle_point - (DOWNLOAD_DURATION / 2))
                end_time = start_time + DOWNLOAD_DURATION
                
                print(f"    Video duration: {duration:.0f}s, downloading from {start_time:.0f}s to {end_time:.0f}s")
                
                # Download only the middle section
                cmd = [
                    yt_dlp_path,
                    '--no-warnings',
                    '-f', 'best[ext=mp4]/best',
                    '--extractor-args', 'youtube:player_client=android',  # Bypass YouTube restrictions
                    '--download-sections', f'*{start_time:.0f}-{end_time:.0f}',  # Download only middle section
                    '-o', output_path,
                    '--socket-timeout', '30',
                    url
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    print(f"    ✓ Downloaded {DOWNLOAD_DURATION}s section ({file_size / (1024*1024):.1f} MB)")
                    return output_path
                else:
                    # Fallback: download full video if section download fails
                    print(f"    ⚠ Section download failed, trying full video...")
                    cmd_fallback = [
                        yt_dlp_path,
                        '--no-warnings',
                        '-f', 'best[ext=mp4]/best',
                        '--extractor-args', 'youtube:player_client=android',
                        '-o', output_path,
                        '--socket-timeout', '30',
                        url
                    ]
                    result = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=300)
                    
                    if result.returncode == 0 and os.path.exists(output_path):
                        file_size = os.path.getsize(output_path)
                        print(f"    ✓ Downloaded full video ({file_size / (1024*1024):.1f} MB)")
                        return output_path
                    else:
                        print(f"    ✗ Failed to download")
                        if result.stderr:
                            print(f"    Error: {result.stderr[:200]}")
                        return None
            else:
                # Duration not available, download full video
                print(f"    ⚠ Duration unknown, downloading full video...")
                cmd = [
                    yt_dlp_path,
                    '--no-warnings',
                    '-f', 'best[ext=mp4]/best',
                    '--extractor-args', 'youtube:player_client=android',
                    '-o', output_path,
                    '--socket-timeout', '30',
                    url
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    print(f"    ✓ Downloaded full video ({file_size / (1024*1024):.1f} MB)")
                    return output_path
                else:
                    print(f"    ✗ Failed to download")
                    if result.stderr:
                        print(f"    Error: {result.stderr[:200]}")
                    return None
        else:
            # Could not get video info, download full video as fallback
            print(f"    ⚠ Could not get video info, downloading full video...")
            cmd = [
                yt_dlp_path,
                '--no-warnings',
                '-f', 'best[ext=mp4]/best',
                '--extractor-args', 'youtube:player_client=android',
                '-o', output_path,
                '--socket-timeout', '30',
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"    ✓ Downloaded full video ({file_size / (1024*1024):.1f} MB)")
                return output_path
            else:
                print(f"    ✗ Failed to download")
                if result.stderr:
                    print(f"    Error: {result.stderr[:200]}")
                return None
            
    except subprocess.TimeoutExpired:
        print(f"    ✗ Download timeout")
        return None
    except Exception as e:
        print(f"    ✗ Error downloading: {e}")
        return None

def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe"""
    try:
        cmd = [
            FFPROBE_PATH,
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1:noprint_wrappers=1',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())
        return duration
    except Exception as e:
        print(f"    Error getting duration: {e}")
        return None

def extract_clip(video_path, output_clip_path, index):
    """Extract clip from downloaded video (already 20 seconds from middle)"""
    try:
        duration = get_video_duration(video_path)
        
        if duration is None:
            print(f"    ✗ Could not determine video duration")
            return False
        
        # If video is already around 20 seconds (downloaded section), use it as-is
        if duration <= CLIP_DURATION + 5:  # Allow 5 seconds buffer
            print(f"    Using downloaded section as clip ({duration:.1f}s)")
            # Just copy the file
            import shutil
            shutil.copy2(video_path, output_clip_path)
            print(f"    ✓ Clip ready")
            return True
        else:
            # If we got a full video (fallback), extract from middle
            middle_point = duration / 2
            start_time = max(0, middle_point - (CLIP_DURATION / 2))
            
            # Make sure we don't go past the end
            if start_time + CLIP_DURATION > duration:
                start_time = duration - CLIP_DURATION
            
            clip_duration = CLIP_DURATION
            
            print(f"    Extracting {clip_duration:.1f}s clip from middle at {start_time:.1f}s (total: {duration:.1f}s)")
            
            cmd = [
                FFMPEG_PATH,
                '-i', video_path,
                '-ss', str(start_time),
                '-t', str(clip_duration),
                '-c:v', 'libx264',
                '-crf', '23',
                '-c:a', 'aac',  # Ensure audio codec is AAC
                '-b:a', '128k',  # Set audio bitrate
                '-map', '0:v',  # Always map video
                '-map', '0:a?',  # Map audio if it exists (optional)
                '-y',  # Overwrite output
                output_clip_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(output_clip_path):
                print(f"    ✓ Clip extracted")
                return True
            else:
                print(f"    ✗ Failed to extract clip")
                return False
    except Exception as e:
        print(f"    ✗ Error extracting clip: {e}")
        return False

def convert_to_tiktok_format(input_file, output_file):
    """Convert video to TikTok vertical format (9:16 aspect ratio with black bars)"""
    try:
        print(f"\nConverting to TikTok vertical format...")
        
        # TikTok aspect ratio is 9:16 (vertical)
        # We'll add black bars on the sides if needed
        cmd = [
            FFMPEG_PATH,
            '-i', input_file,
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black',
            '-c:v', 'libx264',
            '-crf', '23',
            '-map', '0:v',  # Always map video
            '-map', '0:a?',  # Map audio if it exists (optional)
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y',
            output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0 and os.path.exists(output_file):
            print(f"✓ Converted to TikTok format (1080x1920)")
            return True
        else:
            print(f"✗ Failed to convert to TikTok format")
            print(result.stderr[:200])
            return False
    except subprocess.TimeoutExpired:
        print(f"✗ Conversion timeout")
        return False
    except Exception as e:
        print(f"✗ Error converting format: {e}")
        return False

def join_clips(clip_paths, output_file):
    """Join multiple clips into one video"""
    try:
        if len(clip_paths) < 2:
            print("✗ Need at least 2 clips to join")
            return False
        
        # Normalize all clips to ensure consistent properties
        print(f"\nNormalizing {len(clip_paths)} clips for seamless joining...")
        normalized_clips = []
        
        for i, clip_path in enumerate(clip_paths):
            normalized_path = os.path.join(TEMP_DIR, f"normalized_{i}.mp4")
            
            # Re-encode each clip with consistent settings BEFORE joining
            # This ensures no pauses/stutters due to codec mismatches
            cmd = [
                FFMPEG_PATH,
                '-i', clip_path,
                '-c:v', 'libx264',
                '-preset', 'fast',  # Faster encoding
                '-crf', '23',
                '-r', '30',  # Force 30fps
                '-map', '0:v',  # Always map video
                '-map', '0:a?',  # Map audio if it exists (optional)
                '-c:a', 'aac',
                '-b:a', '128k',
                '-ar', '48000',  # Standard audio rate
                '-y',
                normalized_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0 and os.path.exists(normalized_path):
                normalized_clips.append(normalized_path)
                print(f"  ✓ Normalized clip {i+1}/{len(clip_paths)}")
            else:
                print(f"  ✗ Failed to normalize clip {i+1}")
                print(f"    Error: {result.stderr[:200]}")
                return False
        
        # Create concat file for ffmpeg
        concat_file = os.path.join(TEMP_DIR, "concat.txt")
        with open(concat_file, 'w') as f:
            for clip in normalized_clips:
                # Convert to absolute path and use forward slashes for ffmpeg
                abs_path = os.path.abspath(clip)
                # Use forward slashes for ffmpeg
                ffmpeg_path = abs_path.replace('\\', '/')
                f.write(f"file '{ffmpeg_path}'\n")
        
        print(f"\nJoining {len(normalized_clips)} normalized clips...")
        
        cmd = [
            FFMPEG_PATH,
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c:v', 'copy',  # Copy video stream (no re-encoding since already normalized)
            '-c:a', 'copy',  # Copy audio stream (already normalized to AAC)
            '-y',
            output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0 and os.path.exists(output_file):
            print(f"✓ Video joined successfully: {output_file}")
            
            # Clean up normalized clips
            for clip in normalized_clips:
                try:
                    os.remove(clip)
                except:
                    pass
            
            return True
        else:
            print(f"✗ Failed to join videos")
            print("Error output:")
            print(result.stderr[:500])
            return False
    except subprocess.TimeoutExpired:
        print(f"✗ Join operation timeout")
        return False
    except Exception as e:
        print(f"✗ Error joining clips: {e}")
        return False

def cleanup(keep_clips=False):
    """Clean up temporary files"""
    if not keep_clips and os.path.exists(TEMP_DIR):
        import shutil
        try:
            shutil.rmtree(TEMP_DIR)
            print("\n✓ Temporary files cleaned up")
        except Exception as e:
            print(f"Warning: Could not clean temp files: {e}")

def test_join_existing_clips():
    """Test joining already existing clips"""
    print("=" * 60)
    print("TEST: Joining Existing Clips")
    print("=" * 60)
    
    setup_directories()
    
    # Find existing clips
    existing_clips = []
    if os.path.exists(TEMP_DIR):
        for file in sorted(os.listdir(TEMP_DIR)):
            if file.startswith("clip_") and file.endswith(".mp4"):
                clip_path = os.path.join(TEMP_DIR, file)
                existing_clips.append(clip_path)
                print(f"Found: {clip_path}")
    
    if len(existing_clips) < 2:
        print(f"\n✗ Not enough clips found. Found {len(existing_clips)}, need at least 2")
        return False
    
    print(f"\n✓ Found {len(existing_clips)} clips to join")
    
    # Join clips
    output_filename = f"joined_test_{len(existing_clips)}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    if join_clips(existing_clips, output_path):
        print(f"\n✓ TEST PASSED!")
        print(f"Output: {output_path}")
        return True
    else:
        print(f"\n✗ TEST FAILED!")
        return False

def process_news_compilation():
    """
    AUTOMATION MODE: Hardcoded pipeline
    1. Fetch 5 news videos
    2. Download 20 seconds from middle of each (FAST!)
    3. Use downloaded sections as clips
    4. Stitch all clips together
    5. Convert to vertical TikTok format
    
    Returns: path to final video or None
    """
    print("=" * 60)
    print("AUTOMATED NEWS VIDEO COMPILATION")
    print("=" * 60)
    
    # Check dependencies
    if not check_dependencies():
        print("\nPlease install missing dependencies and try again.")
        return None
    
    # Setup directories
    setup_directories()
    
    # Step 1: Fetch 5 news videos
    print("\nStep 1: Fetching 5 news videos...")
    print("-" * 60)
    
    try:
        from viral_fetcher import fetch_5_news_videos
        videos = fetch_5_news_videos()
    except ImportError:
        print("✗ viral_fetcher module not found. Make sure viral_fetcher.py is in the same directory.")
        return None
    except Exception as e:
        print(f"✗ Error fetching videos: {e}")
        return None
    
    if not videos:
        print("✗ No videos fetched. Exiting.")
        return None
    
    if len(videos) < 2:
        print(f"✗ Only {len(videos)} video(s) fetched. Need at least 2 to create compilation.")
        return None
    
    urls = [v['url'] for v in videos]
    print(f"\n✓ {len(urls)} URL(s) ready for processing")
    
    # Step 2: Download 20-second sections and create clips
    print("\nStep 2: Downloading 20-second sections from middle of each video...")
    print("-" * 60)
    
    clips = []
    for index, url in enumerate(urls, 1):
        print(f"\n[{index}/{len(urls)}] Processing video...")
        
        # Download 20 seconds from middle
        video_path = download_video(url, index)
        if not video_path:
            print(f"    ⚠ Skipping this video")
            continue
        
        # Create clip (will use downloaded section if it's already 20s)
        clip_path = os.path.join(TEMP_DIR, f"clip_{index}.mp4")
        if extract_clip(video_path, clip_path, index):
            clips.append(clip_path)
        else:
            print(f"    ⚠ Skipping this clip")
    
    if not clips:
        print("\n✗ No clips were created. Exiting.")
        cleanup(keep_clips=False)
        return None
    
    if len(clips) < 2:
        print(f"\n⚠ Only {len(clips)} clip(s) created. Need at least 2 clips to join.")
        cleanup(keep_clips=True)
        return None
    
    print(f"\n✓ Successfully created {len(clips)} clip(s)")
    
    # Step 3: Join clips
    print("\nStep 3: Stitching clips together...")
    print("-" * 60)
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"news_compilation_{timestamp}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    if not join_clips(clips, output_path):
        print("\n✗ Failed to join clips")
        cleanup(keep_clips=True)
        return None
    
    # Step 4: Convert to TikTok vertical format
    print("\nStep 4: Converting to vertical format...")
    print("-" * 60)
    
    tiktok_filename = f"news_vertical_{timestamp}.mp4"
    tiktok_path = os.path.join(OUTPUT_DIR, tiktok_filename)
    
    if convert_to_tiktok_format(output_path, tiktok_path):
        print(f"\n{'=' * 60}")
        print(f"✓ SUCCESS! News compilation created:")
        print(f"  {tiktok_path}")
        print(f"  Format: 1080x1920 (9:16 vertical)")
        print(f"  Duration: ~{len(clips) * 20} seconds ({len(clips)} clips × 20s)")
        print(f"{'=' * 60}")
        
        # Remove intermediate file to save space
        try:
            os.remove(output_path)
        except:
            pass
        
        # Cleanup temp files
        cleanup(keep_clips=False)
        
        return tiktok_path
    else:
        print(f"\n⚠ Vertical format conversion failed")
        print(f"  Standard format saved at: {output_path}")
        cleanup(keep_clips=False)
        return output_path

def main():
    """Main entry point for automation"""
    try:
        final_video = process_news_compilation()
        
        if final_video:
            print(f"\n✓ Final video ready for upload:")
            print(f"  {final_video}")
            return final_video
        else:
            print("\n✗ Compilation failed")
            return None
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        cleanup(keep_clips=False)
        return None
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        cleanup(keep_clips=False)
        return None

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        cleanup(keep_clips=False)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        cleanup(keep_clips=False)
