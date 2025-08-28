# Segma Realtime Console

The **Segma Realtime Console** is a lightweight web console for testing, developing, and debugging real-time AI agent workflows.  
It is designed to help developers quickly connect browsers, backends, and the OpenAI Realtime API for streaming speech, transcription, and conversation logic.

---

## Features

- 🔄 **Realtime Agent Console** – simple UI for testing real-time speech/voice flows
- 🎙️ **Browser Audio Capture** – microphone streaming directly to backend
- 📡 **Relay Support** – relay browser traffic to OpenAI Realtime API or other backends
- ⚙️ **Configurable Environment** – `.env` support for API keys, ports, and service endpoints
- 🐳 **Dockerized Deployment** – reproducible setup with `docker compose`
- 🌐 **Browser Access** – runs locally on `http://<ip>:3005/`

---

## Prerequisites

Before starting, make sure you have:

- **Git** (for pulling the repository)
- **Docker & Docker Compose** (for containerized setup)
- **Chrome Browser** (tested and recommended)
- Access to an **OpenAI API key** (or your custom realtime API server)

---

## Getting Started

Clone and set up the environment:

```bash
git clone https://gitlab.com/wavein/segma-realtime-console.git
cd segma-realtime-console
docker compose build
cp ./env-example ./.env
vi ./.env   # configure your env:
#OPENAI_API_KEY – OpenAI API key
#API_URL – URL of agent inference API
docker compose up -d
```

Open Chrome.

Enable the following experimental flag:

```
chrome://flags/#unsafely-treat-insecure-origin-as-secure
```  

Add your dev server URL (e.g., http://<ip>:3005) so microphone access works with insecure origins.

Visit:

```
http://<ip address>:3005/
```

You should see the Segma Realtime Console interface.
