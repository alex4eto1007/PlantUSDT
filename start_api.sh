#!/bin/bash
cd /root/PlantUSDT
source venv/bin/activate
nohup python bot/api.py > /var/log/plantusdt-api.log 2>&1 &
echo $! > /var/run/plantusdt-api.pid
echo "API started with PID: $(cat /var/run/plantusdt-api.pid)"
