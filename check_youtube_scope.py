#!/usr/bin/env python3
"""
Check what scopes the current OAuth token has.
"""

import sys
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).parent))

from src.integrations.token_store import get_token

def check_token_info():
    """Check token information including scopes."""
    access_token = get_token("GOOGLE_OAUTH_ACCESS_TOKEN")
    
    if not access_token:
        print("❌ No access token found in .runtime_tokens.json")
        return
    
    print("=" * 70)
    print("OAUTH TOKEN INFORMATION")
    print("=" * 70)
    print(f"\n📋 Access Token: {access_token[:40]}...\n")
    
    # Check token info via Google's tokeninfo endpoint
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?access_token={access_token}"
        request = Request(url)
        
        with urlopen(request, timeout=10) as response:
            info = json.loads(response.read().decode())
        
        print("✅ Token is valid!\n")
        print("📊 Token Details:")
        print(f"   Issued to: {info.get('email', 'N/A')}")
        print(f"   Expires in: {info.get('expires_in', 'N/A')} seconds")
        print(f"   Audience: {info.get('aud', 'N/A')[:50]}...")
        
        # Check scopes
        scope_string = info.get('scope', '')
        scopes = scope_string.split()
        
        print(f"\n🔐 Granted Scopes ({len(scopes)}):")
        
        youtube_scopes = []
        other_scopes = []
        
        for scope in scopes:
            if 'youtube' in scope.lower():
                youtube_scopes.append(scope)
                print(f"   ✅ {scope}")
            else:
                other_scopes.append(scope)
        
        if not youtube_scopes:
            print("   ❌ No YouTube scopes found!")
        
        if other_scopes:
            print(f"\n📝 Other Scopes ({len(other_scopes)}):")
            for scope in other_scopes[:5]:
                print(f"   • {scope}")
            if len(other_scopes) > 5:
                print(f"   ... and {len(other_scopes) - 5} more")
        
        # Check if YouTube upload scope is present
        print("\n" + "=" * 70)
        print("YOUTUBE UPLOAD CHECK")
        print("=" * 70)
        
        required_scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube"
        ]
        
        has_upload_scope = any(s in scopes for s in required_scopes)
        
        if has_upload_scope:
            print("✅ YouTube upload scope is present!")
            print("   You can upload videos to YouTube.")
        else:
            print("❌ YouTube upload scope is MISSING!")
            print("\n💡 Required scopes:")
            for scope in required_scopes:
                print(f"   • {scope}")
            print("\n🔧 To fix:")
            print("   1. Start server: python3 src/api/server.py")
            print("   2. Visit: http://localhost:5000/admin")
            print("   3. Click 'Connect Google Account'")
            print("   4. Grant YouTube permissions")
        
        return has_upload_scope
        
    except Exception as e:
        print(f"❌ Error checking token: {e}")
        print("\nThis usually means the token is invalid or expired.")
        return False

if __name__ == "__main__":
    has_scope = check_token_info()
    sys.exit(0 if has_scope else 1)
