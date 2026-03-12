#!/bin/bash
# Quick YouTube OAuth Setup

echo "=============================================================================="
echo "YOUTUBE OAUTH - STEP BY STEP"
echo "=============================================================================="
echo ""
echo "📋 Current OAuth Client ID: $(grep GOOGLE_OAUTH_CLIENT_ID .env | cut -d'=' -f2)"
echo ""
echo "⚠️  BEFORE RUNNING THE OAUTH SCRIPT:"
echo ""
echo "1. Go to Google Cloud Console:"
echo "   https://console.cloud.google.com/apis/credentials"
echo ""
echo "2. Find this OAuth Client ID:"
echo "   696917218520-ck80jtk3q0cu8qkr34rve1et7sqhjltg"
echo ""
echo "3. Click 'Edit' and add this Authorized redirect URI:"
echo "   http://localhost:8080/oauth2callback"
echo ""
echo "4. Make sure YouTube Data API v3 is enabled:"
echo "   https://console.cloud.google.com/apis/library/youtube.googleapis.com"
echo ""
echo "5. Click 'ENABLE' if not already enabled"
echo ""
echo "=============================================================================="
echo ""
read -p "Have you completed steps 1-5 above? (y/n): " answer

if [ "$answer" != "y" ]; then
    echo ""
    echo "❌ Please complete the steps above first, then run this script again."
    exit 1
fi

echo ""
echo "=============================================================================="
echo "STARTING OAUTH FLOW"
echo "=============================================================================="
echo ""
echo "✅ This will:"
echo "   1. Start a local server on http://localhost:8080"
echo "   2. Open your browser to Google OAuth"
echo "   3. Ask you to grant YouTube permissions"
echo "   4. Save tokens to .runtime_tokens.json"
echo ""
echo "⚠️  IMPORTANT: When granting permissions, make sure to:"
echo "   ✅ Allow YouTube upload access"
echo "   ✅ Allow YouTube manage access"
echo ""
read -p "Ready to start? (y/n): " start

if [ "$start" != "y" ]; then
    echo "❌ Cancelled"
    exit 1
fi

echo ""
echo "🚀 Launching OAuth script..."
echo ""

python3 get_youtube_token.py

if [ $? -eq 0 ]; then
    echo ""
    echo "=============================================================================="
    echo "✅ SUCCESS! Now upload your video:"
    echo "=============================================================================="
    echo ""
    echo "   python3 upload_simple.py"
    echo ""
else
    echo ""
    echo "❌ OAuth failed. Check the errors above."
    echo ""
    echo "Common issues:"
    echo "  1. Redirect URI not added to Google Cloud Console"
    echo "  2. YouTube API not enabled"
    echo "  3. Browser blocked the popup"
    echo ""
fi
