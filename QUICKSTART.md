# Quick Start Guide

## 🚀 Running the Automation Pipeline

### Prerequisites

1. ✅ **YouTube OAuth** - Authenticated and working
2. ✅ **Facebook** (Optional) - Page Access Token configured
3. ✅ **Instagram** (Optional) - Business Account ID configured
4. ✅ **CDN** (For Instagram) - Local server or S3/R2 configured

---

## Step 1: Test Integrations

Run the test script to verify your setup:

```bash
python test_social_integrations.py
```

This will check:

- Facebook authentication and API access
- Instagram authentication and API access
- CDN uploader functionality

Fix any issues before proceeding.

---

## Step 2: Configure Pipeline

Edit `automation_pipeline.py` settings (lines 30-36):

```python
FETCH_CATEGORIES = ["news"]      # Categories to fetch
VIDEOS_PER_FETCH = 1             # Videos per run
CLIPS_PER_VIDEO = 1              # Clips per video
CLIP_DURATION = 20               # Seconds
MAX_UPLOADS_PER_RUN = 1          # Max uploads per run
PRIVACY_STATUS = "unlisted"      # YouTube privacy
```

**Recommended for testing:**

- Start with `PRIVACY_STATUS = "private"` or `"unlisted"`
- Use `VIDEOS_PER_FETCH = 1` and `CLIPS_PER_VIDEO = 1`
- Change to `"public"` after testing

---

## Step 3: Run Pipeline (Test Mode)

Run once to test the full pipeline:

```bash
python automation_pipeline.py --once
```

**What happens:**

1. Fetches 1 viral video
2. Creates 1 short clip (20s)
3. Uploads to YouTube ✓
4. Uploads to Facebook ✓ (if configured)
5. Uploads to Instagram ✓ (if configured + CDN setup)
6. Logs everything to `logs/automation.log`

**Check results:**

- YouTube: Check your channel
- Facebook: Check your page
- Instagram: Check your profile
- Logs: `tail -f logs/automation.log`

---

## Step 4: Run Pipeline (Production Mode)

Run continuously (every 30 minutes):

```bash
python automation_pipeline.py
```

**What happens:**

- Runs immediately on start
- Then runs every 30 minutes
- Resets daily upload counter at midnight
- Stops on Ctrl+C

**Monitor:**

```bash
# Watch logs
tail -f logs/automation.log

# Check running process
ps aux | grep automation_pipeline
```

---

## Step 5: Run as Service (Optional)

### Using systemd (Linux)

Create service file: `/etc/systemd/system/lightclaw-automation.service`

```ini
[Unit]
Description=LightClaw Automation Pipeline
After=network.target

[Service]
Type=simple
User=misgun
WorkingDirectory=/home/misgun/LightClaw
ExecStart=/usr/bin/python3 /home/misgun/LightClaw/automation_pipeline.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**

```bash
sudo systemctl enable lightclaw-automation
sudo systemctl start lightclaw-automation

# Check status
sudo systemctl status lightclaw-automation

# View logs
sudo journalctl -u lightclaw-automation -f
```

### Using Cron

Add to crontab (`crontab -e`):

```bash
# Run every 30 minutes
*/30 * * * * cd /home/misgun/LightClaw && /usr/bin/python3 automation_pipeline.py --once >> logs/automation.log 2>&1
```

---

## 🔍 Monitoring

### Check Logs

```bash
# Real-time logs
tail -f logs/automation.log

# Recent errors
grep ERROR logs/automation.log | tail -20

# Upload summary
grep "✅" logs/automation.log | tail -20
```

### Check Uploads

**YouTube:**

- Visit: https://studio.youtube.com/
- Check: Content → Videos
- Filter: Unlisted/Private

**Facebook:**

- Visit your page
- Check: Posts or Videos tab

**Instagram:**

- Visit your profile
- Check: Reels or Posts

---

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# LLM (for intent classification)
LLM_BACKEND=ollama
LLM_MODEL=mistral

# YouTube (required)
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...

# Facebook (optional)
FACEBOOK_PAGE_ACCESS_TOKEN=...
FACEBOOK_PAGE_ID=...

# Instagram (optional)
INSTAGRAM_BUSINESS_ACCOUNT_ID=...

# CDN (for Instagram)
CDN_BACKEND=local              # or s3, cloudflare
FILE_SERVER_PORT=8080
```

### Pipeline Settings (automation_pipeline.py)

```python
# Lines 30-36
FETCH_CATEGORIES = ["news"]
VIDEOS_PER_FETCH = 1
CLIPS_PER_VIDEO = 1
CLIP_DURATION = 20
MAX_UPLOADS_PER_RUN = 1
PRIVACY_STATUS = "unlisted"
```

---

## 🐛 Troubleshooting

### YouTube Upload Failed

```
Error: YouTube not authenticated
```

**Fix:**

1. Check `youtube_client_secret.json` exists
2. Run: `python automation_pipeline.py --once`
3. Complete OAuth flow in browser

### Facebook Upload Failed

```
Error: Facebook not authenticated
```

**Fix:**

1. Check `.env` has `FACEBOOK_PAGE_ACCESS_TOKEN` and `FACEBOOK_PAGE_ID`
2. Run: `python test_social_integrations.py`
3. Verify token is valid (test in Graph API Explorer)

### Instagram Upload Failed

```
Error: Invalid media URL
```

**Fix:**

1. Instagram needs **public URLs** (not local files)
2. Check CDN is configured: `CDN_BACKEND=local` (or s3/cloudflare)
3. For local: Ensure port 8080 is accessible
4. For production: Use S3 or Cloudflare R2

### No Clips Created

```
Warning: No clips created
```

**Fix:**

1. Check NewsExtractor clipper is installed
2. Verify video URL is valid
3. Check disk space
4. See logs for ffmpeg errors

### Rate Limits

**YouTube:**

- Default: ~6 uploads/day
- Pipeline: 15 clips/day (5 runs × 1 clip)
- Solution: Request quota increase

**Facebook:**

- Rate: 200 requests/hour
- Usually sufficient

**Instagram:**

- Rate: 25 posts/day
- Videos: ~30s processing time

---

## 📊 Analytics

### View Statistics

**YouTube:**

```python
from src.integrations.youtube import YouTubeProvider
yt = YouTubeProvider()
stats = yt.get_video_statistics(video_id)
```

**Facebook:**

```python
from src.integrations.facebook import FacebookProvider
fb = FacebookProvider()
posts = fb.get_page_posts(limit=10)
```

---

## 🎯 Best Practices

1. **Start Small**
   - Test with 1 clip, unlisted privacy
   - Gradually increase after verifying quality

2. **Monitor Quality**
   - Review clips before going public
   - Adjust CLIP_DURATION for better content
   - Use relevant hashtags

3. **Manage Quotas**
   - YouTube: 15 clips/day = 5 runs
   - Instagram: 25 posts/day max
   - Monitor usage

4. **Token Management**
   - Facebook tokens expire (60 days)
   - Set calendar reminder to refresh
   - Monitor logs for auth errors

5. **CDN Cleanup**
   - Delete old videos from CDN
   - Set up S3/R2 lifecycle policies
   - Save storage costs

---

## 📚 Additional Resources

- [Full Setup Guide](SOCIAL_MEDIA_INTEGRATION.md)
- [LLM Optimization](LLM_SPEED_OPTIMIZATION.md)
- [YouTube Upload Guide](YOUTUBE_UPLOAD_SKILL.md)

---

## 🆘 Support

For issues:

1. Check `logs/automation.log`
2. Run `python test_social_integrations.py`
3. Verify credentials in `.env`
4. See [SOCIAL_MEDIA_INTEGRATION.md](SOCIAL_MEDIA_INTEGRATION.md)
