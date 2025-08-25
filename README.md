# Claude Telegram Bot

A Telegram bot that interfaces with Claude API for conversational AI.

## Features

- User authentication via password or Claude API key
- Conversation history with context retention
- Session management with configurable timeout
- Health check endpoint for monitoring
- Docker support for easy deployment
- Graceful shutdown handling

## Setup

### Local Development

1. Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

2. Edit `.env` with your credentials:
- `BOT_TOKEN`: Get from @BotFather on Telegram
- `API_ID` & `API_HASH`: Get from https://my.telegram.org/apps
- `MASTER_PASSWORD`: Password for credit-based access
- `DEFAULT_CLAUDE_API_KEY`: Claude API key for password auth

3. Install dependencies and run:
```bash
uv sync
uv run python bot.py
```

### Docker Deployment

```bash
docker-compose up -d
```

### Render.com Deployment

1. Fork this repository
2. Connect your GitHub account to Render
3. Create a new Background Worker
4. Select this repository
5. Add environment variables in Render dashboard
6. Deploy

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | Telegram bot token |
| `API_ID` | Yes | Telegram API ID |
| `API_HASH` | Yes | Telegram API hash |
| `MASTER_PASSWORD` | No | Password for shared access |
| `DEFAULT_CLAUDE_API_KEY` | No | Claude API key for password users |
| `SESSION_STRING` | No | Persistent session (auto-generated) |
| `PORT` | No | Health check port (default: 8080) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |
| `MAX_CONVERSATION_LENGTH` | No | Max messages in history (default: 20) |
| `SESSION_TIMEOUT_HOURS` | No | Session expiry time (default: 24) |

## Commands

- `/start` - Start or restart authentication
- `/reset` - Clear conversation history
- `/help` - Show help message

## Architecture

- `bot.py` - Main bot logic with Telethon
- `health_server.py` - Health check endpoint for monitoring
- `Dockerfile` - Container configuration
- `render.yaml` - Render.com deployment config

## Security

- API keys stored only in memory
- Sessions expire after inactivity
- No conversation logging
- Password/API key authentication