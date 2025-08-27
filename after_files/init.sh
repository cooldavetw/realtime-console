#!/bin/bash

/frontend_autorestart.sh &
echo "frontend started"
python3 /agent.py 2>&1
