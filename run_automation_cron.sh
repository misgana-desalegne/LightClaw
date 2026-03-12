#!/bin/bash
# Cron wrapper for automation pipeline
# Run this from cron every 30 minutes

cd /home/misgun/LightClaw

# Set environment variables (update these!)
export GOOGLE_OAUTH_CLIENT_ID="your-client-id"
export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"

# Run pipeline once
/usr/bin/python3 automation_pipeline.py --once

# Log completion
echo "$(date): Pipeline completed" >> logs/cron.log
