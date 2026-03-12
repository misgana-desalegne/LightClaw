"""
Instagram Graph API integration for posting photos, videos, and reels.
Uses Meta Developer App credentials and Instagram Business Account.
"""

import os
import json
import logging
import time
from typing import Dict, Any, Optional, List
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from pathlib import Path

from src.integrations.token_store import get_token

logger = logging.getLogger(__name__)


class InstagramProvider:
    """Instagram Graph API provider for posting content."""
    
    API_VERSION = "v18.0"
    BASE_URL = f"https://graph.facebook.com/{API_VERSION}"
    
    def __init__(self):
        self.access_token = self._resolve_access_token()
        self.instagram_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
        
    def _resolve_access_token(self) -> Optional[str]:
        """Get Instagram/Facebook access token."""
        # Try environment variable first
        token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
        if token:
            return token
            
        # Try token store
        token = get_token("FACEBOOK_PAGE_ACCESS_TOKEN")
        if token:
            return token
            
        logger.warning("No Facebook/Instagram access token found")
        return None
    
    def is_authenticated(self) -> bool:
        """Check if Instagram is authenticated."""
        return bool(self.access_token and self.instagram_account_id)
    
    def post_photo(
        self,
        photo_url: str,
        caption: str = "",
        location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Post photo to Instagram (requires publicly accessible URL).
        
        Args:
            photo_url: Publicly accessible URL to image
            caption: Photo caption (max 2200 chars)
            location_id: Optional location ID
            
        Returns:
            dict: Response with media_id
        """
        if not self.is_authenticated():
            return {"success": False, "error": "Not authenticated"}
        
        try:
            # Step 1: Create media container
            endpoint = f"{self.BASE_URL}/{self.instagram_account_id}/media"
            
            params = {
                "image_url": photo_url,
                "caption": caption[:2200],
                "access_token": self.access_token
            }
            
            if location_id:
                params["location_id"] = location_id
            
            request = Request(
                f"{endpoint}?{urlencode(params)}",
                method="POST"
            )
            
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode())
            
            creation_id = result.get("id")
            if not creation_id:
                return {"success": False, "error": "Failed to create media container"}
            
            logger.info(f"Media container created: {creation_id}")
            
            # Step 2: Publish media
            publish_endpoint = f"{self.BASE_URL}/{self.instagram_account_id}/media_publish"
            publish_params = {
                "creation_id": creation_id,
                "access_token": self.access_token
            }
            
            publish_request = Request(
                f"{publish_endpoint}?{urlencode(publish_params)}",
                method="POST"
            )
            
            with urlopen(publish_request, timeout=30) as response:
                publish_result = json.loads(response.read().decode())
            
            media_id = publish_result.get("id")
            logger.info(f"Photo published to Instagram: {media_id}")
            
            return {
                "success": True,
                "media_id": media_id,
                "url": f"https://www.instagram.com/p/{media_id}"
            }
            
        except HTTPError as e:
            error_body = e.read().decode()
            logger.error(f"Instagram API error: {error_body}")
            return {"success": False, "error": error_body}
        except Exception as e:
            logger.error(f"Error posting to Instagram: {e}")
            return {"success": False, "error": str(e)}
    
    def post_video(
        self,
        video_url: str,
        caption: str = "",
        thumb_offset: int = 0,
        location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Post video to Instagram (requires publicly accessible URL).
        
        Args:
            video_url: Publicly accessible URL to video
            caption: Video caption (max 2200 chars)
            thumb_offset: Thumbnail offset in milliseconds
            location_id: Optional location ID
            
        Returns:
            dict: Response with media_id
        """
        if not self.is_authenticated():
            return {"success": False, "error": "Not authenticated"}
        
        try:
            # Step 1: Create media container
            endpoint = f"{self.BASE_URL}/{self.instagram_account_id}/media"
            
            params = {
                "media_type": "VIDEO",
                "video_url": video_url,
                "caption": caption[:2200],
                "thumb_offset": thumb_offset,
                "access_token": self.access_token
            }
            
            if location_id:
                params["location_id"] = location_id
            
            request = Request(
                f"{endpoint}?{urlencode(params)}",
                method="POST"
            )
            
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode())
            
            creation_id = result.get("id")
            if not creation_id:
                return {"success": False, "error": "Failed to create media container"}
            
            logger.info(f"Video container created: {creation_id}")
            
            # Step 2: Check status (video processing takes time)
            status_endpoint = f"{self.BASE_URL}/{creation_id}"
            status_params = {
                "fields": "status_code",
                "access_token": self.access_token
            }
            
            max_attempts = 30
            for attempt in range(max_attempts):
                time.sleep(2)  # Wait 2 seconds between checks
                
                status_request = Request(f"{status_endpoint}?{urlencode(status_params)}")
                
                with urlopen(status_request, timeout=30) as response:
                    status_result = json.loads(response.read().decode())
                
                status_code = status_result.get("status_code")
                
                if status_code == "FINISHED":
                    logger.info("Video processing finished")
                    break
                elif status_code == "ERROR":
                    return {"success": False, "error": "Video processing failed"}
                
                logger.info(f"Video processing... ({attempt + 1}/{max_attempts})")
            
            # Step 3: Publish media
            publish_endpoint = f"{self.BASE_URL}/{self.instagram_account_id}/media_publish"
            publish_params = {
                "creation_id": creation_id,
                "access_token": self.access_token
            }
            
            publish_request = Request(
                f"{publish_endpoint}?{urlencode(publish_params)}",
                method="POST"
            )
            
            with urlopen(publish_request, timeout=30) as response:
                publish_result = json.loads(response.read().decode())
            
            media_id = publish_result.get("id")
            logger.info(f"Video published to Instagram: {media_id}")
            
            return {
                "success": True,
                "media_id": media_id,
                "url": f"https://www.instagram.com/p/{media_id}"
            }
            
        except HTTPError as e:
            error_body = e.read().decode()
            logger.error(f"Instagram video upload error: {error_body}")
            return {"success": False, "error": error_body}
        except Exception as e:
            logger.error(f"Error uploading video to Instagram: {e}")
            return {"success": False, "error": str(e)}
    
    def post_reel(
        self,
        video_url: str,
        caption: str = "",
        share_to_feed: bool = True,
        cover_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Post Instagram Reel (short video).
        
        Args:
            video_url: Publicly accessible URL to video
            caption: Reel caption (max 2200 chars)
            share_to_feed: Whether to share to main feed
            cover_url: Optional custom cover image URL
            
        Returns:
            dict: Response with media_id
        """
        if not self.is_authenticated():
            return {"success": False, "error": "Not authenticated"}
        
        try:
            # Step 1: Create reel container
            endpoint = f"{self.BASE_URL}/{self.instagram_account_id}/media"
            
            params = {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption[:2200],
                "share_to_feed": share_to_feed,
                "access_token": self.access_token
            }
            
            if cover_url:
                params["cover_url"] = cover_url
            
            request = Request(
                f"{endpoint}?{urlencode(params)}",
                method="POST"
            )
            
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode())
            
            creation_id = result.get("id")
            if not creation_id:
                return {"success": False, "error": "Failed to create reel container"}
            
            logger.info(f"Reel container created: {creation_id}")
            
            # Step 2: Check processing status
            status_endpoint = f"{self.BASE_URL}/{creation_id}"
            status_params = {
                "fields": "status_code",
                "access_token": self.access_token
            }
            
            max_attempts = 30
            for attempt in range(max_attempts):
                time.sleep(2)
                
                status_request = Request(f"{status_endpoint}?{urlencode(status_params)}")
                
                with urlopen(status_request, timeout=30) as response:
                    status_result = json.loads(response.read().decode())
                
                status_code = status_result.get("status_code")
                
                if status_code == "FINISHED":
                    break
                elif status_code == "ERROR":
                    return {"success": False, "error": "Reel processing failed"}
                
                logger.info(f"Reel processing... ({attempt + 1}/{max_attempts})")
            
            # Step 3: Publish reel
            publish_endpoint = f"{self.BASE_URL}/{self.instagram_account_id}/media_publish"
            publish_params = {
                "creation_id": creation_id,
                "access_token": self.access_token
            }
            
            publish_request = Request(
                f"{publish_endpoint}?{urlencode(publish_params)}",
                method="POST"
            )
            
            with urlopen(publish_request, timeout=30) as response:
                publish_result = json.loads(response.read().decode())
            
            media_id = publish_result.get("id")
            logger.info(f"Reel published to Instagram: {media_id}")
            
            return {
                "success": True,
                "media_id": media_id,
                "url": f"https://www.instagram.com/reel/{media_id}"
            }
            
        except HTTPError as e:
            error_body = e.read().decode()
            logger.error(f"Instagram reel upload error: {error_body}")
            return {"success": False, "error": error_body}
        except Exception as e:
            logger.error(f"Error posting reel to Instagram: {e}")
            return {"success": False, "error": str(e)}
    
    def get_media(self, limit: int = 10) -> Dict[str, Any]:
        """Get recent media from Instagram account."""
        if not self.is_authenticated():
            return {"success": False, "error": "Not authenticated"}
        
        try:
            endpoint = f"{self.BASE_URL}/{self.instagram_account_id}/media"
            params = {
                "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
                "limit": limit,
                "access_token": self.access_token
            }
            
            request = Request(f"{endpoint}?{urlencode(params)}")
            
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode())
            
            media = result.get("data", [])
            
            return {
                "success": True,
                "media": media,
                "count": len(media)
            }
            
        except Exception as e:
            logger.error(f"Error fetching Instagram media: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_media(self, media_id: str) -> Dict[str, Any]:
        """Delete Instagram media."""
        if not self.is_authenticated():
            return {"success": False, "error": "Not authenticated"}
        
        try:
            endpoint = f"{self.BASE_URL}/{media_id}"
            params = {"access_token": self.access_token}
            
            request = Request(
                f"{endpoint}?{urlencode(params)}",
                method="DELETE"
            )
            
            with urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode())
            
            return {"success": result.get("success", False)}
            
        except Exception as e:
            logger.error(f"Error deleting Instagram media: {e}")
            return {"success": False, "error": str(e)}
