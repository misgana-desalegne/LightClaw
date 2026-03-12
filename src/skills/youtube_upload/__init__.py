"""
YouTube Upload Skill for LightClaw Agent

Upload video clips to YouTube with full metadata control.
"""

from src.skills.youtube_upload.skill import YouTubeUploadSkill, create_skill

__all__ = ["YouTubeUploadSkill", "create_skill"]
