#!/bin/bash
if ! pgrep -f "bot/api.py" > /dev/null; then
    echo "$(date): API not running, restarting..." >> /var/log/plantusdt-api-monitor.log
    /root/PlantUSDT/start_api.sh
fi
