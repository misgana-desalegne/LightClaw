# Social Media Integration Guide

## Overview

The automation pipeline now supports posting videos to:

- ✅ **YouTube** (Shorts)
- ✅ **Facebook** (Page videos)
- ✅ **Instagram** (Reels/Videos)

After creating video clips, the pipeline automatically uploads them to all configured platforms.

---

## 🎬 YouTube Setup

### 1. Create OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable **YouTube Data API v3**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Set Application Type: **Web application**
6. Add Authorized redirect URI: `http://localhost:8000/oauth-callback`
7. Download the credentials JSON file

### 2. Configure Environment

Save credentials to: `youtube_client_secret.json`

### 3. Authenticate

```bash
# Run the pipeline - it will prompt for OAuth
python automation_pipeline.py --once

# Or authenticate via web admin (if available)
# Visit /admin and click "Authenticate YouTube"
```

The pipeline will open a browser for OAuth authorization. After authorizing, tokens are saved automatically.

---

## 📱 Facebook Setup

### 1. Create Meta Developer App

1. Go to [Meta Developer Console](https://developers.facebook.com/)
2. Click **Create App**
3. Select **Business** type
4. Fill in app details and create

### 2. Add Facebook Page

1. In your app, go to **Settings** → **Basic**
2. Note your **App ID** and **App Secret**
3. Go to **Products** → Add **Facebook Login**
4. Add your Facebook Page

### 3. Get Page Access Token

You need a **Page Access Token** (not User Access Token):

#### Option A: Graph API Explorer (Quick Test)

1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app
3. Click **Get Token** → **Get Page Access Token**
4. Select your page
5. Copy the token

⚠️ **This token expires in 1-2 hours** - good for testing only.

#### Option B: Long-Lived Token (Production)

1. Get a short-lived user access token from Graph API Explorer
2. Exchange it for a long-lived token (60 days):

```bash
curl -i -X GET "https://graph.facebook.com/v18.0/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=SHORT_LIVED_TOKEN"
```

3. Get Page Access Token using the long-lived user token:

```bash
curl -i -X GET "https://graph.facebook.com/v18.0/me/accounts?access_token=LONG_LIVED_USER_TOKEN"
```

4. Find your page in the response and use its `access_token`

### 4. Get Page ID

```bash
curl -i -X GET "https://graph.facebook.com/v18.0/me/accounts?access_token=PAGE_ACCESS_TOKEN"
```

Or visit your Facebook Page and check the URL:

- `facebook.com/yourpage` → Page ID is in "About" section
- Or use: `facebook.com/[YOUR_PAGE_ID]`

### 5. Configure Environment

Add to `.env`:

```bash
FACEBOOK_APP_ID=your_app_id
FACEBOOK_APP_SECRET=your_app_secret
FACEBOOK_PAGE_ID=your_page_id
FACEBOOK_PAGE_ACCESS_TOKEN=your_page_access_token
```

### 6. Required Permissions

Your Page Access Token needs these permissions:

- `pages_manage_posts` - Post to page
- `pages_read_engagement` - Read post analytics
- `pages_show_list` - Access page list

---

## 📷 Instagram Setup

### Prerequisites

- Instagram **Business** or **Creator** account (not personal)
- Facebook Page linked to Instagram account
- Same Meta Developer App as Facebook

### 1. Link Instagram to Facebook Page

1. Open Instagram app → Settings → Account → Linked Accounts
2. Link to your Facebook Page
3. Convert to **Business Account** or **Creator Account** if not already

### 2. Get Instagram Business Account ID

```bash
curl -i -X GET "https://graph.facebook.com/v18.0/me/accounts?fields=instagram_business_account&access_token=PAGE_ACCESS_TOKEN"
```

Find the `instagram_business_account.id` in the response.

Or use Graph API Explorer:

1. Select your Page
2. Query: `/me?fields=instagram_business_account`
3. Copy the ID

### 3. Configure Environment

Add to `.env`:

```bash
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_instagram_account_id
# Use same token as Facebook
```

### 4. Required Permissions

Your token needs:

- `instagram_basic` - Basic Instagram access
- `instagram_content_publish` - Publish content
- `pages_read_engagement` - Read engagement data

---

## 🌐 CDN Setup (for Instagram)

Instagram requires **publicly accessible URLs** for video uploads. You have 3 options:

### Option 1: Local HTTP Server (Testing)

**Best for:** Development and testing

```bash
# In .env
CDN_BACKEND=local
FILE_SERVER_PORT=8080
FILE_SERVER_DIR=src/skills/NewsExtractor/shorts_from_youtube
```

The pipeline starts a local HTTP server automatically. Videos are served from `http://localhost:8080/`.

⚠️ **Limitations:**

- Only works if Instagram API can access your local machine
- Not suitable for production (firewalls, NAT, etc.)
- Good for testing with ngrok or similar tunneling

**Using ngrok for testing:**

```bash
# Start ngrok
ngrok http 8080

# Update your code to use ngrok URL
# Or set up a reverse proxy
```

### Option 2: AWS S3 (Production)

**Best for:** Production, reliable, scalable

```bash
# In .env
CDN_BACKEND=s3
AWS_S3_BUCKET=your-bucket-name
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

**Setup:**

1. Create S3 bucket
2. Enable public access:
   - Bucket Policy: Allow `s3:GetObject` for everyone
   - CORS: Allow GET from `*.instagram.com`
3. Create IAM user with `s3:PutObject` and `s3:DeleteObject` permissions
4. Install boto3: `pip install boto3`

**Bucket Policy Example:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    }
  ]
}
```

### Option 3: Cloudflare R2 (Production)

**Best for:** Production, cheaper than S3, generous free tier

```bash
# In .env
CDN_BACKEND=cloudflare
CLOUDFLARE_R2_BUCKET=your-bucket-name
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_R2_ACCESS_KEY=your_access_key
CLOUDFLARE_R2_SECRET_KEY=your_secret_key
CLOUDFLARE_R2_PUBLIC_URL=https://yourbucket.your-domain.com
```

**Setup:**

1. Create Cloudflare R2 bucket
2. Generate R2 API tokens
3. Set up custom domain (optional but recommended)
4. Make bucket public
5. Install boto3: `pip install boto3`

---

## 🚀 Running the Pipeline

### Run Once (Test)

```bash
python automation_pipeline.py --once
```

### Run Continuously (Production)

```bash
# Runs every 30 minutes
python automation_pipeline.py
```

### Check Logs

```bash
tail -f logs/automation.log
```

---

## 📊 Pipeline Flow

```
1. Fetch viral tech/news videos
2. Create short clips (20s each)
3. Upload to YouTube ✓
4. Upload to Facebook ✓
5. Upload to Instagram ✓
   - Upload video to CDN
   - Get public URL
   - Post to Instagram
6. Clean up old clips
```

---

## ⚙️ Configuration

Edit `automation_pipeline.py` to adjust:

```python
FETCH_CATEGORIES = ["news"]  # Categories to fetch
VIDEOS_PER_FETCH = 1         # Videos per run
CLIPS_PER_VIDEO = 1          # Clips per video
CLIP_DURATION = 20           # Seconds
MAX_UPLOADS_PER_RUN = 1      # Max uploads per run
PRIVACY_STATUS = "unlisted"  # YouTube privacy
```

---

## 🔍 Troubleshooting

### YouTube Authentication Failed

```
Error: YouTube not authenticated
```

**Solution:**

1. Check `youtube_client_secret.json` exists
2. Run authentication flow
3. Check OAuth redirect URI is `http://localhost:8000/oauth-callback`

### Facebook Upload Failed

```
Error: (#200) Requires pages_manage_posts permission
```

**Solution:**

1. Check permissions in Graph API Explorer
2. Generate new token with correct permissions
3. Update `FACEBOOK_PAGE_ACCESS_TOKEN` in `.env`

### Instagram Upload Failed

```
Error: Invalid media URL
```

**Solution:**

1. Check CDN is configured and running
2. Verify video URL is publicly accessible
3. Test URL in browser: `curl -I <video_url>`
4. Check Instagram can access your CDN (firewall, NAT)

### CDN Upload Failed

```
Error: Failed to upload to CDN
```

**Solution:**

**For local backend:**

- Check `FILE_SERVER_PORT` is available
- Check `FILE_SERVER_DIR` exists
- Use ngrok for external access

**For S3/R2:**

- Verify credentials are correct
- Check bucket exists and is public
- Verify IAM permissions
- Install boto3: `pip install boto3`

### Rate Limits

If you hit rate limits:

**YouTube:**

- Default quota: ~6 uploads/day
- Pipeline limit: 15 clips/day (5 runs)
- Request quota increase from Google

**Facebook:**

- Standard: 200 requests/hour
- Usually sufficient for automation

**Instagram:**

- Publishing rate limit: 25 posts per day
- Video processing: ~30 seconds per video

---

## 📝 Best Practices

1. **Start with YouTube Only**
   - Test YouTube uploads first
   - Add Facebook/Instagram once working

2. **Use Unlisted/Private for Testing**
   - Set `PRIVACY_STATUS = "private"` during testing
   - Change to `"public"` for production

3. **Monitor Logs**
   - Check `logs/automation.log` regularly
   - Set up log rotation

4. **CDN Cleanup**
   - CDN files can be deleted after Instagram upload
   - Set up lifecycle policies (S3/R2) to auto-delete old files

5. **Token Refresh**
   - Facebook Page Tokens expire (60 days for long-lived)
   - Set up token refresh automation
   - Monitor token expiration

6. **Content Quality**
   - Review clips before enabling auto-posting
   - Adjust `CLIP_DURATION` for better content
   - Use relevant hashtags in descriptions

---

## 🔐 Security Notes

- **Never commit `.env` to git**
- **Rotate tokens regularly**
- **Use least-privilege IAM policies** (S3/R2)
- **Monitor API usage** to detect unauthorized access
- **Enable 2FA** on Meta Developer account

---

## 📈 Monitoring & Analytics

### YouTube Analytics

```python
from src.integrations.youtube import YouTubeProvider

yt = YouTubeProvider()
analytics = yt.get_video_statistics(video_id)
```

### Facebook Insights

```python
from src.integrations.facebook import FacebookProvider

fb = FacebookProvider()
posts = fb.get_page_posts(limit=10)
```

### Instagram Insights

```python
from src.integrations.instagram import InstagramProvider

ig = InstagramProvider()
insights = ig.get_media_insights(media_id)
```

---

## 🆘 Support

For issues:

1. Check logs: `logs/automation.log`
2. Test each platform individually
3. Verify credentials and permissions
4. Check API status pages:
   - YouTube: https://www.google.com/appsstatus
   - Facebook/Instagram: https://developers.facebook.com/status/

---

## 📚 Additional Resources

- [YouTube API Documentation](https://developers.google.com/youtube/v3)
- [Facebook Graph API](https://developers.facebook.com/docs/graph-api)
- [Instagram Graph API](https://developers.facebook.com/docs/instagram-api)
- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [Cloudflare R2 Documentation](https://developers.cloudflare.com/r2/)
