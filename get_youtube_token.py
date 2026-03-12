#!/usr/bin/env python3
"""
Standalone OAuth script to get YouTube upload token.
This script will help you authenticate and get tokens with YouTube scope.
"""

import os
import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse
from urllib.request import Request, urlopen
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration - read from .env
CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip('"')
CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip('"')
REDIRECT_URI = "http://localhost:8080/oauth2callback"

# Scopes needed
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar"
]

# Global variable to store the authorization code
auth_code = None


class OAuthHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback."""
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def do_GET(self):
        """Handle GET request from OAuth callback."""
        global auth_code
        
        # Parse query parameters
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        if 'code' in params:
            auth_code = params['code'][0]
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = """
            <html>
            <head><title>Authentication Successful</title></head>
            <body style="font-family: Arial; padding: 50px; text-align: center;">
                <h1 style="color: green;">✅ Authentication Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                <p style="color: #666; font-size: 14px;">The authorization code has been received.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        else:
            # Error case
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            error = params.get('error', ['Unknown error'])[0]
            html = f"""
            <html>
            <head><title>Authentication Failed</title></head>
            <body style="font-family: Arial; padding: 50px; text-align: center;">
                <h1 style="color: red;">❌ Authentication Failed</h1>
                <p>Error: {error}</p>
                <p>Please close this window and try again.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode())


def exchange_code_for_tokens(code):
    """Exchange authorization code for access and refresh tokens."""
    print("\n🔄 Exchanging authorization code for tokens...")
    
    token_url = "https://oauth2.googleapis.com/token"
    
    data = urlencode({
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }).encode()
    
    request = Request(token_url, data=data, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    
    try:
        with urlopen(request, timeout=30) as response:
            token_data = json.loads(response.read().decode())
        
        return token_data
    except Exception as e:
        print(f"❌ Error exchanging code: {e}")
        return None


def save_tokens(token_data):
    """Save tokens to .runtime_tokens.json."""
    token_file = Path(".runtime_tokens.json")
    
    # Load existing tokens
    if token_file.exists():
        with open(token_file, 'r') as f:
            existing_tokens = json.load(f)
    else:
        existing_tokens = {}
    
    # Update with new tokens
    existing_tokens.update({
        "GOOGLE_OAUTH_ACCESS_TOKEN": token_data.get("access_token"),
        "GOOGLE_OAUTH_REFRESH_TOKEN": token_data.get("refresh_token"),
        "GOOGLE_OAUTH_TOKEN_TYPE": token_data.get("token_type"),
        "GOOGLE_OAUTH_EXPIRES_IN": token_data.get("expires_in"),
    })
    
    # Save back
    with open(token_file, 'w') as f:
        json.dump(existing_tokens, f, indent=2)
    
    print(f"✅ Tokens saved to {token_file}")


def main():
    print("=" * 70)
    print("YOUTUBE OAUTH - GET TOKEN WITH UPLOAD SCOPE")
    print("=" * 70)
    print()
    print("This script will:")
    print("  1. Open your browser to Google OAuth")
    print("  2. Ask you to grant YouTube upload permissions")
    print("  3. Save the tokens to .runtime_tokens.json")
    print()
    print(f"📋 Client ID: {CLIENT_ID[:40]}...")
    print(f"🔗 Redirect URI: {REDIRECT_URI}")
    print(f"🔐 Scopes: {len(SCOPES)} scopes (YouTube + Gmail + Calendar)")
    print()
    
    # Build authorization URL
    auth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "response_type": "code",
        "access_type": "offline",  # Get refresh token
        "prompt": "consent"  # Force consent screen to get refresh token
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(auth_params)}"
    
    print("🌐 Starting local server on port 8080...")
    print()
    
    # Start local server
    server = HTTPServer(('localhost', 8080), OAuthHandler)
    
    print("✅ Server started!")
    print()
    print("=" * 70)
    print("IMPORTANT: In the next step...")
    print("=" * 70)
    print("When Google asks for permissions, make sure to:")
    print("  ✅ Grant YouTube upload access")
    print("  ✅ Grant YouTube view access")
    print("  ✅ Grant Gmail access (if needed)")
    print("  ✅ Grant Calendar access (if needed)")
    print()
    input("Press Enter to open your browser and start OAuth flow...")
    
    # Open browser
    print(f"\n🌐 Opening browser...")
    print(f"   URL: {auth_url[:80]}...")
    webbrowser.open(auth_url)
    
    print()
    print("⏳ Waiting for authorization...")
    print("   (Complete the authorization in your browser)")
    print()
    
    # Wait for callback (timeout after 5 minutes)
    server.timeout = 300
    
    while auth_code is None:
        server.handle_request()
    
    print("✅ Authorization code received!")
    
    # Exchange code for tokens
    token_data = exchange_code_for_tokens(auth_code)
    
    if not token_data:
        print("❌ Failed to get tokens")
        return 1
    
    if 'error' in token_data:
        print(f"❌ Error: {token_data.get('error')}")
        print(f"   Description: {token_data.get('error_description', 'N/A')}")
        return 1
    
    # Verify we got the tokens
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    
    if not access_token:
        print("❌ No access token received")
        return 1
    
    print(f"\n✅ Access token: {access_token[:40]}...")
    
    if refresh_token:
        print(f"✅ Refresh token: {refresh_token[:40]}...")
    else:
        print("⚠️  No refresh token (you may need to revoke and reauthorize)")
    
    # Save tokens
    save_tokens(token_data)
    
    print()
    print("=" * 70)
    print("✅ SUCCESS! Tokens saved!")
    print("=" * 70)
    print()
    print("🎬 Now you can upload your video:")
    print("   python3 upload_simple.py")
    print()
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
