"""
Simple file server utility for serving videos publicly.
Used for Instagram uploads which require public URLs.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

logger = logging.getLogger(__name__)


class FileServer:
    """Simple HTTP file server for serving videos."""
    
    def __init__(self, directory: str, port: int = 8080):
        """
        Initialize file server.
        
        Args:
            directory: Directory to serve files from
            port: Port to run server on
        """
        self.directory = Path(directory)
        self.port = port
        self.server = None
        self.thread = None
        self.base_url = f"http://localhost:{port}"
        
    def start(self):
        """Start the file server in a background thread."""
        if self.server:
            logger.warning("Server already running")
            return
        
        # Change to directory
        os.chdir(self.directory)
        
        # Create server
        handler = SimpleHTTPRequestHandler
        self.server = HTTPServer(("", self.port), handler)
        
        # Run in background thread
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        
        logger.info(f"File server started at {self.base_url}")
    
    def stop(self):
        """Stop the file server."""
        if self.server:
            self.server.shutdown()
            self.server = None
            self.thread = None
            logger.info("File server stopped")
    
    def get_public_url(self, file_path: str) -> str:
        """
        Get public URL for a file.
        
        Args:
            file_path: Path to file (relative or absolute)
            
        Returns:
            str: Public URL
        """
        file_path = Path(file_path)
        
        # Get relative path from directory
        if file_path.is_absolute():
            relative_path = file_path.relative_to(self.directory)
        else:
            relative_path = file_path
        
        # Convert to URL
        url_path = str(relative_path).replace(os.sep, "/")
        return f"{self.base_url}/{url_path}"


# Global file server instance
_global_server: Optional[FileServer] = None


def start_file_server(directory: str = "src/skills/NewsExtractor/shorts_from_youtube", port: int = 8080):
    """
    Start global file server.
    
    Args:
        directory: Directory to serve
        port: Port to use
    """
    global _global_server
    
    if _global_server:
        return _global_server
    
    _global_server = FileServer(directory, port)
    _global_server.start()
    return _global_server


def stop_file_server():
    """Stop global file server."""
    global _global_server
    
    if _global_server:
        _global_server.stop()
        _global_server = None


def get_public_url(file_path: str) -> Optional[str]:
    """
    Get public URL for a file using global server.
    
    Args:
        file_path: Path to file
        
    Returns:
        str: Public URL or None if server not running
    """
    global _global_server
    
    if not _global_server:
        logger.warning("File server not running")
        return None
    
    return _global_server.get_public_url(file_path)


# Example usage:
if __name__ == "__main__":
    # Start server
    server = start_file_server(".", port=8080)
    
    print(f"File server running at http://localhost:8080")
    print("Press Ctrl+C to stop")
    
    try:
        # Keep running
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_file_server()
        print("\nServer stopped")
