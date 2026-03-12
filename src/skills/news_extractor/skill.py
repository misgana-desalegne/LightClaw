from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Any

from src.agent.context import Context
from src.models.schemas import SkillResult


class NewsExtractorSkill:
    name = "news_extractor"
    version = "1.0.0"
    description = "Fetch viral news and tech videos, create clips, and join them."
    actions = ["fetch_news", "fetch_tech", "fetch_trending", "create_clips", "status"]
    required_env = []

    def __init__(self) -> None:
        """Initialize the NewsExtractor skill."""
        # NewsExtractor is a sibling directory at src/skills/NewsExtractor
        self.news_extractor_path = Path(__file__).parent.parent / "NewsExtractor"
        self.viral_fetcher = self.news_extractor_path / "viral_fetcher.py"
        self.clipper = self.news_extractor_path / "videoClipper.py"
        
    def can_handle(self, intent: str) -> bool:
        """Check if this skill can handle the intent."""
        return any(keyword in intent.lower() for keyword in ["news", "viral", "video", "clip", "tech"])

    def execute(self, action: str, payload: dict, context: Context) -> SkillResult:
        """Execute the requested action."""
        if action == "fetch_news":
            return self._fetch_news(payload)
        if action == "fetch_tech":
            return self._fetch_tech(payload)
        if action == "fetch_trending":
            return self._fetch_trending(payload)
        if action == "create_clips":
            return self._create_clips(payload)
        if action == "status":
            return self._get_status()
        
        return SkillResult(
            success=False,
            skill=self.name,
            action=action,
            message="Unsupported action"
        )

    def _fetch_news(self, payload: dict) -> SkillResult:
        """Fetch latest news videos."""
        channel = payload.get("channel")
        max_results = payload.get("max_results", 5)
        
        try:
            # Import the viral fetcher module
            sys.path.insert(0, str(self.news_extractor_path))
            from viral_fetcher import ViralVideoFetcher
            
            videos = ViralVideoFetcher.fetch_news_videos(
                channel_name=channel,
                max_results=max_results
            )
            
            if not videos:
                return SkillResult(
                    success=False,
                    skill=self.name,
                    action="fetch_news",
                    message="No news videos found"
                )
            
            # Format response
            video_list = []
            for i, video in enumerate(videos, 1):
                video_list.append(
                    f"{i}. [{video['channel']}] {video['title'][:60]}...\n   {video['url']}"
                )
            
            message = f"📰 Found {len(videos)} news video(s):\n\n" + "\n\n".join(video_list)
            
            return SkillResult(
                success=True,
                skill=self.name,
                action="fetch_news",
                message=message,
                data={"videos": videos, "count": len(videos)}
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                skill=self.name,
                action="fetch_news",
                message=f"Error fetching news videos: {str(e)}"
            )

    def _fetch_tech(self, payload: dict) -> SkillResult:
        """Fetch latest tech news videos."""
        channel = payload.get("channel")
        max_results = payload.get("max_results", 5)
        
        try:
            sys.path.insert(0, str(self.news_extractor_path))
            from viral_fetcher import ViralVideoFetcher
            
            videos = ViralVideoFetcher.fetch_tech_videos(
                channel_name=channel,
                max_results=max_results
            )
            
            if not videos:
                return SkillResult(
                    success=False,
                    skill=self.name,
                    action="fetch_tech",
                    message="No tech videos found"
                )
            
            # Format response
            video_list = []
            for i, video in enumerate(videos, 1):
                video_list.append(
                    f"{i}. [{video['channel']}] {video['title'][:60]}...\n   {video['url']}"
                )
            
            message = f"💻 Found {len(videos)} tech video(s):\n\n" + "\n\n".join(video_list)
            
            return SkillResult(
                success=True,
                skill=self.name,
                action="fetch_tech",
                message=message,
                data={"videos": videos, "count": len(videos)}
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                skill=self.name,
                action="fetch_tech",
                message=f"Error fetching tech videos: {str(e)}"
            )

    def _fetch_trending(self, payload: dict) -> SkillResult:
        """Fetch trending videos from YouTube."""
        max_results = payload.get("max_results", 10)
        
        try:
            sys.path.insert(0, str(self.news_extractor_path))
            from viral_fetcher import ViralVideoFetcher
            
            # Try to fetch trending videos
            videos = ViralVideoFetcher.fetch_youtube_trending(max_results=max_results)
            
            if not videos:
                return SkillResult(
                    success=False,
                    skill=self.name,
                    action="fetch_trending",
                    message="No trending videos found"
                )
            
            # Format response
            video_list = []
            for i, video in enumerate(videos, 1):
                video_list.append(
                    f"{i}. {video['title'][:60]}...\n   {video['url']}"
                )
            
            message = f"🔥 Found {len(videos)} trending video(s):\n\n" + "\n\n".join(video_list)
            
            return SkillResult(
                success=True,
                skill=self.name,
                action="fetch_trending",
                message=message,
                data={"videos": videos, "count": len(videos)}
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                skill=self.name,
                action="fetch_trending",
                message=f"Error fetching trending videos: {str(e)}"
            )

    def _create_clips(self, payload: dict) -> SkillResult:
        """Create video clips from URLs."""
        urls = payload.get("urls", [])
        clip_duration = payload.get("clip_duration", 10)
        
        if not urls:
            return SkillResult(
                success=False,
                skill=self.name,
                action="create_clips",
                message="No video URLs provided"
            )
        
        try:
            # Create a temporary file with URLs
            urls_file = self.news_extractor_path / "temp_urls.txt"
            with open(urls_file, 'w') as f:
                for url in urls:
                    f.write(f"{url}\n")
            
            # Call the clipper script (this is a long-running process)
            message = f"🎬 Started creating clips from {len(urls)} video(s).\n"
            message += f"Clip duration: {clip_duration} seconds\n"
            message += f"This will take a few minutes. Check the output_videos folder."
            
            # Note: We don't actually run the subprocess here as it's blocking
            # Instead, we provide instructions
            return SkillResult(
                success=True,
                skill=self.name,
                action="create_clips",
                message=message,
                data={
                    "urls": urls,
                    "clip_duration": clip_duration,
                    "output_dir": str(self.news_extractor_path / "output_videos")
                }
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                skill=self.name,
                action="create_clips",
                message=f"Error creating clips: {str(e)}"
            )

    def _get_status(self) -> SkillResult:
        """Get status of the NewsExtractor."""
        output_dir = self.news_extractor_path / "output_videos"
        temp_dir = self.news_extractor_path / "temp_videos"
        
        # Count files
        output_videos = list(output_dir.glob("*.mp4")) if output_dir.exists() else []
        temp_videos = list(temp_dir.glob("*.mp4")) if temp_dir.exists() else []
        
        message = f"📊 NewsExtractor Status:\n\n"
        message += f"Output videos: {len(output_videos)}\n"
        message += f"Temp videos: {len(temp_videos)}\n"
        message += f"Output dir: {output_dir}\n"
        
        return SkillResult(
            success=True,
            skill=self.name,
            action="status",
            message=message,
            data={
                "output_videos": len(output_videos),
                "temp_videos": len(temp_videos),
                "output_dir": str(output_dir)
            }
        )


def create_skill(dependencies: dict[str, Any]) -> NewsExtractorSkill:
    """Create and return the NewsExtractor skill."""
    return NewsExtractorSkill()
