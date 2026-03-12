#!/usr/bin/env python3
"""
Setup Validation Script
Checks if everything is configured correctly for automation.
"""

import os
import sys
import json
from pathlib import Path

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def check(name: str, condition: bool, error_msg: str = "") -> bool:
    """Check a condition and print result."""
    if condition:
        print(f"{GREEN}✅ {name}{RESET}")
        return True
    else:
        print(f"{RED}❌ {name}{RESET}")
        if error_msg:
            print(f"   {YELLOW}→ {error_msg}{RESET}")
        return False

def main():
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}LightClaw Automation Setup Validator{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    all_passed = True
    
    # 1. Check Python version
    print(f"{BLUE}1. Python Environment{RESET}")
    py_version = sys.version_info
    all_passed &= check(
        "Python 3.8+",
        py_version >= (3, 8),
        f"Current: {py_version.major}.{py_version.minor}, Need: 3.8+"
    )
    
    # 2. Check required packages
    print(f"\n{BLUE}2. Required Packages{RESET}")
    packages = ["schedule", "yt_dlp", "moviepy"]
    for pkg in packages:
        try:
            __import__(pkg.replace("-", "_"))
            all_passed &= check(f"Package: {pkg}", True)
        except ImportError:
            all_passed &= check(
                f"Package: {pkg}",
                False,
                f"Install with: pip3 install {pkg}"
            )
    
    # 3. Check environment variables
    print(f"\n{BLUE}3. Environment Variables{RESET}")
    env_vars = [
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET"
    ]
    for var in env_vars:
        value = os.getenv(var)
        all_passed &= check(
            f"Environment: {var}",
            bool(value),
            f"Set with: export {var}='your-value'"
        )
    
    # 4. Check token file
    print(f"\n{BLUE}4. Authentication Tokens{RESET}")
    token_file = Path(".tokens.json")
    if token_file.exists():
        try:
            with open(token_file) as f:
                tokens = json.load(f)
            
            has_access = "google_access_token" in tokens
            has_refresh = "google_refresh_token" in tokens
            
            all_passed &= check(
                "Token file exists",
                True
            )
            all_passed &= check(
                "Access token present",
                has_access,
                "Authenticate via web UI at http://localhost:8000/admin"
            )
            all_passed &= check(
                "Refresh token present",
                has_refresh,
                "Authenticate via web UI at http://localhost:8000/admin"
            )
        except json.JSONDecodeError:
            all_passed &= check(
                "Token file valid JSON",
                False,
                "File is corrupted, delete and re-authenticate"
            )
    else:
        all_passed &= check(
            "Token file exists",
            False,
            "Authenticate via web UI at http://localhost:8000/admin"
        )
    
    # 5. Check required files
    print(f"\n{BLUE}5. Required Files{RESET}")
    required_files = [
        "automation_pipeline.py",
        "install_automation.sh",
        "manage_automation.sh",
        "src/skills/news_extractor/skill.py",
        "src/skills/youtube_upload/skill.py",
        "src/integrations/youtube.py",
    ]
    for file in required_files:
        path = Path(file)
        all_passed &= check(
            f"File: {file}",
            path.exists(),
            f"File missing or incorrect structure"
        )
    
    # 6. Check executables
    print(f"\n{BLUE}6. Executable Scripts{RESET}")
    executables = [
        "automation_pipeline.py",
        "install_automation.sh",
        "manage_automation.sh",
    ]
    for exe in executables:
        path = Path(exe)
        is_executable = path.exists() and os.access(path, os.X_OK)
        all_passed &= check(
            f"Executable: {exe}",
            is_executable,
            f"Run: chmod +x {exe}"
        )
    
    # 7. Check ffmpeg
    print(f"\n{BLUE}7. External Dependencies{RESET}")
    import subprocess
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        all_passed &= check(
            "ffmpeg installed",
            result.returncode == 0,
            "Install with: sudo apt-get install ffmpeg"
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        all_passed &= check(
            "ffmpeg installed",
            False,
            "Install with: sudo apt-get install ffmpeg"
        )
    
    # 8. Check directories
    print(f"\n{BLUE}8. Directory Structure{RESET}")
    dirs = ["src/skills", "src/integrations", "logs"]
    for dir_path in dirs:
        path = Path(dir_path)
        all_passed &= check(
            f"Directory: {dir_path}",
            path.exists() and path.is_dir(),
            f"Create with: mkdir -p {dir_path}"
        )
    
    # Final summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    if all_passed:
        print(f"{GREEN}✅ All checks passed! You're ready to run automation.{RESET}")
        print(f"\n{BLUE}Next steps:{RESET}")
        print(f"  1. Test run: ./automation_pipeline.py --once")
        print(f"  2. Install service: sudo ./install_automation.sh")
        print(f"  3. Start service: sudo systemctl start lightclaw-automation")
    else:
        print(f"{RED}❌ Some checks failed. Please fix the issues above.{RESET}")
        print(f"\n{BLUE}Common fixes:{RESET}")
        print(f"  • Install packages: pip3 install -r requirements.txt")
        print(f"  • Set environment: export GOOGLE_OAUTH_CLIENT_ID='...'")
        print(f"  • Authenticate: python3 src/main.py → http://localhost:8000/admin")
        print(f"  • Make executable: chmod +x *.sh automation_pipeline.py")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
