from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.agent.context import Context
from src.integrations.youtube import YouTubeProvider
from src.models.schemas import SkillResult


class YouTubeUploadSkill:
    name = "youtube_upload"
    version = "1.0.0"
    description = "Upload videos to YouTube, manage uploads, and update video metadata."
    actions = [
        "upload",
        "upload_clip",
        "list_uploads",
        "delete_video",
        "update_video",
        "quota_info",
        "check_auth"
    ]
    required_env = ["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"]

    def __init__(self, provider: YouTubeProvider) -> None:
        self.provider = provider

    def can_handle(self, intent: str) -> bool:
        """Check if this skill can handle the intent."""
        keywords = ["upload", "youtube", "video", "publish"]
        return any(keyword in intent.lower() for keyword in keywords)

    def execute(self, action: str, payload: dict, context: Context) -> SkillResult:
        """Execute the requested action."""
        if action == "upload":
            return self._upload_video(payload)
        if action == "upload_clip":
            return self._upload_clip(payload)
        if action == "list_uploads":
            return self._list_uploads(payload)
        if action == "delete_video":
            return self._delete_video(payload)
        if action == "update_video":
            return self._update_video(payload)
        if action == "quota_info":
            return self._quota_info()
        if action == "check_auth":
            return self._check_auth()
        
        return SkillResult(
            success=False,
            skill=self.name,
            action=action,
            message="Unsupported action"
        )

    def _check_auth(self) -> SkillResult:
        """Check if YouTube is authenticated."""
        is_auth = self.provider.is_authenticated()
        
        if is_auth:
            message = "✅ YouTube is authenticated and ready to upload!"
        else:
            message = (
                "❌ YouTube not authenticated.\n\n"
                "To upload videos, you need to:\n"
                "1. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET env vars\n"
                "2. Authenticate via /admin interface\n"
                "3. Grant YouTube upload permissions"
            )
        
        return SkillResult(
            success=is_auth,
            skill=self.name,
            action="check_auth",
            message=message,
            data={"authenticated": is_auth}
        )

    def _upload_video(self, payload: dict) -> SkillResult:
        """Upload a video to YouTube."""
        video_path = payload.get("video_path")
        title = payload.get("title", "Uploaded Video")
        description = payload.get("description", "")
        tags = payload.get("tags", [])
        privacy = payload.get("privacy", "private")  # private, unlisted, public
        category_id = payload.get("category_id", "22")  # 22 = People & Blogs
        made_for_kids = payload.get("made_for_kids", False)
        
        if not video_path:
            return SkillResult(
                success=False,
                skill=self.name,
                action="upload",
                message="❌ No video path provided. Please specify 'video_path' in payload."
            )
        
        video_path = Path(video_path)
        if not video_path.exists():
            return SkillResult(
                success=False,
                skill=self.name,
                action="upload",
                message=f"❌ Video file not found: {video_path}"
            )
        
        if not self.provider.is_authenticated():
            return SkillResult(
                success=False,
                skill=self.name,
                action="upload",
                message="❌ YouTube not authenticated. Please authenticate via /admin"
            )
        
        try:
            # Get file size
            file_size_mb = video_path.stat().st_size / (1024 * 1024)
            
            print(f"📤 Uploading video to YouTube...")
            print(f"   File: {video_path.name}")
            print(f"   Size: {file_size_mb:.1f} MB")
            print(f"   Title: {title}")
            print(f"   Privacy: {privacy}")
            
            result = self.provider.upload_video(
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                category_id=category_id,
                privacy_status=privacy,
                made_for_kids=made_for_kids,
            )
            
            if result:
                message = (
                    f"✅ Video uploaded successfully!\n\n"
                    f"📹 Title: {result['title']}\n"
                    f"🔗 URL: {result['url']}\n"
                    f"🔒 Privacy: {result['privacy_status']}\n"
                    f"📊 Size: {file_size_mb:.1f} MB\n\n"
                    f"Video ID: {result['id']}"
                )
                
                return SkillResult(
                    success=True,
                    skill=self.name,
                    action="upload",
                    message=message,
                    data=result
                )
            else:
                return SkillResult(
                    success=False,
                    skill=self.name,
                    action="upload",
                    message="❌ Upload failed - no result returned"
                )
        
        except Exception as e:
            return SkillResult(
                success=False,
                skill=self.name,
                action="upload",
                message=f"❌ Upload failed: {str(e)}"
            )

    def _upload_clip(self, payload: dict) -> SkillResult:
        """Upload a video clip from the news_extractor output directory."""
        clip_name = payload.get("clip_name")
        clip_index = payload.get("clip_index")
        title = payload.get("title")
        description = payload.get("description", "")
        tags = payload.get("tags", ["shorts", "viral", "clips"])
        privacy = payload.get("privacy", "private")
        
        # Look for clip in news_extractor output directories
        possible_dirs = [
            Path(__file__).parent.parent / "NewsExtractor" / "output_videos",
            Path(__file__).parent.parent / "NewsExtractor" / "shorts_from_youtube",
        ]
        
        video_path = None
        
        # Find by clip name
        if clip_name:
            for dir_path in possible_dirs:
                if dir_path.exists():
                    clip_path = dir_path / clip_name
                    if clip_path.exists():
                        video_path = clip_path
                        break
        
        # Find by index
        elif clip_index is not None:
            for dir_path in possible_dirs:
                if dir_path.exists():
                    clips = sorted([f for f in dir_path.glob("*.mp4")])
                    if 0 <= clip_index < len(clips):
                        video_path = clips[clip_index]
                        break
        
        if not video_path:
            # List available clips
            available_clips = []
            for dir_path in possible_dirs:
                if dir_path.exists():
                    clips = list(dir_path.glob("*.mp4"))
                    available_clips.extend([(c.name, str(c)) for c in clips])
            
            clips_list = "\n".join([f"  {i}. {name}" for i, (name, _) in enumerate(available_clips)])
            
            return SkillResult(
                success=False,
                skill=self.name,
                action="upload_clip",
                message=(
                    f"❌ Clip not found.\n\n"
                    f"Available clips:\n{clips_list}\n\n"
                    f"Use 'clip_name' or 'clip_index' to specify which clip to upload."
                )
            )
        
        # Auto-generate title if not provided
        if not title:
            title = f"Viral Clip - {video_path.stem}"
        
        # Upload using the main upload method
        return self._upload_video({
            "video_path": str(video_path),
            "title": title,
            "description": description,
            "tags": tags,
            "privacy": privacy,
            "category_id": "22",  # People & Blogs
        })

    def _list_uploads(self, payload: dict) -> SkillResult:
        """List recent video uploads."""
        max_results = payload.get("max_results", 10)
        
        if not self.provider.is_authenticated():
            return SkillResult(
                success=False,
                skill=self.name,
                action="list_uploads",
                message="❌ YouTube not authenticated. Please authenticate via /admin"
            )
        
        try:
            videos = self.provider.list_my_videos(max_results=max_results)
            
            if not videos:
                return SkillResult(
                    success=True,
                    skill=self.name,
                    action="list_uploads",
                    message="📹 No videos found on your channel.",
                    data={"videos": []}
                )
            
            video_list = []
            for i, video in enumerate(videos, 1):
                video_list.append(
                    f"{i}. {video['title']}\n"
                    f"   🔗 {video['url']}\n"
                    f"   📅 {video['published_at'][:10]}\n"
                    f"   ID: {video['id']}"
                )
            
            message = f"📹 Your recent uploads ({len(videos)}):\n\n" + "\n\n".join(video_list)
            
            return SkillResult(
                success=True,
                skill=self.name,
                action="list_uploads",
                message=message,
                data={"videos": videos, "count": len(videos)}
            )
        
        except Exception as e:
            return SkillResult(
                success=False,
                skill=self.name,
                action="list_uploads",
                message=f"❌ Failed to list uploads: {str(e)}"
            )

    def _delete_video(self, payload: dict) -> SkillResult:
        """Delete a video from YouTube."""
        video_id = payload.get("video_id")
        
        if not video_id:
            return SkillResult(
                success=False,
                skill=self.name,
                action="delete_video",
                message="❌ No video_id provided"
            )
        
        if not self.provider.is_authenticated():
            return SkillResult(
                success=False,
                skill=self.name,
                action="delete_video",
                message="❌ YouTube not authenticated. Please authenticate via /admin"
            )
        
        try:
            success = self.provider.delete_video(video_id)
            
            if success:
                return SkillResult(
                    success=True,
                    skill=self.name,
                    action="delete_video",
                    message=f"✅ Video {video_id} deleted successfully"
                )
            else:
                return SkillResult(
                    success=False,
                    skill=self.name,
                    action="delete_video",
                    message=f"❌ Failed to delete video {video_id}"
                )
        
        except Exception as e:
            return SkillResult(
                success=False,
                skill=self.name,
                action="delete_video",
                message=f"❌ Error deleting video: {str(e)}"
            )

    def _update_video(self, payload: dict) -> SkillResult:
        """Update video metadata."""
        video_id = payload.get("video_id")
        title = payload.get("title")
        description = payload.get("description")
        tags = payload.get("tags")
        privacy = payload.get("privacy")
        
        if not video_id:
            return SkillResult(
                success=False,
                skill=self.name,
                action="update_video",
                message="❌ No video_id provided"
            )
        
        if not self.provider.is_authenticated():
            return SkillResult(
                success=False,
                skill=self.name,
                action="update_video",
                message="❌ YouTube not authenticated. Please authenticate via /admin"
            )
        
        try:
            result = self.provider.update_video_metadata(
                video_id=video_id,
                title=title,
                description=description,
                tags=tags,
                privacy_status=privacy,
            )
            
            if result:
                message = (
                    f"✅ Video updated successfully!\n\n"
                    f"📹 Title: {result['title']}\n"
                    f"🔗 URL: {result['url']}\n"
                    f"🔒 Privacy: {result['privacy_status']}"
                )
                
                return SkillResult(
                    success=True,
                    skill=self.name,
                    action="update_video",
                    message=message,
                    data=result
                )
            else:
                return SkillResult(
                    success=False,
                    skill=self.name,
                    action="update_video",
                    message=f"❌ Failed to update video {video_id}"
                )
        
        except Exception as e:
            return SkillResult(
                success=False,
                skill=self.name,
                action="update_video",
                message=f"❌ Error updating video: {str(e)}"
            )

    def _quota_info(self) -> SkillResult:
        """Get information about YouTube upload quotas."""
        try:
            quota = self.provider.get_upload_quota()
            
            message = (
                "📊 YouTube Upload Quota Information:\n\n"
                f"📤 Daily uploads: {quota['daily_upload_limit']} videos\n"
                f"📦 Max file size: {quota['video_size_limit_mb'] / 1000:.0f} GB\n"
                f"⏱️  Max video length: {quota['video_length_limit_hours']} hours\n\n"
                f"ℹ️  {quota['note']}"
            )
            
            return SkillResult(
                success=True,
                skill=self.name,
                action="quota_info",
                message=message,
                data=quota
            )
        
        except Exception as e:
            return SkillResult(
                success=False,
                skill=self.name,
                action="quota_info",
                message=f"❌ Error getting quota info: {str(e)}"
            )


def create_skill(dependencies: dict[str, Any]) -> YouTubeUploadSkill:
    """Create and return the YouTube upload skill."""
    youtube_provider = dependencies.get("youtube_provider")
    
    if not youtube_provider:
        # Create a new provider instance
        youtube_provider = YouTubeProvider()
    
    return YouTubeUploadSkill(youtube_provider)
