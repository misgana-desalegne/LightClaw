#!/usr/bin/env python3
"""
Helper script to update Facebook Page Access Token in .env
Usage: python3 update_fb_token.py
"""
import os
import sys

def update_env_token():
    env_path = '/home/misgun/LightClaw/.env'
    
    print("=" * 70)
    print("Facebook Page Access Token Updater")
    print("=" * 70)
    print("\nInstructions:")
    print("1. Go to: https://developers.facebook.com/tools/explorer/")
    print("2. Select your App")
    print("3. Generate Access Token with permissions:")
    print("   - pages_read_engagement")
    print("   - pages_manage_posts")
    print("   - pages_show_list")
    print("   - publish_video")
    print("4. Select your PAGE (not profile)")
    print("5. Copy the token and paste below")
    print("\n" + "=" * 70)
    
    new_token = input("\nPaste your new Facebook Page Access Token: ").strip()
    
    if not new_token:
        print("❌ No token provided. Exiting.")
        sys.exit(1)
    
    if len(new_token) < 50:
        print(f"⚠️  Warning: Token seems short ({len(new_token)} chars). Are you sure it's correct?")
        confirm = input("Continue anyway? (y/n): ").strip().lower()
        if confirm != 'y':
            sys.exit(1)
    
    # Read current .env
    if not os.path.exists(env_path):
        print(f"❌ .env file not found at {env_path}")
        sys.exit(1)
    
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Update FACEBOOK_PAGE_ACCESS_TOKEN
    updated = False
    new_lines = []
    for line in lines:
        if line.strip().startswith('FACEBOOK_PAGE_ACCESS_TOKEN='):
            new_lines.append(f'FACEBOOK_PAGE_ACCESS_TOKEN={new_token}\n')
            updated = True
            print(f"\n✅ Updated FACEBOOK_PAGE_ACCESS_TOKEN")
        else:
            new_lines.append(line)
    
    # If not found, add it
    if not updated:
        new_lines.append(f'\nFACEBOOK_PAGE_ACCESS_TOKEN={new_token}\n')
        print(f"\n✅ Added FACEBOOK_PAGE_ACCESS_TOKEN to .env")
    
    # Write back
    with open(env_path, 'w') as f:
        f.writelines(new_lines)
    
    print(f"\n✅ .env file updated successfully!")
    print(f"\nToken preview: {new_token[:20]}...{new_token[-10:]}")
    print(f"Token length: {len(new_token)} characters")
    
    print("\n" + "=" * 70)
    print("Next steps:")
    print("1. Run: python3 test_fb_simple.py")
    print("2. If successful, test the full pipeline")
    print("=" * 70)

if __name__ == '__main__':
    try:
        update_env_token()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
