#!/bin/bash
# Manage LightClaw Automation Service
# Convenient wrapper around systemctl commands

SERVICE_NAME="lightclaw-automation"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_help() {
    echo "LightClaw Automation Manager"
    echo
    echo "Usage: $0 [command]"
    echo
    echo "Commands:"
    echo "  start        Start the automation service"
    echo "  stop         Stop the automation service"
    echo "  restart      Restart the automation service"
    echo "  status       Show service status"
    echo "  logs         Show live logs (Ctrl+C to exit)"
    echo "  logs-file    Show main log file"
    echo "  enable       Enable service to start on boot"
    echo "  disable      Disable service from starting on boot"
    echo "  test         Run automation once (no scheduler)"
    echo "  stats        Show statistics"
    echo "  help         Show this help message"
    echo
}

check_service() {
    if ! systemctl list-unit-files | grep -q "$SERVICE_NAME.service"; then
        echo -e "${RED}❌ Service not installed${NC}"
        echo "Run: sudo ./install_automation.sh"
        exit 1
    fi
}

case "$1" in
    start)
        check_service
        echo -e "${BLUE}🚀 Starting automation service...${NC}"
        sudo systemctl start $SERVICE_NAME
        echo -e "${GREEN}✅ Service started${NC}"
        echo
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    
    stop)
        check_service
        echo -e "${YELLOW}⏸️  Stopping automation service...${NC}"
        sudo systemctl stop $SERVICE_NAME
        echo -e "${GREEN}✅ Service stopped${NC}"
        ;;
    
    restart)
        check_service
        echo -e "${BLUE}🔄 Restarting automation service...${NC}"
        sudo systemctl restart $SERVICE_NAME
        echo -e "${GREEN}✅ Service restarted${NC}"
        echo
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    
    status)
        check_service
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    
    logs)
        check_service
        echo -e "${BLUE}📋 Showing live logs (Ctrl+C to exit)...${NC}"
        echo
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    
    logs-file)
        LOG_FILE="logs/automation.log"
        if [ -f "$LOG_FILE" ]; then
            echo -e "${BLUE}📋 Showing $LOG_FILE (last 50 lines)...${NC}"
            echo
            tail -n 50 "$LOG_FILE"
        else
            echo -e "${RED}❌ Log file not found: $LOG_FILE${NC}"
        fi
        ;;
    
    enable)
        check_service
        echo -e "${BLUE}✅ Enabling service to start on boot...${NC}"
        sudo systemctl enable $SERVICE_NAME
        echo -e "${GREEN}✅ Service enabled${NC}"
        ;;
    
    disable)
        check_service
        echo -e "${YELLOW}⏸️  Disabling service from starting on boot...${NC}"
        sudo systemctl disable $SERVICE_NAME
        echo -e "${GREEN}✅ Service disabled${NC}"
        ;;
    
    test)
        echo -e "${BLUE}🧪 Running automation once (test mode)...${NC}"
        echo
        python3 automation_pipeline.py &
        PID=$!
        
        echo "Process ID: $PID"
        echo "Press Ctrl+C to stop"
        echo
        
        wait $PID
        ;;
    
    stats)
        LOG_FILE="logs/automation.log"
        
        echo -e "${BLUE}📊 Automation Statistics${NC}"
        echo
        
        if [ ! -f "$LOG_FILE" ]; then
            echo -e "${RED}❌ Log file not found${NC}"
            exit 1
        fi
        
        echo "Pipeline runs:"
        grep "Starting pipeline run" "$LOG_FILE" | wc -l
        
        echo
        echo "Videos fetched:"
        grep "Fetched.*videos" "$LOG_FILE" | tail -n 5
        
        echo
        echo "Clips uploaded:"
        grep "Uploaded:" "$LOG_FILE" | wc -l
        
        echo
        echo "Recent uploads:"
        grep "Uploaded:" "$LOG_FILE" | tail -n 5
        
        echo
        echo "Errors:"
        grep "ERROR" "$LOG_FILE" | wc -l
        
        echo
        echo "Last 5 errors:"
        grep "ERROR" "$LOG_FILE" | tail -n 5
        ;;
    
    help|--help|-h|"")
        show_help
        ;;
    
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo
        show_help
        exit 1
        ;;
esac
