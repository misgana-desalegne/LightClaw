"""
CDN/Cloud Storage uploader for making videos publicly accessible.
Supports multiple backends: Local HTTP server, S3, Cloudflare R2, etc.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import quote

logger = logging.getLogger(__name__)


class CDNUploader:
    """Upload files to CDN for public access."""
    
    def __init__(self, backend: str = "local"):
        """
        Initialize CDN uploader.
        
        Args:
            backend: Backend type ('local', 's3', 'cloudflare', etc.)
        """
        self.backend = backend
        
        if backend == "local":
            self._init_local()
        elif backend == "s3":
            self._init_s3()
        elif backend == "cloudflare":
            self._init_cloudflare()
        else:
            raise ValueError(f"Unsupported backend: {backend}")
    
    def _init_local(self):
        """Initialize local file server."""
        from src.utils.file_server import start_file_server
        
        self.port = int(os.getenv("FILE_SERVER_PORT", "8080"))
        self.directory = os.getenv("FILE_SERVER_DIR", "src/skills/NewsExtractor/shorts_from_youtube")
        
        self.server = start_file_server(self.directory, self.port)
        self.base_url = self.server.base_url
        
        logger.info(f"Using local file server: {self.base_url}")
    
    def _init_s3(self):
        """Initialize AWS S3."""
        # Requires boto3
        try:
            import boto3
            
            self.bucket = os.getenv("AWS_S3_BUCKET")
            self.region = os.getenv("AWS_REGION", "us-east-1")
            
            if not self.bucket:
                raise ValueError("AWS_S3_BUCKET not set")
            
            self.s3_client = boto3.client('s3', region_name=self.region)
            self.base_url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com"
            
            logger.info(f"Using S3: {self.base_url}")
            
        except ImportError:
            raise ImportError("boto3 required for S3 backend: pip install boto3")
    
    def _init_cloudflare(self):
        """Initialize Cloudflare R2."""
        # Requires boto3 (R2 is S3-compatible)
        try:
            import boto3
            
            self.bucket = os.getenv("CLOUDFLARE_R2_BUCKET")
            self.account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
            self.access_key = os.getenv("CLOUDFLARE_R2_ACCESS_KEY")
            self.secret_key = os.getenv("CLOUDFLARE_R2_SECRET_KEY")
            self.public_url = os.getenv("CLOUDFLARE_R2_PUBLIC_URL")  # Custom domain
            
            if not all([self.bucket, self.account_id, self.access_key, self.secret_key]):
                raise ValueError("Cloudflare R2 credentials not set")
            
            # Create S3-compatible client
            self.s3_client = boto3.client(
                's3',
                endpoint_url=f"https://{self.account_id}.r2.cloudflarestorage.com",
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name="auto"
            )
            
            self.base_url = self.public_url or f"https://{self.bucket}.{self.account_id}.r2.cloudflarestorage.com"
            
            logger.info(f"Using Cloudflare R2: {self.base_url}")
            
        except ImportError:
            raise ImportError("boto3 required for Cloudflare R2: pip install boto3")
    
    def upload(self, file_path: str, public_name: Optional[str] = None) -> str:
        """
        Upload file and return public URL.
        
        Args:
            file_path: Path to file
            public_name: Public filename (defaults to original name)
            
        Returns:
            str: Public URL
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not public_name:
            public_name = file_path.name
        
        if self.backend == "local":
            return self._upload_local(file_path, public_name)
        elif self.backend in ["s3", "cloudflare"]:
            return self._upload_s3(file_path, public_name)
    
    def _upload_local(self, file_path: Path, public_name: str) -> str:
        """Upload to local file server (just return URL)."""
        from src.utils.file_server import get_public_url
        
        # Files should already be in the directory
        # Just return the public URL
        url = get_public_url(file_path.name)
        
        if not url:
            # Fallback: construct URL manually
            url = f"{self.base_url}/{quote(public_name)}"
        
        logger.info(f"Local URL: {url}")
        return url
    
    def _upload_s3(self, file_path: Path, public_name: str) -> str:
        """Upload to S3 or S3-compatible storage."""
        try:
            # Upload file
            with open(file_path, 'rb') as f:
                self.s3_client.upload_fileobj(
                    f,
                    self.bucket,
                    public_name,
                    ExtraArgs={'ACL': 'public-read', 'ContentType': 'video/mp4'}
                )
            
            # Construct public URL
            url = f"{self.base_url}/{quote(public_name)}"
            
            logger.info(f"Uploaded to CDN: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise
    
    def delete(self, public_name: str):
        """Delete file from CDN."""
        if self.backend == "local":
            # Can't delete from local server
            logger.warning("Delete not supported for local backend")
            return
        
        elif self.backend in ["s3", "cloudflare"]:
            try:
                self.s3_client.delete_object(Bucket=self.bucket, Key=public_name)
                logger.info(f"Deleted from CDN: {public_name}")
            except Exception as e:
                logger.error(f"Delete failed: {e}")


# Global uploader instance
_global_uploader: Optional[CDNUploader] = None


def get_uploader(backend: Optional[str] = None) -> CDNUploader:
    """
    Get or create global CDN uploader.
    
    Args:
        backend: Backend type (defaults to env var or 'local')
    """
    global _global_uploader
    
    if not backend:
        backend = os.getenv("CDN_BACKEND", "local")
    
    if not _global_uploader or _global_uploader.backend != backend:
        _global_uploader = CDNUploader(backend)
    
    return _global_uploader


def upload_for_instagram(file_path: str) -> str:
    """
    Upload file for Instagram (requires public URL).
    
    Args:
        file_path: Path to video file
        
    Returns:
        str: Public URL
    """
    uploader = get_uploader()
    return uploader.upload(file_path)


# Example usage:
if __name__ == "__main__":
    # Test local backend
    print("Testing local backend...")
    uploader = CDNUploader("local")
    
    # Create test file
    test_file = Path("test_video.mp4")
    test_file.write_text("test")
    
    try:
        url = uploader.upload(str(test_file))
        print(f"Public URL: {url}")
    finally:
        test_file.unlink()
