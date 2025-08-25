#!/bin/bash

/agent_autorestart.sh &
echo "agent started"
cd /frontend
npm run dev
