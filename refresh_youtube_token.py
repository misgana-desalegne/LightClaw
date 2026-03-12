#!/usr/bin/env python3
"""Test YouTube token refresh."""

import sys
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).parent))

from src.integrations.token_store import get_token, upsert_tokens

def refresh_token():
    """Manually refresh the YouTube access token."""
    refresh_token = get_token("GOOGLE_OAUTH_REFRESH_TOKEN")
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    
    print(f"Refresh token: {refresh_token[:40] if refresh_token else 'None'}...")
    print(f"Client ID: {client_id}")
    print(f"Client secret: {'*' * 20}")
    
    if not all([refresh_token, client_id, client_secret]):
        print("❌ Missing required credentials")
        return False
    
    print("\n🔄 Refreshing access token...")
    
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
        with urlopen(request, timeout=15) as response:
            token_response = json.loads(response.read().decode("utf-8"))
        
        new_access_token = token_response.get("access_token")
        if new_access_token:
            print(f"\n✅ Got new access token: {new_access_token[:40]}...")
            
            # Save it
            upsert_tokens({"GOOGLE_OAUTH_ACCESS_TOKEN": new_access_token})
            print("✅ Token saved to .runtime_tokens.json")
            return True
        else:
            print("❌ No access token in response")
            print(json.dumps(token_response, indent=2))
            return False
    
    except Exception as e:
        print(f"❌ Error refreshing token: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = refresh_token()
    sys.exit(0 if success else 1)
