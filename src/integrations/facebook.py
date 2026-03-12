"""
Facebook Graph API integration for posting videos, photos, and text.
Uses Meta Developer App credentials and Page Access Token.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from pathlib import Path

from src.integrations.token_store import get_token, upsert_tokens

logger = logging.getLogger(__name__)


class FacebookProvider:
    """Facebook Graph API provider for posting content."""
    
    API_VERSION = "v18.0"
    BASE_URL = f"https://graph.facebook.com/{API_VERSION}"
    
    def __init__(self):
        self.access_token = self._resolve_access_token()
        self.page_id = os.getenv("FACEBOOK_PAGE_ID")
        self.app_id = os.getenv("FACEBOOK_APP_ID")
        self.app_secret = os.getenv("FACEBOOK_APP_SECRET")
        
    def _resolve_access_token(self) -> Optional[str]:
        """Get Facebook Page Access Token."""
        # Try environment variable first
        token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
        if token:
            return token
            
        # Try token store
        token = get_token("FACEBOOK_PAGE_ACCESS_TOKEN")
        if token:
            return token
            
        logger.warning("No Facebook Page Access Token found")
        return None
    
    def is_authenticated(self) -> bool:
        """Check if Facebook is authenticated."""
        return bool(self.access_token and self.page_id)
    
    def post_text(
        self,
        message: str,
        link: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Post text message to Facebook Page.
        
        Args:
            message: Text content
            link: Optional URL to share
            
        Returns:
            dict: Response with post_id
        """
        if not self.is_authenticated():
            return {"success": False, "error": "Not authenticated"}
        
        try:
            endpoint = f"{self.BASE_URL}/{self.page_id}/feed"
            
            data = {
                "message": message,
                "access_token": self.access_token
            }
            
            if link:
                data["link"] = link
            
            request = Request(
                endpoint,
                data=urlencode(data).encode(),
                method="POST"
            )
            
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode())
            
            post_id = result.get("id")
            logger.info(f"Posted to Facebook: {post_id}")
            
            return {
                "success": True,
                "post_id": post_id,
                "url": f"https://facebook.com/{post_id}"
            }
            
        except HTTPError as e:
            error_body = e.read().decode()
            logger.error(f"Facebook API error: {error_body}")
            return {"success": False, "error": error_body}
        except Exception as e:
            logger.error(f"Error posting to Facebook: {e}")
            return {"success": False, "error": str(e)}
    
    def post_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        published: bool = True
    ) -> Dict[str, Any]:
        """
        Upload video to Facebook Page (resumable upload for large files).
        
        Args:
            video_path: Path to video file
            title: Video title
            description: Video description
            tags: List of tags/hashtags
            published: Whether to publish immediately
            
        Returns:
            dict: Response with video_id
        """
        if not self.is_authenticated():
            return {"success": False, "error": "Not authenticated"}
        
        video_path = Path(video_path)
        if not video_path.exists():
            return {"success": False, "error": f"Video not found: {video_path}"}
        
        try:
            file_size = video_path.stat().st_size
            
            # Prepare description with hashtags
            full_description = description
            if tags:
                hashtags = " ".join([f"#{tag.replace(' ', '')}" for tag in tags])
                full_description = f"{description}\n\n{hashtags}" if description else hashtags
            
            # Step 1: Initialize upload session
            init_endpoint = f"{self.BASE_URL}/{self.page_id}/videos"
            init_params = {
                "upload_phase": "start",
                "file_size": file_size,
                "access_token": self.access_token
            }
            
            init_request = Request(
                f"{init_endpoint}?{urlencode(init_params)}",
                method="POST"
            )
            
            with urlopen(init_request, timeout=30) as response:
                init_result = json.loads(response.read().decode())
            
            upload_session_id = init_result.get("upload_session_id")
            if not upload_session_id:
                return {"success": False, "error": "Failed to initialize upload"}
            
            logger.info(f"Upload session started: {upload_session_id}")
            
            # Step 2: Upload video data
            with open(video_path, 'rb') as video_file:
                video_data = video_file.read()
            
            upload_params = {
                "upload_phase": "transfer",
                "upload_session_id": upload_session_id,
                "start_offset": 0,
                "access_token": self.access_token
            }
            
            upload_request = Request(
                f"{init_endpoint}?{urlencode(upload_params)}",
                data=video_data,
                method="POST"
            )
            upload_request.add_header('Content-Type', 'application/octet-stream')
            
            with urlopen(upload_request, timeout=300) as response:
                upload_result = json.loads(response.read().decode())
            
            logger.info("Video data uploaded")
            
            # Step 3: Finish upload and publish
            finish_params = {
                "upload_phase": "finish",
                "upload_session_id": upload_session_id,
                "title": title,
                "description": full_description,
                "published": "true" if published else "false",
                "access_token": self.access_token
            }
            
            finish_request = Request(
                f"{init_endpoint}?{urlencode(finish_params)}",
                method="POST"
            )
            
            with urlopen(finish_request, timeout=30) as response:
                finish_result = json.loads(response.read().decode())
            
            video_id = finish_result.get("id")
            logger.info(f"Video published to Facebook: {video_id}")
            
            return {
                "success": True,
                "video_id": video_id,
                "post_id": finish_result.get("post_id"),
                "url": f"https://facebook.com/{video_id}"
            }
            
        except HTTPError as e:
            error_body = e.read().decode()
            logger.error(f"Facebook video upload error: {error_body}")
            return {"success": False, "error": error_body}
        except Exception as e:
            logger.error(f"Error uploading video to Facebook: {e}")
            return {"success": False, "error": str(e)}
    
    def post_photo(
        self,
        photo_path: str,
        caption: str = ""
    ) -> Dict[str, Any]:
        """
        Post photo to Facebook Page.
        
        Args:
            photo_path: Path to image file
            caption: Photo caption
            
        Returns:
            dict: Response with post_id
        """
        if not self.is_authenticated():
            return {"success": False, "error": "Not authenticated"}
        
        photo_path = Path(photo_path)
        if not photo_path.exists():
            return {"success": False, "error": f"Photo not found: {photo_path}"}
        
        try:
            endpoint = f"{self.BASE_URL}/{self.page_id}/photos"
            
            with open(photo_path, 'rb') as photo_file:
                photo_data = photo_file.read()
            
            # Create multipart form data
            boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
            
            body_parts = []
            body_parts.append(f"--{boundary}".encode())
            body_parts.append(b'Content-Disposition: form-data; name="message"\r\n')
            body_parts.append(caption.encode())
            
            body_parts.append(f"\r\n--{boundary}".encode())
            body_parts.append(b'Content-Disposition: form-data; name="source"; filename="photo.jpg"\r\n')
            body_parts.append(b'Content-Type: image/jpeg\r\n')
            body_parts.append(photo_data)
            
            body_parts.append(f"\r\n--{boundary}".encode())
            body_parts.append(b'Content-Disposition: form-data; name="access_token"\r\n')
            body_parts.append(self.access_token.encode())
            
            body_parts.append(f"\r\n--{boundary}--".encode())
            
            body = b"\r\n".join(body_parts)
            
            request = Request(endpoint, data=body, method="POST")
            request.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
            
            with urlopen(request, timeout=60) as response:
                result = json.loads(response.read().decode())
            
            post_id = result.get("id")
            logger.info(f"Photo posted to Facebook: {post_id}")
            
            return {
                "success": True,
                "post_id": post_id,
                "url": f"https://facebook.com/{post_id}"
            }
            
        except HTTPError as e:
            error_body = e.read().decode()
            logger.error(f"Facebook photo upload error: {error_body}")
            return {"success": False, "error": error_body}
        except Exception as e:
            logger.error(f"Error posting photo to Facebook: {e}")
            return {"success": False, "error": str(e)}
    
    def get_page_posts(self, limit: int = 10) -> Dict[str, Any]:
        """Get recent posts from page."""
        if not self.is_authenticated():
            return {"success": False, "error": "Not authenticated"}
        
        try:
            endpoint = f"{self.BASE_URL}/{self.page_id}/posts"
            params = {
                "fields": "id,message,created_time,likes.summary(true),comments.summary(true)",
                "limit": limit,
                "access_token": self.access_token
            }
            
            request = Request(f"{endpoint}?{urlencode(params)}")
            
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode())
            
            posts = result.get("data", [])
            
            return {
                "success": True,
                "posts": posts,
                "count": len(posts)
            }
            
        except Exception as e:
            logger.error(f"Error fetching Facebook posts: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_post(self, post_id: str) -> Dict[str, Any]:
        """Delete a post."""
        if not self.is_authenticated():
            return {"success": False, "error": "Not authenticated"}
        
        try:
            endpoint = f"{self.BASE_URL}/{post_id}"
            params = {"access_token": self.access_token}
            
            request = Request(
                f"{endpoint}?{urlencode(params)}",
                method="DELETE"
            )
            
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode())
            
            return {"success": result.get("success", False)}
            
        except Exception as e:
            logger.error(f"Error deleting Facebook post: {e}")
            return {"success": False, "error": str(e)}
