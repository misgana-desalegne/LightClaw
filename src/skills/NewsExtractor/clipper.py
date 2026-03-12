# -*- coding: utf-8 -*-
"""
Single Video Clipper
Extract multiple 20-second clips from a single YouTube video
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import timedelta

# Force UTF-8 encoding for console output
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuration
TEMP_DIR = "temp_videos"
OUTPUT_DIR = "shorts_from_youtube"  # TikTok/YouTube Shorts folder
CLIP_DURATION = 20  # seconds
NUM_CLIPS = 5  # Number of clips to extract
SHORTS_WIDTH = 1080   # TikTok/YouTube Shorts: 9:16 aspect ratio
SHORTS_HEIGHT = 1920

# FFmpeg paths
FFMPEG_PATH = r"C:\ffmpeg\ffmpeg-8.0.1-essentials_build\bin\ffmpeg.exe"
FFPROBE_PATH = r"C:\ffmpeg\ffmpeg-8.0.1-essentials_build\bin\ffprobe.exe"

def setup_directories():
    """Create necessary directories"""
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def check_dependencies():
    """Check if yt-dlp and ffmpeg are installed"""
    ffmpeg_ok = os.path.exists(FFMPEG_PATH) and os.path.exists(FFPROBE_PATH)
    
    if ffmpeg_ok:
        print(f"✓ ffmpeg is installed at {FFMPEG_PATH}")
    else:
        print(f"✗ ffmpeg not found at {FFMPEG_PATH}")
        return False
    
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
        print("✓ yt-dlp is installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ yt-dlp not found. Installing...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'yt-dlp'], capture_output=True)
        print("✓ yt-dlp installed")
    
    return True

def get_video_duration(video_path):
    """Get duration of a video file in seconds"""
    try:
        cmd = [
            FFPROBE_PATH,
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1:nokey_sep="="',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())
        return duration
    except Exception as e:
        print(f"Error getting video duration: {e}")
        return 0

def download_video(url):
    """Download video from URL using yt-dlp"""
    output_path = os.path.join(TEMP_DIR, "source_video.mp4")
    
    try:
        print(f"Downloading video from: {url}")
        
        cmd = [
            'yt-dlp',
            '--no-warnings',
            '-f', 'best[ext=mp4]/best',
            '-o', output_path,
            '--socket-timeout', '30',
            url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✓ Downloaded successfully ({file_size / (1024*1024):.1f} MB)")
            return output_path
        else:
            print(f"✗ Download failed")
            return None
            
    except subprocess.TimeoutExpired:
        print("✗ Download timed out")
        return None
    except Exception as e:
        print(f"✗ Error downloading: {e}")
        return None

def download_video_optimized(url, start_time, duration):
    """Download only the needed section of a video (faster!)"""
    output_path = os.path.join(TEMP_DIR, f"section_{start_time}_{duration}.mp4")
    
    try:
        print(f"Downloading {duration}s section starting at {start_time}s...")
        
        cmd = [
            'yt-dlp',
            '--no-warnings',
            '-f', 'best[ext=mp4]/best',
            '-o', output_path,
            '--socket-timeout', '30',
            '--download-sections', f'*{start_time}-{start_time + duration}',
            url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"  ✓ Downloaded section ({file_size / (1024*1024):.1f} MB)")
            return output_path
        else:
            # Fallback to full download if sections not supported
            return None
            
    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        return None

def create_clips_from_video_optimized(url, num_clips, clip_duration):
    """Create clips by downloading only needed sections (FAST!)"""
    try:
        # Get video info to know total duration
        info = get_video_info(url)
        if not info:
            print("✗ Could not get video info")
            return False
        
        total_duration = info['duration']
        
        if total_duration <= 0:
            print(f"✗ Could not determine video duration")
            return False
        
        print(f"\n✓ Video duration: {int(total_duration)} seconds")
        
        # Calculate start times for clips
        if total_duration <= clip_duration * num_clips:
            intervals = [0]
        else:
            step = (total_duration - clip_duration) / (num_clips - 1)
            intervals = [int(i * step) for i in range(num_clips)]
        
        print(f"✓ Creating {len(intervals)} vertical shorts (1080x1920)...\n")
        
        clips_created = []
        
        for idx, start_time in enumerate(intervals, 1):
            clip_name = f"short_{idx:02d}.mp4"
            clip_path = os.path.join(OUTPUT_DIR, clip_name)
            
            # Make sure start time is valid
            start_time = min(start_time, int(total_duration - clip_duration))
            
            print(f"[{idx}/{len(intervals)}] Downloading & processing {start_time}s-{start_time + clip_duration}s...", end=" ", flush=True)
            
            # Download only this section
            temp_section = os.path.join(TEMP_DIR, f"temp_section_{idx}.mp4")
            
            cmd_download = [
                'yt-dlp',
                '--no-warnings',
                '-f', 'best[ext=mp4]/best',
                '-o', temp_section,
                '--socket-timeout', '30',
                '--download-sections', f'*{start_time}-{start_time + clip_duration}',
                url
            ]
            
            result = subprocess.run(cmd_download, capture_output=True, text=True, timeout=120)
            
            # If section download failed, try full extraction from downloaded file
            if result.returncode != 0 or not os.path.exists(temp_section):
                print("(fallback to full download)", end=" ", flush=True)
                # This would need the full video, which defeats the purpose
                # Skip this clip
                print("✗ Skipped")
                continue
            
            # Now process this section to make it vertical shorts format
            filter_complex = (
                f"[0:v]scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=decrease,"
                f"pad={SHORTS_WIDTH}:{SHORTS_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black[v];"
                f"[v]split=2[v1][v2];"
                f"[v1]scale={SHORTS_WIDTH}:{SHORTS_HEIGHT},boxblur=40:2[bg];"
                f"[bg][v2]overlay=(W-w)/2:(H-h)/2[out]"
            )
            
            cmd_encode = [
                FFMPEG_PATH,
                '-i', temp_section,
                '-filter_complex', filter_complex,
                '-map', '[out]',
                '-map', '0:a?',
                '-c:v', 'libx264',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',
                clip_path
            ]
            
            result = subprocess.run(cmd_encode, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0 and os.path.exists(clip_path):
                file_size = os.path.getsize(clip_path)
                print(f"✓ ({file_size / (1024*1024):.1f} MB)")
                clips_created.append(clip_path)
                
                # Cleanup temp section
                try:
                    os.remove(temp_section)
                except:
                    pass
            else:
                print(f"✗ Failed")
                try:
                    os.remove(temp_section)
                except:
                    pass
        
        return len(clips_created) > 0
        
    except Exception as e:
        print(f"✗ Error creating clips: {e}")
        return False
    """Create multiple TikTok/Shorts-style vertical clips from a single video"""
    try:
        # Get video duration
        total_duration = get_video_duration(video_path)
        
        if total_duration <= 0:
            print(f"✗ Could not determine video duration")
            return False
        
        print(f"\n✓ Video duration: {int(total_duration)} seconds")
        
        # Calculate start times for clips
        # Distribute clips evenly across the video
        if total_duration <= clip_duration * num_clips:
            # Video too short, create clips from beginning
            intervals = [0]
            print(f"✓ Video is shorter than requested clips, creating clips from beginning")
        else:
            # Calculate step size to distribute clips evenly
            step = (total_duration - clip_duration) / (num_clips - 1)
            intervals = [int(i * step) for i in range(num_clips)]
        
        print(f"\n✓ Creating {len(intervals)} vertical clips ({SHORTS_WIDTH}x{SHORTS_HEIGHT})...\n")
        
        clips_created = []
        
        for idx, start_time in enumerate(intervals, 1):
            clip_name = f"short_{idx:02d}.mp4"
            clip_path = os.path.join(OUTPUT_DIR, clip_name)
            
            # Make sure start time doesn't exceed available video
            start_time = min(start_time, int(total_duration - clip_duration))
            
            print(f"[{idx}/{len(intervals)}] Creating short at {start_time}s - {clip_name}", end=" ", flush=True)
            
            # FFmpeg filter to create vertical video (TikTok/YouTube Shorts style)
            # Scale and pad video to 9:16 aspect ratio with background blur
            filter_complex = (
                f"[0:v]scale={SHORTS_WIDTH}:{SHORTS_HEIGHT}:force_original_aspect_ratio=decrease,"
                f"pad={SHORTS_WIDTH}:{SHORTS_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black[v];"
                f"[v]split=2[v1][v2];"
                f"[v1]scale={SHORTS_WIDTH}:{SHORTS_HEIGHT},boxblur=40:2[bg];"
                f"[bg][v2]overlay=(W-w)/2:(H-h)/2[out]"
            )
            
            cmd = [
                FFMPEG_PATH,
                '-i', video_path,
                '-ss', str(start_time),
                '-t', str(clip_duration),
                '-filter_complex', filter_complex,
                '-map', '[out]',
                '-map', '0:a?',
                '-c:v', 'libx264',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',
                clip_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0 and os.path.exists(clip_path):
                file_size = os.path.getsize(clip_path)
                print(f"✓ ({file_size / (1024*1024):.1f} MB)")
                clips_created.append(clip_path)
            else:
                print(f"✗ Failed")
        
        return len(clips_created) > 0
        
    except Exception as e:
        print(f"✗ Error creating clips: {e}")
        return False

def get_video_info(url):
    """Get video info without downloading"""
    try:
        cmd = [
            'yt-dlp',
            '-j',
            '--no-warnings',
            url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown')
            }
    except:
        pass
    
    return None

def cleanup_temp():
    """Clean up temporary files"""
    import shutil
    try:
        shutil.rmtree(TEMP_DIR)
        print("\n✓ Temporary files cleaned up")
    except Exception as e:
        print(f"Warning: Could not clean temp files: {e}")

def main():
    """Main function"""
    global NUM_CLIPS, CLIP_DURATION
    
    print("=" * 70)
    print("SINGLE VIDEO CLIPPER - TikTok/YouTube SHORTS GENERATOR")
    print("Extract & convert to vertical shorts from one YouTube video")
    print("=" * 70)
    
    # Ask about download method
    print("\n" + "=" * 70)
    print("DOWNLOAD OPTIMIZATION")
    print("=" * 70)
    
    print("\nHow do you want to download?")
    print("  1 = Fast (download only needed sections) - RECOMMENDED")
    print("  2 = Full download (download entire video)")
    
    download_choice = input("\nSelect option (1-2): ").strip()
    
    use_optimized = download_choice != "2"
    
    if use_optimized:
        print("✓ Will download only needed sections (FASTER!)")
    else:
        print("✓ Will download entire video")
    print("\nOptions:")
    print("  1 = Enter YouTube URL")
    print("  2 = Enter from clipboard")
    
    url_choice = input("\nSelect option (1-2): ").strip()
    
    url = None
    
    if url_choice == "2":
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            url = root.clipboard_get()
            root.destroy()
            print(f"✓ Got URL from clipboard")
        except:
            print("Could not read clipboard, using manual entry")
            url_choice = "1"
    
    if url_choice == "1":
        url = input("\nEnter YouTube URL: ").strip()
    
    if not url:
        print("✗ No URL provided")
        return
    
    # Get video info
    print("\nFetching video info...")
    info = get_video_info(url)
    
    if info:
        print(f"✓ Title: {info['title'][:60]}")
        print(f"✓ Duration: {info['duration']} seconds ({int(info['duration']/60)} min)")
        print(f"✓ Uploader: {info['uploader'][:50]}")
    
    # Ask about number of clips
    print("\n" + "=" * 70)
    print("CLIP SETTINGS")
    print("=" * 70)
    
    print("\nHow many clips do you want to extract?")
    print("  1 = 3 clips")
    print("  2 = 5 clips (default)")
    print("  3 = 8 clips")
    print("  4 = 10 clips")
    print("  5 = Custom number")
    
    num_choice = input("\nSelect option (1-5): ").strip()
    
    num_map = {
        '1': 3,
        '2': 5,
        '3': 8,
        '4': 10,
    }
    
    if num_choice in num_map:
        NUM_CLIPS = num_map[num_choice]
    elif num_choice == '5':
        try:
            custom_num = int(input("Enter number of clips: ").strip())
            NUM_CLIPS = max(1, custom_num)
        except ValueError:
            print("Invalid input, using default 5 clips")
            NUM_CLIPS = 5
    else:
        print("Invalid choice, using default 5 clips")
        NUM_CLIPS = 5
    
    print(f"✓ Will extract {NUM_CLIPS} clips")
    
    # Ask about clip duration
    print("\n" + "=" * 70)
    print("CLIP DURATION")
    print("=" * 70)
    
    print("\nHow long should each clip be?")
    print("  1 = 10 seconds")
    print("  2 = 15 seconds")
    print("  3 = 20 seconds (default)")
    print("  4 = 30 seconds")
    print("  5 = Custom duration (in seconds)")
    
    duration_choice = input("\nSelect option (1-5): ").strip()
    
    duration_map = {
        '1': 10,
        '2': 15,
        '3': 20,
        '4': 30,
    }
    
    if duration_choice in duration_map:
        CLIP_DURATION = duration_map[duration_choice]
    elif duration_choice == '5':
        try:
            custom_duration = int(input("Enter clip duration in seconds: ").strip())
            CLIP_DURATION = max(1, custom_duration)
        except ValueError:
            print("Invalid input, using default 20 seconds")
            CLIP_DURATION = 20
    else:
        print("Invalid choice, using default 20 seconds")
        CLIP_DURATION = 20
    
    print(f"✓ Each clip will be {CLIP_DURATION} seconds")
    
    # Create clips using chosen method
    print("\n" + "=" * 70)
    print("CREATING CLIPS")
    print("=" * 70)
    
    if use_optimized:
        # Fast method - download only sections as needed
        if create_clips_from_video_optimized(url, NUM_CLIPS, CLIP_DURATION):
            print(f"\n✓ Successfully created TikTok/YouTube Shorts!")
            print(f"✓ Output folder: {OUTPUT_DIR}")
            print(f"✓ Format: {SHORTS_WIDTH}x{SHORTS_HEIGHT} (9:16 vertical)")
            
            # List created files
            output_files = sorted([f for f in os.listdir(OUTPUT_DIR) if f.endswith('.mp4')])
            print(f"\nCreated {len(output_files)} short(s):")
            for f in output_files[-NUM_CLIPS:]:
                file_path = os.path.join(OUTPUT_DIR, f)
                file_size = os.path.getsize(file_path)
                print(f"  • {f} ({file_size / (1024*1024):.1f} MB)")
            
            # Cleanup
            cleanup = input("\nClean up temporary files? (y/n): ").lower() == 'y'
            if cleanup:
                cleanup_temp()
        else:
            print("✗ Failed to create shorts")
    else:
        # Traditional method - download full video first
        video_path = download_video(url)
        
        if not video_path:
            print("✗ Failed to download video")
            return
        
        if create_clips_from_video(video_path, NUM_CLIPS, CLIP_DURATION):
            print(f"\n✓ Successfully created TikTok/YouTube Shorts!")
            print(f"✓ Output folder: {OUTPUT_DIR}")
            print(f"✓ Format: {SHORTS_WIDTH}x{SHORTS_HEIGHT} (9:16 vertical)")
            
            # List created files
            output_files = sorted([f for f in os.listdir(OUTPUT_DIR) if f.endswith('.mp4')])
            print(f"\nCreated {len(output_files)} short(s):")
            for f in output_files[-NUM_CLIPS:]:
                file_path = os.path.join(OUTPUT_DIR, f)
                file_size = os.path.getsize(file_path)
                print(f"  • {f} ({file_size / (1024*1024):.1f} MB)")
            
            # Cleanup
            cleanup = input("\nClean up temporary files? (y/n): ").lower() == 'y'
            if cleanup:
                cleanup_temp()
        else:
            print("✗ Failed to create shorts")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAborted by user")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
