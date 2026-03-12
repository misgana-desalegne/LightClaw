# 🎬 LightClaw - Automated Social Media Video Pipeline

**Automated pipeline for fetching viral videos, creating short clips, and uploading to YouTube, Facebook, and Instagram.**

## 🚀 Features

✅ **Fetch viral tech/news videos** from multiple sources  
✅ **Create short clips** (20s optimized for Shorts/Reels)  
✅ **Upload to YouTube** (with OAuth authentication)  
✅ **Upload to Facebook** (Page videos)  
✅ **Upload to Instagram** (Reels/Videos via Graph API)  
✅ **CDN support** (Local server, AWS S3, Cloudflare R2)  
✅ **Optimized LLM** (Fast intent classification)  
✅ **Automated scheduling** (Runs every 30 minutes)  
✅ **Rate limit management** (YouTube quotas, API limits)  
✅ **Comprehensive logging** (Track all uploads)

---

## 📚 Documentation

| Document                                                       | Description                                     |
| -------------------------------------------------------------- | ----------------------------------------------- |
| **[QUICKSTART.md](QUICKSTART.md)**                             | Quick start guide - Get running in 5 minutes    |
| **[SOCIAL_MEDIA_INTEGRATION.md](SOCIAL_MEDIA_INTEGRATION.md)** | Complete setup for YouTube, Facebook, Instagram |
| **[ARCHITECTURE.md](ARCHITECTURE.md)**                         | System architecture and data flow               |
| **[LLM_SPEED_OPTIMIZATION.md](LLM_SPEED_OPTIMIZATION.md)**     | Optimize LLM speed for intent classification    |
| **[YOUTUBE_UPLOAD_SKILL.md](YOUTUBE_UPLOAD_SKILL.md)**         | YouTube OAuth setup details                     |

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt

**📚 [Full Automation Guide →](AUTOMATION_README.md)**

---

## Phase 1: Architecture

### Core design

- `Orchestrator`: routes intents to skills and coordinates cross-skill flows
- `SkillRegistry`: plugin-style registration and intent-based resolution
- `Context`: shared state/memory for current session
```

### 2. Configure Environment

Copy and edit `.env`:

```bash
# Required: YouTube OAuth
GOOGLE_OAUTH_CLIENT_ID=your_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret

# Optional: Facebook
FACEBOOK_PAGE_ACCESS_TOKEN=your_token
FACEBOOK_PAGE_ID=your_page_id

# Optional: Instagram
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_account_id

# CDN for Instagram (local, s3, or cloudflare)
CDN_BACKEND=local
FILE_SERVER_PORT=8080
```

### 3. Test Integrations

```bash
python test_social_integrations.py
```

### 4. Run Pipeline

```bash
# Test run (once)
python automation_pipeline.py --once

# Production (continuous)
python automation_pipeline.py
```

---

## 📊 Pipeline Flow

```
1. Fetch viral tech/news videos
   ↓
2. Create short clips (20s)
   ↓
3. Upload to YouTube ✓
   ↓
4. Upload to Facebook ✓ (if configured)
   ↓
5. Upload to Instagram ✓ (if configured + CDN)
   ↓
6. Clean up old files
```

---

## 🛠️ Utilities

### Test Integrations

```bash
python test_social_integrations.py
```

Tests Facebook, Instagram, and CDN setup.

### Cleanup Old Files

```bash
# Clean local clips (7 days)
python cleanup.py --clips

# Clean CDN files (3 days)
python cleanup.py --cdn --keep-days 3

# Clean logs (30 days)
python cleanup.py --logs

# Clean everything
python cleanup.py --all
```

---

## 📁 Project Structure

```
LightClaw/
├── automation_pipeline.py          # Main pipeline script
├── test_social_integrations.py    # Test script for integrations
├── cleanup.py                      # Cleanup utility
│
├── src/
│   ├── integrations/
│   │   ├── youtube.py             # YouTube API integration
│   │   ├── facebook.py            # Facebook Graph API
│   │   ├── instagram.py           # Instagram Graph API
│   │   └── llm.py                 # LLM (optimized)
│   │
│   ├── utils/
│   │   ├── cdn_uploader.py        # CDN uploader (S3, R2, local)
│   │   ├── file_server.py         # Local HTTP file server
│   │   └── logger.py              # Logging utilities
│   │
│   └── skills/
│       ├── news_extractor/        # News video fetcher
│       └── youtube_upload/        # YouTube upload skill
│
└── logs/
    └── automation.log             # Pipeline logs
```

---

## ⚙️ Configuration

### Pipeline Settings (automation_pipeline.py)

```python
FETCH_CATEGORIES = ["news"]      # Categories to fetch
VIDEOS_PER_FETCH = 1             # Videos per run
CLIPS_PER_VIDEO = 1              # Clips per video
CLIP_DURATION = 20               # Seconds
MAX_UPLOADS_PER_RUN = 1          # Max uploads per run
PRIVACY_STATUS = "unlisted"      # YouTube privacy
```

---

## 🔍 Troubleshooting

### YouTube Authentication Failed

```bash
# Check OAuth credentials
ls youtube_client_secret.json

# Run authentication
python automation_pipeline.py --once
```

### Facebook Upload Failed

```bash
# Test connection
python test_social_integrations.py

# Verify token in .env
echo $FACEBOOK_PAGE_ACCESS_TOKEN
```

### Instagram Upload Failed

Instagram requires **public URLs**:

```bash
# Check CDN
echo $CDN_BACKEND

# For local: Use ngrok
ngrok http 8080

# For production: Use S3 or R2
```

See [SOCIAL_MEDIA_INTEGRATION.md](SOCIAL_MEDIA_INTEGRATION.md) for detailed troubleshooting.

---

## 📈 Monitoring

### View Logs

```bash
# Real-time
tail -f logs/automation.log

# Errors only
grep ERROR logs/automation.log

# Recent uploads
grep "✅" logs/automation.log | tail -20
```

### Check Uploads

- **YouTube**: https://studio.youtube.com/
- **Facebook**: Your page posts
- **Instagram**: Your profile reels

---

## 🚦 Rate Limits

| Platform  | Limit          | Pipeline Default |
| --------- | -------------- | ---------------- |
| YouTube   | ~6 uploads/day | 15 clips/day     |
| Facebook  | 200 req/hour   | Sufficient       |
| Instagram | 25 posts/day   | Sufficient       |

---

## 🤝 Contributing

Contributions welcome! Please fork the repository and submit a pull request.

---

## 📄 License

MIT License

---

## 🆘 Support

For issues:

1. Check `logs/automation.log`
2. Run `python test_social_integrations.py`
3. See documentation in markdown files
4. Open an issue on GitHub

---

**Made with ❤️ by the LightClaw team**
