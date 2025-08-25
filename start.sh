#!/bin/bash
set -e

echo "Starting Claude Telegram Bot..."

# Check required environment variables
if [ -z "$BOT_TOKEN" ]; then
    echo "Error: BOT_TOKEN is not set"
    exit 1
fi

if [ -z "$API_ID" ]; then
    echo "Error: API_ID is not set"
    exit 1
fi

if [ -z "$API_HASH" ]; then
    echo "Error: API_HASH is not set"
    exit 1
fi

# Start the bot
exec uv run python bot.py