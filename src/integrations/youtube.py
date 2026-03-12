from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pathlib import Path
from typing import Any

from src.integrations.token_store import get_token, upsert_tokens


class YouTubeProvider:
    """Provider for YouTube Data API v3 operations."""
    
    API_BASE = "https://www.googleapis.com/youtube/v3"
    UPLOAD_API = "https://www.googleapis.com/upload/youtube/v3/videos"
    
    def __init__(self) -> None:
        self._access_token = self._resolve_access_token()
        self._client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        self._client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
        self._use_youtube_api = bool(self._access_token)
    
    def _resolve_access_token(self) -> str | None:
        """Get access token, refreshing if necessary."""
        refresh_token = os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN") or get_token("GOOGLE_OAUTH_REFRESH_TOKEN")
        
        if refresh_token:
            client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
            
            if client_id and client_secret:
                from urllib.parse import urlencode
                
                refresh_payload = urlencode({
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }).encode("utf-8")
                
                request = Request(
                    "https://oauth2.googleapis.com/token",
                    data=refresh_payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    method="POST",
                )
                
                try:
                    with urlopen(request, timeout=5) as response:
                        token_response = json.loads(response.read().decode("utf-8"))
                    refreshed_access_token = token_response.get("access_token")
                    if refreshed_access_token:
                        # Update the token in the store
                        upsert_tokens({"GOOGLE_OAUTH_ACCESS_TOKEN": refreshed_access_token})
                        print(f"✅ Token refreshed successfully")
                        return refreshed_access_token
                except Exception as e:
                    print(f"⚠️  Token refresh failed: {type(e).__name__}, using stored token")
                    pass
        
        # Fallback to stored token
        return get_token("GOOGLE_OAUTH_ACCESS_TOKEN")
    
    def is_authenticated(self) -> bool:
        """Check if user has authenticated with YouTube/Google."""
        return self._use_youtube_api
    
    def upload_video(
        self,
        video_path: str | Path,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        category_id: str = "22",  # 22 = People & Blogs
        privacy_status: str = "private",  # private, unlisted, public
        made_for_kids: bool = False,
    ) -> dict[str, Any] | None:
        """
        Upload a video to YouTube.
        
        Args:
            video_path: Path to the video file
            title: Video title (max 100 chars)
            description: Video description (max 5000 chars)
            tags: List of tags (max 500 chars total)
            category_id: YouTube category ID (default: 22 = People & Blogs)
            privacy_status: 'private', 'unlisted', or 'public'
            made_for_kids: Whether the video is made for kids (COPPA)
        
        Returns:
            Dict with video info (id, title, url) or None on failure
        """
        if not self._use_youtube_api:
            raise ValueError("YouTube API not authenticated. Please authenticate via /admin")
        
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # Prepare metadata
        metadata = {
            "snippet": {
                "title": title[:100],  # Max 100 chars
                "description": description[:5000],  # Max 5000 chars
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": made_for_kids,
            }
        }
        
        try:
            # Read video file
            with open(video_path, 'rb') as video_file:
                video_data = video_file.read()
            
            # Create multipart request
            boundary = "===============7330845974216740156=="
            
            # Build multipart body
            body_parts = []
            
            # Part 1: JSON metadata
            body_parts.append(f"--{boundary}".encode())
            body_parts.append(b"Content-Type: application/json; charset=UTF-8\r\n")
            body_parts.append(json.dumps(metadata).encode())
            
            # Part 2: Video file
            body_parts.append(f"\r\n--{boundary}".encode())
            body_parts.append(b"Content-Type: video/*\r\n")
            body_parts.append(video_data)
            
            # End boundary
            body_parts.append(f"\r\n--{boundary}--".encode())
            
            body = b"\r\n".join(body_parts)
            
            # Upload request
            url = f"{self.UPLOAD_API}?uploadType=multipart&part=snippet,status"
            
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": f"multipart/related; boundary={boundary}",
                "Content-Length": str(len(body)),
            }
            
            request = Request(url, data=body, headers=headers, method="POST")
            
            with urlopen(request, timeout=600) as response:  # 10 min timeout
                result = json.loads(response.read().decode())
                
                video_id = result.get("id")
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                return {
                    "id": video_id,
                    "title": result.get("snippet", {}).get("title"),
                    "url": video_url,
                    "privacy_status": result.get("status", {}).get("privacyStatus"),
                    "channel_id": result.get("snippet", {}).get("channelId"),
                }
        
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            raise Exception(f"YouTube API error: {e.code} - {error_body}")
        except URLError as e:
            raise Exception(f"Network error uploading to YouTube: {e.reason}")
        except Exception as e:
            raise Exception(f"Failed to upload video: {str(e)}")
    
    def get_upload_quota(self) -> dict[str, Any] | None:
        """Get information about upload quota (requires YouTube Analytics API)."""
        # Note: This requires YouTube Analytics API which has different quotas
        # For basic info, we just return static quota info
        return {
            "daily_upload_limit": 6,  # Default YouTube limit for new channels
            "video_size_limit_mb": 256000,  # 256 GB for verified accounts
            "video_length_limit_hours": 12,  # 12 hours for verified accounts
            "note": "Limits may vary based on account verification status"
        }
    
    def list_my_videos(self, max_results: int = 10) -> list[dict[str, Any]]:
        """List videos from authenticated user's channel."""
        if not self._use_youtube_api:
            return []
        
        try:
            # First, get the user's channel
            url = f"{self.API_BASE}/channels?part=contentDetails&mine=true"
            headers = {"Authorization": f"Bearer {self._access_token}"}
            
            request = Request(url, headers=headers)
            with urlopen(request, timeout=30) as response:
                channel_data = json.loads(response.read().decode())
            
            if not channel_data.get("items"):
                return []
            
            # Get uploads playlist ID
            uploads_playlist_id = (
                channel_data["items"][0]
                .get("contentDetails", {})
                .get("relatedPlaylists", {})
                .get("uploads")
            )
            
            if not uploads_playlist_id:
                return []
            
            # Get videos from uploads playlist
            url = f"{self.API_BASE}/playlistItems?part=snippet&playlistId={uploads_playlist_id}&maxResults={max_results}"
            
            request = Request(url, headers=headers)
            with urlopen(request, timeout=30) as response:
                playlist_data = json.loads(response.read().decode())
            
            videos = []
            for item in playlist_data.get("items", []):
                snippet = item.get("snippet", {})
                video_id = snippet.get("resourceId", {}).get("videoId")
                
                videos.append({
                    "id": video_id,
                    "title": snippet.get("title"),
                    "description": snippet.get("description", "")[:100],
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "published_at": snippet.get("publishedAt"),
                })
            
            return videos
        
        except Exception as e:
            print(f"Error listing videos: {e}")
            return []
    
    def delete_video(self, video_id: str) -> bool:
        """Delete a video from YouTube."""
        if not self._use_youtube_api:
            return False
        
        try:
            url = f"{self.API_BASE}/videos?id={video_id}"
            headers = {"Authorization": f"Bearer {self._access_token}"}
            
            request = Request(url, headers=headers, method="DELETE")
            with urlopen(request, timeout=30) as response:
                return response.status == 204
        
        except Exception as e:
            print(f"Error deleting video: {e}")
            return False
    
    def update_video_metadata(
        self,
        video_id: str,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        privacy_status: str | None = None,
    ) -> dict[str, Any] | None:
        """Update video metadata."""
        if not self._use_youtube_api:
            return None
        
        try:
            # First get current video data
            url = f"{self.API_BASE}/videos?part=snippet,status&id={video_id}"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }
            
            request = Request(url, headers=headers)
            with urlopen(request, timeout=30) as response:
                video_data = json.loads(response.read().decode())
            
            if not video_data.get("items"):
                return None
            
            video = video_data["items"][0]
            
            # Update fields
            if title:
                video["snippet"]["title"] = title[:100]
            if description is not None:
                video["snippet"]["description"] = description[:5000]
            if tags is not None:
                video["snippet"]["tags"] = tags
            if privacy_status:
                video["status"]["privacyStatus"] = privacy_status
            
            # Update video
            url = f"{self.API_BASE}/videos?part=snippet,status"
            body = json.dumps(video).encode()
            
            request = Request(url, data=body, headers=headers, method="PUT")
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode())
                
                video_id = result.get("id")
                return {
                    "id": video_id,
                    "title": result.get("snippet", {}).get("title"),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "privacy_status": result.get("status", {}).get("privacyStatus"),
                }
        
        except Exception as e:
            print(f"Error updating video: {e}")
            return None
