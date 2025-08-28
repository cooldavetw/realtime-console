#!/bin/bash

/frontend_autorestart.sh &
echo "frontend started"
cd /backend && python3 main.py 2>&1
