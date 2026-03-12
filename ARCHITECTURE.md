# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTOMATION PIPELINE                          │
│                  (automation_pipeline.py)                       │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     VIDEO PROCESSING                            │
│                                                                 │
│  ┌────────────────┐     ┌────────────────┐                    │
│  │ News Extractor │ ──> │ Clipper (FFmpeg)│                   │
│  │  Fetch Videos  │     │  Create Clips   │                   │
│  └────────────────┘     └────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UPLOAD MANAGER                               │
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐      │
│  │   YouTube    │   │   Facebook   │   │  Instagram   │      │
│  │  Integration │   │ Integration  │   │ Integration  │      │
│  └──────────────┘   └──────────────┘   └──────────────┘      │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐
│   YouTube    │   │   Facebook   │   │     CDN Uploader     │
│   Data API   │   │  Graph API   │   │  ┌────────────────┐ │
│              │   │              │   │  │ Local Server   │ │
│   OAuth 2.0  │   │ Page Access  │   │  │ AWS S3        │ │
│              │   │    Token     │   │  │ Cloudflare R2 │ │
└──────────────┘   └──────────────┘   │  └────────────────┘ │
                                      └──────────────────────┘
                                               │
                                               ▼
                                      ┌──────────────┐
                                      │  Instagram   │
                                      │  Graph API   │
                                      └──────────────┘
```

---

## Component Breakdown

### 1. Automation Pipeline (Main)
**File**: `automation_pipeline.py`

**Responsibilities:**
- Fetch viral videos
- Create short clips
- Upload to all platforms
- Schedule runs (every 30 min)
- Handle rate limits
- Log everything

**Key Classes:**
- `AutomationPipeline` - Main pipeline orchestrator

### 2. Video Processing

#### News Extractor
**File**: `src/skills/news_extractor/skill.py`

**Responsibilities:**
- Fetch viral tech/news videos
- Search YouTube, Reddit, etc.
- Filter by views, engagement

#### Clipper
**File**: `src/skills/NewsExtractor/clipper.py`

**Responsibilities:**
- Download videos (yt-dlp)
- Create short clips (FFmpeg)
- Optimize for Shorts/Reels

### 3. Upload Integrations

#### YouTube Integration
**File**: `src/integrations/youtube.py`

**Features:**
- OAuth 2.0 authentication
- Video upload (resumable)
- Playlist management
- Analytics

**API**: YouTube Data API v3

#### Facebook Integration
**File**: `src/integrations/facebook.py`

**Features:**
- Page video upload (resumable)
- Text posts with links
- Photo posts
- Analytics

**API**: Facebook Graph API v18.0

**Authentication**: Page Access Token

#### Instagram Integration
**File**: `src/integrations/instagram.py`

**Features:**
- Video posts (requires public URL)
- Reels (short videos)
- Photo posts
- Analytics

**API**: Instagram Graph API v18.0

**Authentication**: Same token as Facebook

### 4. CDN Uploader

**File**: `src/utils/cdn_uploader.py`

**Backends:**

1. **Local HTTP Server**
   - File: `src/utils/file_server.py`
   - Port: 8080 (configurable)
   - Good for: Testing

2. **AWS S3**
   - Library: boto3
   - Public URLs
   - Good for: Production

3. **Cloudflare R2**
   - Library: boto3 (S3-compatible)
   - Public URLs
   - Good for: Production (cheaper)

**Purpose**: Instagram requires publicly accessible video URLs

---

## Data Flow

### Successful Upload Flow

```
1. Fetch Video
   │
   ├─> Download from source
   └─> Save to temp directory
   
2. Create Clip
   │
   ├─> Extract 20s segment
   ├─> Optimize for vertical (9:16)
   └─> Save to shorts_from_youtube/
   
3. Upload to YouTube
   │
   ├─> Authenticate (OAuth)
   ├─> Upload video
   ├─> Set title, description, tags
   └─> Get video URL
   
4. Upload to Facebook
   │
   ├─> Authenticate (Page Token)
   ├─> Upload video (resumable)
   ├─> Set title, description
   └─> Get post URL
   
5. Upload to Instagram
   │
   ├─> Upload to CDN
   ├─> Get public URL
   ├─> Create media container
   ├─> Wait for processing
   ├─> Publish media
   └─> Get post URL
   
6. Cleanup
   │
   └─> Delete old clips (keep 20)
```

---

## Authentication Flow

### YouTube OAuth Flow

```
1. User runs pipeline
   │
2. Pipeline checks for token
   │
   ├─> Token exists? ──> Use token
   │
   └─> No token? ──> Start OAuth flow
       │
       ├─> Open browser
       ├─> User logs in
       ├─> User grants permissions
       ├─> Redirect to callback
       └─> Save token
```

### Facebook/Instagram Token Flow

```
1. User creates Meta Developer App
   │
2. User generates Page Access Token
   │  (via Graph API Explorer)
   │
3. User adds token to .env
   │
4. Pipeline reads token
   │
5. Pipeline uses token for API calls
   │
   └─> Token expires in 60 days
       └─> User must refresh manually
```

---

## CDN Architecture

### Local Backend (Testing)

```
Pipeline ──> Local File Server (port 8080)
             │
             └──> http://localhost:8080/video.mp4
                  │
                  └──> Instagram API ✗ (Not publicly accessible)
                       │
                       └──> Use ngrok:
                            ngrok http 8080 ──> https://abc123.ngrok.io/video.mp4
                                                 │
                                                 └──> Instagram API ✓
```

### S3 Backend (Production)

```
Pipeline ──> Upload to S3 Bucket
             │
             └──> https://bucket.s3.amazonaws.com/video.mp4
                  │
                  └──> Instagram API ✓ (Publicly accessible)
```

### Cloudflare R2 Backend (Production)

```
Pipeline ──> Upload to R2 Bucket
             │
             └──> https://bucket.your-domain.com/video.mp4
                  │
                  └──> Instagram API ✓ (Publicly accessible)
```

---

## Error Handling

### Pipeline Errors

```
Try:
    1. Fetch videos
    │
    ├─> Success ──> Continue
    └─> Fail ──> Log error, skip run
    
    2. Create clips
    │
    ├─> Success ──> Continue
    └─> Fail ──> Log error, skip upload
    
    3. Upload to YouTube
    │
    ├─> Success ──> Continue to Facebook
    └─> Fail ──> Log error, skip Facebook/Instagram
    
    4. Upload to Facebook (optional)
    │
    ├─> Success ──> Continue to Instagram
    └─> Fail ──> Log error, continue to Instagram
    
    5. Upload to Instagram (optional)
    │
    ├─> Success ──> Done!
    └─> Fail ──> Log error, continue
    
Except:
    Log full traceback
    Continue next run
```

### Rate Limit Handling

```
YouTube:
    ├─> Check daily quota (15 clips/day)
    ├─> If exceeded ──> Skip upload
    └─> If OK ──> Upload

Facebook:
    └─> Facebook handles rate limiting (200 req/hour)

Instagram:
    ├─> Check daily quota (25 posts/day)
    ├─> If exceeded ──> Skip upload
    └─> If OK ──> Upload
```

---

## Logging

### Log Levels

```
INFO  ── Normal operations (fetch, upload, success)
WARN  ── Warnings (auth missing, quota near limit)
ERROR ── Errors (upload failed, API error)
```

### Log Files

```
logs/
├── automation.log        # Main log (all runs)
├── automation.log.1      # Rotated log
└── automation.log.2      # Older rotated log
```

### Log Rotation

```
When: Daily at midnight
Keep: 7 days of logs
Max size: 10 MB per log
```

---

## Scheduling

### Schedule Options

#### 1. Built-in Scheduler (Recommended)

```python
# Run every 30 minutes
schedule.every(30).minutes.do(pipeline.run_pipeline)

# Reset counter at midnight
schedule.every().day.at("00:00").do(pipeline.reset_daily_counter)
```

#### 2. Cron Job

```bash
# Every 30 minutes
*/30 * * * * cd /path/to/LightClaw && python3 automation_pipeline.py --once
```

#### 3. Systemd Service

```ini
[Service]
ExecStart=/usr/bin/python3 /path/to/LightClaw/automation_pipeline.py
Restart=always
```

---

## Security

### Credentials Storage

```
.env file (not in git)
├── YouTube OAuth Client ID/Secret
├── Facebook App ID/Secret
├── Facebook Page Access Token
├── Instagram Business Account ID
├── AWS/Cloudflare credentials
└── LLM API keys
```

### Token Management

```
YouTube:
├── OAuth token stored in: .youtube_token.json
├── Refresh: Automatic
└── Expiry: 7 days (auto-refreshed)

Facebook/Instagram:
├── Page token stored in: .env
├── Refresh: Manual
└── Expiry: 60 days
```

### Best Practices

1. ✅ Never commit `.env` to git
2. ✅ Use least-privilege IAM policies (S3/R2)
3. ✅ Rotate tokens regularly
4. ✅ Monitor API usage
5. ✅ Enable 2FA on Meta Developer account

---

## Performance

### Pipeline Performance

```
Average run time: 5-10 minutes
├── Fetch videos: 10-30 seconds
├── Create clips: 1-3 minutes (FFmpeg)
├── Upload YouTube: 1-2 minutes
├── Upload Facebook: 1-2 minutes
└── Upload Instagram: 2-4 minutes (processing time)
```

### Optimization Tips

1. **LLM Speed**: Use optimized Ollama (see LLM_SPEED_OPTIMIZATION.md)
2. **Video Processing**: Use hardware acceleration (FFmpeg)
3. **Parallel Uploads**: Upload to Facebook/Instagram in parallel
4. **CDN**: Use CDN with fast upload speeds

---

## Monitoring

### Health Checks

```python
# Check authentication
pipeline.check_authentication()

# Check quotas
pipeline.check_daily_quota()

# Check CDN
uploader.upload(test_file)
```

### Metrics to Monitor

- ✅ Upload success rate
- ✅ API error rate
- ✅ Daily upload count
- ✅ Disk space usage
- ✅ Token expiration dates

---

## Scalability

### Current Limits

```
Videos per run: 1
Clips per video: 1
Runs per day: 48 (every 30 min)
Max uploads per day: 15 (quota limit)
```

### Scaling Options

1. **Increase frequency**: Run every 15 minutes
2. **Multiple clips**: Create 2-3 clips per video
3. **Quota increase**: Request from YouTube
4. **Multiple channels**: Use multiple accounts
5. **Distributed**: Run on multiple servers

---

## Future Enhancements

### Planned Features

- [ ] Twitter/X integration
- [ ] TikTok integration
- [ ] Analytics dashboard
- [ ] A/B testing
- [ ] Auto-generated thumbnails
- [ ] Voice-over generation
- [ ] Scheduled posting
- [ ] Content moderation
- [ ] Multi-language support

### Technical Improvements

- [ ] Docker containerization
- [ ] CI/CD pipeline
- [ ] Monitoring dashboard
- [ ] Webhook notifications
- [ ] Database for tracking uploads
- [ ] Queue system for parallel processing

---

## Maintenance

### Regular Tasks

**Daily:**
- Check logs for errors
- Monitor upload success rate

**Weekly:**
- Review upload quality
- Check disk space
- Clean old files

**Monthly:**
- Refresh Facebook token
- Review quotas and limits
- Update dependencies

**Quarterly:**
- Review analytics
- Optimize pipeline
- Update documentation

---

## Support

For architecture questions or issues:
1. Check logs: `logs/automation.log`
2. Review documentation
3. Test components individually
4. Open GitHub issue

---

**Last Updated**: 2026-03-12
