# YouTube Upload Skill - Complete Guide

## Overview

The **YouTube Upload Skill** allows the LightClaw agent to upload video clips to YouTube with full control over metadata, privacy settings, and more. Perfect for automating the upload of video clips created by the NewsExtractor skill!

## Features

### Available Actions

1. **upload** - Upload any video file to YouTube
2. **upload_clip** - Upload a clip from NewsExtractor output directories
3. **list_uploads** - List your recent YouTube uploads
4. **delete_video** - Delete a video from YouTube
5. **update_video** - Update video metadata (title, description, privacy, etc.)
6. **quota_info** - Check YouTube upload quota information
7. **check_auth** - Verify YouTube authentication status

### Supported Intents

The orchestrator can recognize these intents:

- "upload video to youtube"
- "upload clip"
- "list my youtube videos"
- "publish video"

## Setup & Authentication

### 1. Prerequisites

You need a Google Cloud Project with YouTube Data API v3 enabled:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing one
3. Enable **YouTube Data API v3**
4. Create OAuth 2.0 credentials (Desktop application)
5. Download the credentials JSON

### 2. Environment Variables

Set these environment variables:

```bash
export GOOGLE_OAUTH_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
```

### 3. Authentication Flow

1. Start your LightClaw agent
2. Navigate to the `/admin` interface
3. Click "Connect Google Account"
4. Grant YouTube upload permissions
5. Token is stored in `.runtime_tokens.json`

### 4. Verify Authentication

```python
from src.skills.youtube_upload.skill import YouTubeUploadSkill
from src.integrations.youtube import YouTubeProvider
from src.agent.context import Context

provider = YouTubeProvider()
skill = YouTubeUploadSkill(provider)
context = Context()

result = skill.execute("check_auth", {}, context)
print(result.message)
# ✅ YouTube is authenticated and ready to upload!
```

## Usage Examples

### 1. Upload a Video File

```python
from src.skills.youtube_upload.skill import YouTubeUploadSkill
from src.integrations.youtube import YouTubeProvider
from src.agent.context import Context

provider = YouTubeProvider()
skill = YouTubeUploadSkill(provider)
context = Context()

result = skill.execute("upload", {
    "video_path": "/path/to/video.mp4",
    "title": "My Awesome Video",
    "description": "This is an amazing video!",
    "tags": ["viral", "shorts", "trending"],
    "privacy": "public",  # or "private", "unlisted"
    "category_id": "22",  # 22 = People & Blogs
}, context)

print(result.message)
# ✅ Video uploaded successfully!
# 📹 Title: My Awesome Video
# 🔗 URL: https://www.youtube.com/watch?v=abc123
# 🔒 Privacy: public
```

### 2. Upload a Clip from NewsExtractor

```python
# Upload by clip name
result = skill.execute("upload_clip", {
    "clip_name": "short_01.mp4",
    "title": "Viral Tech News #1",
    "description": "Latest tech news clip",
    "tags": ["tech", "news", "shorts"],
    "privacy": "public"
}, context)

# Upload by clip index (0-based)
result = skill.execute("upload_clip", {
    "clip_index": 0,  # First clip
    "title": "Trending News Clip",
    "privacy": "unlisted"
}, context)
```

### 3. List Your YouTube Videos

```python
result = skill.execute("list_uploads", {
    "max_results": 10
}, context)

print(result.message)
# 📹 Your recent uploads (5):
#
# 1. My Awesome Video
#    🔗 https://www.youtube.com/watch?v=abc123
#    📅 2026-03-08
#    ID: abc123
#
# 2. Viral Tech News #1
#    🔗 https://www.youtube.com/watch?v=def456
#    📅 2026-03-07
#    ID: def456
```

### 4. Update Video Metadata

```python
result = skill.execute("update_video", {
    "video_id": "abc123",
    "title": "Updated Title",
    "description": "Updated description",
    "tags": ["new", "tags"],
    "privacy": "public"
}, context)
```

### 5. Delete a Video

```python
result = skill.execute("delete_video", {
    "video_id": "abc123"
}, context)
```

### 6. Check Upload Quota

```python
result = skill.execute("quota_info", {}, context)

print(result.message)
# 📊 YouTube Upload Quota Information:
#
# 📤 Daily uploads: 6 videos
# 📦 Max file size: 256 GB
# ⏱️  Max video length: 12 hours
#
# ℹ️  Limits may vary based on account verification status
```

## Via Chat Interface (Telegram/Webchat)

Once integrated with the orchestrator, you can use natural language:

```
User: "upload the first clip to youtube as public"
Agent: ✅ Video uploaded successfully!
       📹 Title: Viral Clip - short_01
       🔗 URL: https://www.youtube.com/watch?v=abc123
       🔒 Privacy: public

User: "list my youtube videos"
Agent: 📹 Your recent uploads (3):

       1. Viral Clip - short_01
          🔗 https://www.youtube.com/watch?v=abc123
       ...

User: "check youtube quota"
Agent: 📊 YouTube Upload Quota Information:
       📤 Daily uploads: 6 videos
       ...
```

## Integration with NewsExtractor

The YouTube Upload skill automatically finds clips in these directories:

1. `src/skills/NewsExtractor/output_videos/`
2. `src/skills/NewsExtractor/shorts_from_youtube/`

**Complete Workflow:**

```python
# Step 1: Fetch news videos
news_result = news_skill.execute("fetch_tech", {"max_results": 5}, context)

# Step 2: Create clips (using clipper.py or videoClipper.py)
# This creates clips in output_videos/

# Step 3: Upload clips to YouTube
for i in range(3):  # Upload first 3 clips
    upload_result = youtube_skill.execute("upload_clip", {
        "clip_index": i,
        "title": f"Tech News Clip #{i+1}",
        "description": "Latest tech news from top channels",
        "tags": ["tech", "news", "viral", "shorts"],
        "privacy": "public"
    }, context)
    print(upload_result.message)
```

## Privacy Settings

YouTube supports three privacy levels:

- **private** - Only you can see the video
- **unlisted** - Anyone with the link can see it
- **public** - Everyone can find and watch it

```python
# Private upload (default)
result = skill.execute("upload", {
    "video_path": "video.mp4",
    "title": "Private Video",
    "privacy": "private"
}, context)

# Public upload
result = skill.execute("upload", {
    "video_path": "video.mp4",
    "title": "Public Video",
    "privacy": "public"
}, context)
```

## Video Categories

Common YouTube category IDs:

| ID  | Category                 |
| --- | ------------------------ |
| 1   | Film & Animation         |
| 2   | Autos & Vehicles         |
| 10  | Music                    |
| 15  | Pets & Animals           |
| 17  | Sports                   |
| 19  | Travel & Events          |
| 20  | Gaming                   |
| 22  | People & Blogs (default) |
| 23  | Comedy                   |
| 24  | Entertainment            |
| 25  | News & Politics          |
| 26  | Howto & Style            |
| 27  | Education                |
| 28  | Science & Technology     |

```python
# Upload as Tech/Science category
result = skill.execute("upload", {
    "video_path": "tech_video.mp4",
    "title": "Tech Review",
    "category_id": "28",  # Science & Technology
    "privacy": "public"
}, context)
```

## COPPA Compliance

If your video is made for kids, you MUST declare it:

```python
result = skill.execute("upload", {
    "video_path": "kids_video.mp4",
    "title": "Kids Content",
    "made_for_kids": True,  # REQUIRED for kids content
    "privacy": "public"
}, context)
```

## Error Handling

The skill handles various error scenarios:

```python
# File not found
result = skill.execute("upload", {
    "video_path": "/nonexistent/video.mp4",
    "title": "Test"
}, context)
# ❌ Video file not found: /nonexistent/video.mp4

# Not authenticated
result = skill.execute("upload", {
    "video_path": "video.mp4",
    "title": "Test"
}, context)
# ❌ YouTube not authenticated. Please authenticate via /admin

# Upload failure
# ❌ Upload failed: YouTube API error: 403 - Quota exceeded
```

## Advanced Features

### Batch Upload Multiple Clips

```python
from pathlib import Path

clips_dir = Path("src/skills/NewsExtractor/shorts_from_youtube")
clips = sorted(clips_dir.glob("*.mp4"))

for i, clip_path in enumerate(clips[:5]):  # Upload first 5
    result = skill.execute("upload", {
        "video_path": str(clip_path),
        "title": f"Viral Shorts #{i+1}",
        "description": "Auto-generated viral shorts",
        "tags": ["shorts", "viral", "trending"],
        "privacy": "public",
        "category_id": "24"  # Entertainment
    }, context)

    if result.success:
        print(f"✅ Uploaded: {clip_path.name}")
        print(f"   URL: {result.data['url']}")
    else:
        print(f"❌ Failed: {clip_path.name}")
```

### Update Video After Upload

```python
# Upload as private first
upload_result = skill.execute("upload", {
    "video_path": "video.mp4",
    "title": "Test Video",
    "privacy": "private"
}, context)

video_id = upload_result.data['id']

# Later, make it public
update_result = skill.execute("update_video", {
    "video_id": video_id,
    "privacy": "public"
}, context)
```

### Schedule Uploads (Future Enhancement)

```python
# This could be added to orchestrator
def schedule_daily_upload():
    """Upload a clip every day at 9 AM"""
    # Fetch news
    news_result = news_skill.execute("fetch_tech", {"max_results": 5}, context)

    # Create clips (via NewsExtractor)
    # ...

    # Upload the best clip
    upload_result = youtube_skill.execute("upload_clip", {
        "clip_index": 0,
        "title": f"Daily Tech News - {datetime.now().strftime('%Y-%m-%d')}",
        "privacy": "public"
    }, context)
```

## YouTube API Quotas

YouTube API has daily quota limits:

- **Default quota**: 10,000 units per day
- **Upload video**: ~1,600 units
- **You can upload**: ~6 videos per day (default quota)

To increase quota:

1. Apply for quota extension in Google Cloud Console
2. Explain your use case
3. Wait for approval (usually takes a few days)

## Troubleshooting

### Issue: "YouTube not authenticated"

**Solution:**

1. Set `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`
2. Navigate to `/admin` in your agent
3. Click "Connect Google Account"
4. Grant YouTube permissions

### Issue: "Upload failed: 403 - Quota exceeded"

**Solution:**

- You've hit the daily upload limit (6 videos)
- Wait until tomorrow (quota resets at midnight PST)
- Or apply for quota increase in Google Cloud Console

### Issue: "Upload failed: 400 - Invalid privacy status"

**Solution:**

- Use only: "private", "unlisted", or "public"
- Check for typos in privacy setting

### Issue: File too large

**Solution:**

- Max file size: 256 GB (verified accounts)
- Max file size: 2 GB (unverified accounts)
- Verify your account: https://www.youtube.com/verify

## File Structure

```
src/
├── integrations/
│   └── youtube.py              # YouTube API provider
│
├── skills/
│   ├── youtube_upload/
│   │   ├── __init__.py
│   │   └── skill.py            # Skill implementation
│   │
│   └── NewsExtractor/
│       ├── output_videos/      # Clips to upload
│       └── shorts_from_youtube/  # More clips
│
└── agent/
    └── orchestrator.py         # Route upload intents
```

## Testing

```bash
# Run the test script
python3 test_youtube_skill.py
```

Test script example:

```python
from src.skills.youtube_upload.skill import YouTubeUploadSkill
from src.integrations.youtube import YouTubeProvider
from src.agent.context import Context

provider = YouTubeProvider()
skill = YouTubeUploadSkill(provider)
context = Context()

# Test 1: Check auth
result = skill.execute("check_auth", {}, context)
print(result.message)

# Test 2: Get quota info
result = skill.execute("quota_info", {}, context)
print(result.message)

# Test 3: List uploads (if authenticated)
if provider.is_authenticated():
    result = skill.execute("list_uploads", {"max_results": 5}, context)
    print(result.message)
```

## Best Practices

1. **Start with private uploads** - Test first, then make public
2. **Use descriptive titles** - Max 100 characters
3. **Add relevant tags** - Helps with discoverability
4. **Choose correct category** - Improves recommendations
5. **Monitor quota usage** - Don't exceed 6 uploads/day
6. **Optimize video size** - Smaller files upload faster
7. **Use appropriate privacy** - Consider your audience

## Security Notes

- OAuth tokens are stored in `.runtime_tokens.json`
- **Never commit** `.runtime_tokens.json` to git
- Add to `.gitignore`: `.runtime_tokens.json`
- Tokens expire and auto-refresh (if refresh token available)
- Client secret should be kept confidential

## Summary

✅ **YouTube Upload Skill is ready!**

Features:

- Upload videos to YouTube with full metadata control
- Upload clips directly from NewsExtractor output
- List, update, and delete videos
- Check authentication and quota status
- Automatic clip discovery from output directories

The skill integrates seamlessly with the NewsExtractor skill for a complete viral video creation and publishing workflow! 🎉
