# -*- coding: utf-8 -*-
"""
Viral Video Link Fetcher
Automatically fetches viral video URLs from various sources
"""

import requests
import json
import sys
import subprocess
from typing import List

class ViralVideoFetcher:
    """Fetch viral videos from different platforms"""
    
    # Popular YouTube news channels with their channel IDs
    NEWS_CHANNELS = {
        'BBC News': 'UCuqRhIjT0WXEg5ZynCr0Gkw',
        'Reuters': 'UCoZDxDZCzXV65CDEWoUsKCA',
        'Associated Press': 'UCEJYcwysXATRWVJM9qLFPOA',
        'CNN': 'UCupvZG-FFqnIQFFwMYl58BA',
        'Sky News': 'UCtN3SZl1PdHQVGIGDJbvV1A',
        'NBC News': 'UCeY0bbntWzzVIaj2z3QigXg',
        'Fox News': 'UCXIJgqnII2ZODtbriXWGAcQ',
        'Al Jazeera': 'UCNsMeH0OXs_52AEQvweWrUQ',
        'DW News': 'UCknLrEdhBC8p-lMues8XOXA',
        'The Guardian': 'UCIRYvXwJaFfkS_gCYANQ8-w',
        'NPR': 'UCPzHduCvyoe9g2s1xl0_wcA',
        'ABC News': 'UCBi2mrWuNuyYy4gbM6fU18Q',
    }
    
    # Popular YouTube tech news channels
    TECH_CHANNELS = {
        'Linus Tech Tips': 'UCXuqSBlHAE6Xw-yeJA7Ufg',
        'MKBHD': 'UCBJycsmduvVTj7T7-5sAK7Q',
        'The Verge': 'UCddiUEpGJrSvLoEQrI7KO1A',
        'Marques Brownlee': 'UCBJycsmduvVTj7T7-5sAK7Q',
        'Tech Insider': 'UCOmeYUB-tp8EmJGaAyRE3Ow',
        'WIRED': 'UCfpwLfWiR23-yd_YqaOO3Cg',
        'CNet': 'UCOmcA3f_MrHVtIW5Lk287Nw',
        'Android Authority': 'UC7YL0jV-2MJm2QmqTR5vBvg',
        '9to5Google': 'UCpDwmikwks-_-bnXW28pontA',
        'MacRumors': 'UCWy9m1KZC-S0rkQmHrHaWzA',
        'UNBOX THERAPY': 'UCkwN2eVXSo5mMhE_v0YHBjA',
        'Dbrand': 'UCKJSdyQEfqG62SEWvQ7TLCg',
    }
    
    @staticmethod
    def fetch_news_videos(channel_name=None, max_results=10):
        """
        Fetch latest news videos by searching YouTube for news from specific channels
        """
        print("Fetching news videos from YouTube...")
        videos = []
        
        # News search queries mapped to channels
        search_queries = {
            'BBC News': 'BBC News latest',
            'Reuters': 'Reuters news',
            'Associated Press': 'AP news latest',
            'CNN': 'CNN news today',
            'Sky News': 'Sky News latest',
            'NBC News': 'NBC News',
            'Fox News': 'Fox News today',
            'Al Jazeera': 'Al Jazeera English news',
            'DW News': 'DW News',
            'The Guardian': 'Guardian news',
            'NPR': 'NPR news',
            'ABC News': 'ABC News',
        }
        
        # If specific channel requested
        if channel_name and channel_name in search_queries:
            queries_to_fetch = {channel_name: search_queries[channel_name]}
        else:
            # Use all news channels
            queries_to_fetch = search_queries
        
        print(f"Fetching from {len(queries_to_fetch)} news source(s)...")
        videos_per_source = max(1, max_results // len(queries_to_fetch))
        
        for news_source, search_query in queries_to_fetch.items():
            if len(videos) >= max_results:
                break
            
            try:
                print(f"  Searching for {news_source}...", end=" ", flush=True)
                
                # Search YouTube using yt-dlp via python module
                cmd = [
                    sys.executable,
                    '-m', 'yt_dlp',
                    '--flat-playlist',
                    '-j',
                    '--no-warnings',
                    f'ytsearch{videos_per_source}:{search_query}'
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                count_before = len(videos)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line and len(videos) < max_results:
                            try:
                                video_data = json.loads(line)
                                video_id = video_data.get('id') or video_data.get('url', '').split('/')[-1]
                                if video_id and 'http' in video_data.get('url', ''):
                                    videos.append({
                                        'url': f'https://www.youtube.com/watch?v={video_id}',
                                        'title': video_data.get('title', 'Untitled'),
                                        'channel': news_source,
                                        'source': f'YouTube News - {news_source}',
                                    })
                            except:
                                pass
                
                count_added = len(videos) - count_before
                print(f"✓ ({count_added} video(s))")
                        
            except subprocess.TimeoutExpired:
                print("(timeout)")
                continue
            except Exception as e:
                print("(error)")
                continue
        
        return videos
    
    @staticmethod
    def fetch_tech_videos(channel_name=None, max_results=10):
        """
        Fetch latest tech videos by searching YouTube for tech from specific channels
        """
        print("Fetching tech news videos from YouTube...")
        videos = []
        
        # Tech search queries mapped to channels
        search_queries = {
            'Linus Tech Tips': 'Linus Tech Tips latest',
            'MKBHD': 'MKBHD tech review',
            'The Verge': 'The Verge tech news',
            'Marques Brownlee': 'Marques Brownlee review',
            'Tech Insider': 'Tech Insider news',
            'WIRED': 'WIRED tech',
            'CNet': 'CNet tech',
            'Android Authority': 'Android Authority news',
            '9to5Google': '9to5Google news',
            'MacRumors': 'MacRumors Apple news',
            'UNBOX THERAPY': 'UNBOX THERAPY',
            'Dbrand': 'Dbrand tech',
        }
        
        # If specific channel requested
        if channel_name and channel_name in search_queries:
            queries_to_fetch = {channel_name: search_queries[channel_name]}
        else:
            # Use all tech channels
            queries_to_fetch = search_queries
        
        print(f"Fetching from {len(queries_to_fetch)} tech source(s)...")
        videos_per_source = max(1, max_results // len(queries_to_fetch))
        
        for tech_source, search_query in queries_to_fetch.items():
            if len(videos) >= max_results:
                break
            
            try:
                print(f"  Searching for {tech_source}...", end=" ", flush=True)
                
                # Search YouTube using yt-dlp via python module
                cmd = [
                    sys.executable,
                    '-m', 'yt_dlp',
                    '--flat-playlist',
                    '-j',
                    '--no-warnings',
                    f'ytsearch{videos_per_source}:{search_query}'
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                count_before = len(videos)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line and len(videos) < max_results:
                            try:
                                video_data = json.loads(line)
                                video_id = video_data.get('id') or video_data.get('url', '').split('/')[-1]
                                if video_id and 'http' in video_data.get('url', ''):
                                    videos.append({
                                        'url': f'https://www.youtube.com/watch?v={video_id}',
                                        'title': video_data.get('title', 'Untitled'),
                                        'channel': tech_source,
                                        'source': f'YouTube Tech - {tech_source}',
                                    })
                            except:
                                pass
                
                count_added = len(videos) - count_before
                print(f"✓ ({count_added} video(s))")
                        
            except subprocess.TimeoutExpired:
                print("(timeout)")
                continue
            except Exception as e:
                print("(error)")
                continue
        
        return videos
    
    @staticmethod
    def list_news_sources():
        """List all available news sources"""
        print("\nAvailable news sources:")
        for i, source in enumerate(ViralVideoFetcher.NEWS_CHANNELS.keys(), 1):
            print(f"  {i}. {source}")
        print(f"  {len(ViralVideoFetcher.NEWS_CHANNELS) + 1}. All sources")
    
    @staticmethod
    def list_tech_sources():
        """List all available tech sources"""
        print("\nAvailable tech sources:")
        for i, source in enumerate(ViralVideoFetcher.TECH_CHANNELS.keys(), 1):
            print(f"  {i}. {source}")
        print(f"  {len(ViralVideoFetcher.TECH_CHANNELS) + 1}. All sources")
    
    @staticmethod
    def fetch_youtube_trending(max_results=10):
        """Fetch YouTube trending videos using yt-dlp"""
        print("Fetching YouTube trending videos...")
        
        try:
            cmd = [
                sys.executable,
                '-m', 'yt_dlp',
                '--flat-playlist',
                '-j',
                '--no-warnings',
                'https://www.youtube.com/feed/trending'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            videos = []
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line and len(videos) < max_results:
                        try:
                            video_data = json.loads(line)
                            if 'url' in video_data or 'id' in video_data:
                                video_id = video_data.get('id', video_data.get('url', '').split('/')[-1])
                                videos.append({
                                    'url': f'https://www.youtube.com/watch?v={video_id}',
                                    'title': video_data.get('title', 'Untitled'),
                                    'source': 'YouTube Trending'
                                })
                        except:
                            pass
            
            return videos
        except Exception as e:
            print(f"✗ Error fetching YouTube videos: {e}")
            return []
    
    @staticmethod
    def fetch_reddit_videos(subreddit="videos", max_results=10):
        """
        Fetch trending videos from Reddit
        Requires: pip install praw
        """
        try:
            import praw
            
            reddit = praw.Reddit(
                client_id='YOUR_CLIENT_ID',
                client_secret='YOUR_CLIENT_SECRET',
                user_agent='VideoClipper/1.0'
            )
            
            print(f"Fetching trending videos from r/{subreddit}...")
            videos = []
            
            for post in reddit.subreddit(subreddit).hot(limit=max_results):
                if hasattr(post, 'url') and ('youtu' in post.url or 'reddit' in post.url):
                    videos.append({
                        'url': post.url,
                        'title': post.title,
                        'source': f'Reddit (r/{subreddit})'
                    })
            
            return videos
        except ImportError:
            print("✗ praw not installed. Run: pip install praw")
            return []
        except Exception as e:
            print(f"✗ Error fetching Reddit videos: {e}")
            return []
    
    @staticmethod
    def fetch_from_urls_file(filename="viral_urls.txt"):
        """
        Read URLs from a text file
        One URL per line
        """
        try:
            with open(filename, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
            print(f"✓ Loaded {len(urls)} URL(s) from {filename}")
            return [{'url': url, 'title': url, 'source': 'File'} for url in urls]
        except FileNotFoundError:
            print(f"✗ File not found: {filename}")
            return []
    
    @staticmethod
    def fetch_from_youtube_playlist(playlist_url):
        """
        Fetch all videos from a YouTube playlist using yt-dlp
        """
        try:
            print(f"Fetching YouTube playlist...")
            
            cmd = [
                sys.executable,
                '-m', 'yt_dlp',
                '--flat-playlist',
                '-j',
                '--no-warnings',
                playlist_url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            videos = []
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            video_data = json.loads(line)
                            if 'url' in video_data or 'id' in video_data:
                                video_id = video_data.get('id', video_data.get('url', '').split('/')[-1])
                                videos.append({
                                    'url': f'https://www.youtube.com/watch?v={video_id}',
                                    'title': video_data.get('title', 'Untitled'),
                                    'source': 'YouTube Playlist'
                                })
                        except:
                            pass
            
            print(f"✓ Found {len(videos)} video(s) in playlist")
            return videos
        except Exception as e:
            print(f"✗ Error fetching playlist: {e}")
            return []
    
    @staticmethod
    def save_urls_to_file(videos, filename="fetched_urls.txt"):
        """Save fetched video URLs to a file"""
        try:
            with open(filename, 'w') as f:
                for video in videos:
                    f.write(video['url'] + '\n')
            print(f"✓ Saved {len(videos)} URL(s) to {filename}")
            return True
        except Exception as e:
            print(f"✗ Error saving URLs: {e}")
            return False

def fetch_5_news_videos():
    """
    Hardcoded automation function: Fetch exactly 5 news videos (1 from each of 5 channels)
    No CLI interaction - designed for automated pipeline
    """
    print("=" * 60)
    print("FETCHING 5 NEWS VIDEOS FOR AUTOMATION")
    print("=" * 60)
    
    # Hardcoded: Use these 5 news channels
    TARGET_CHANNELS = ['BBC News', 'Reuters', 'CNN', 'Sky News', 'Al Jazeera']
    
    fetcher = ViralVideoFetcher()
    videos = []
    
    print(f"\nFetching from {len(TARGET_CHANNELS)} news sources...")
    
    for channel in TARGET_CHANNELS:
        try:
            channel_videos = fetcher.fetch_news_videos(channel_name=channel, max_results=1)
            if channel_videos:
                videos.extend(channel_videos)
                print(f"  ✓ {channel}: {channel_videos[0]['title'][:50]}...")
            else:
                print(f"  ✗ {channel}: No videos found")
        except Exception as e:
            print(f"  ✗ {channel}: Error ({e})")
    
    if len(videos) >= 5:
        print(f"\n✓ Successfully fetched {len(videos)} news videos")
    else:
        print(f"\n⚠ Only fetched {len(videos)}/5 videos")
    
    return videos

if __name__ == "__main__":
    # Automation mode: fetch 5 news videos and display
    videos = fetch_5_news_videos()
    
    if videos:
        print("\n" + "=" * 60)
        print("FETCHED VIDEOS:")
        print("=" * 60)
        for i, video in enumerate(videos, 1):
            print(f"{i}. [{video['channel']}] {video['title']}")
            print(f"   URL: {video['url']}")
        print("=" * 60)
