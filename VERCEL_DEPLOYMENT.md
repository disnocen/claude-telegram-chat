# Vercel Deployment Guide

This guide will help you deploy the Claude Telegram Bot to Vercel using serverless webhooks.

## Prerequisites

1. A Vercel account (sign up at [vercel.com](https://vercel.com))
2. Vercel CLI installed (`npm i -g vercel`)
3. Telegram Bot Token from [@BotFather](https://t.me/botfather)
4. Claude API key from [Anthropic Console](https://console.anthropic.com)

## Architecture

This serverless version uses:
- **Webhooks** instead of polling for real-time message handling
- **Direct Telegram API calls** instead of Telethon for better serverless compatibility
- **File-based session storage** in `/tmp` for user authentication persistence
- **Pure serverless functions** compatible with Vercel's constraints

## Environment Variables

You'll need to set the following environment variables in Vercel:

### Required Variables
- `BOT_TOKEN` - Your Telegram bot token from BotFather
- `MASTER_PASSWORD` - Master password for authentication (optional)
- `DEFAULT_CLAUDE_API_KEY` - Your Claude API key

### Optional Variables
- `LOG_LEVEL` - Logging level (default: INFO)
- `MAX_CONVERSATION_LENGTH` - Max conversation history (default: 20)
- `SESSION_TIMEOUT_HOURS` - Session timeout in hours (default: 24)
- `WEBHOOK_SECRET` - Secret token for webhook security (optional)

## Deployment Steps

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd claude-telegram-chat
```

### 2. Install Vercel CLI

```bash
npm install -g vercel
```

### 3. Login to Vercel

```bash
vercel login
```

### 4. Deploy to Vercel

```bash
vercel --prod
```

Follow the prompts:
- Link to existing project or create new one
- Select the scope (your account)
- Confirm project settings

### 5. Set Environment Variables

#### Option A: Via Vercel Dashboard
1. Go to your project on [vercel.com](https://vercel.com)
2. Navigate to Settings → Environment Variables
3. Add each variable from `.env.example`

#### Option B: Via CLI
```bash
vercel env add BOT_TOKEN
vercel env add API_ID
vercel env add API_HASH
vercel env add MASTER_PASSWORD
vercel env add DEFAULT_CLAUDE_API_KEY
```

### 6. Set Telegram Webhook

After deployment, you need to set the webhook URL for your Telegram bot:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-project.vercel.app/api/webhook"}'
```

Replace:
- `<YOUR_BOT_TOKEN>` with your actual bot token
- `your-project.vercel.app` with your Vercel deployment URL

### 7. Verify Webhook

Check if the webhook is set correctly:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

## Testing

1. Open Telegram and search for your bot
2. Send `/start` to begin
3. Authenticate with your master password or API key
4. Start chatting with Claude!

## Monitoring

- Check deployment logs: `vercel logs`
- View function logs in Vercel Dashboard
- Health check endpoint: `https://your-project.vercel.app/health`

## Troubleshooting

### Bot not responding
- Check webhook is set correctly
- Verify environment variables are set
- Check Vercel function logs for errors

### Authentication issues
- Ensure `MASTER_PASSWORD` or API keys are set correctly
- Check that API keys are valid and have sufficient credits

### Session issues
- Note: Vercel serverless functions are stateless
- Consider using Vercel KV or external database for persistent sessions
- Current implementation uses in-memory storage (sessions reset on redeploy)

## Security Notes

1. Never commit `.env` files with real credentials
2. Use Vercel's environment variables for sensitive data
3. Regularly rotate API keys and passwords
4. Consider implementing rate limiting for production use

## Limitations

- **Stateless Functions**: Vercel serverless functions don't maintain state between invocations
- **Session Storage**: Current implementation uses in-memory storage which resets on each deployment
- **File Storage**: Cannot use file-based session storage in Vercel
- **Timeout**: Vercel functions have a maximum execution time (10s for hobby, 60s for pro)

## Production Recommendations

For production use, consider:
1. Using Vercel KV or Redis for session persistence
2. Implementing proper error handling and retries
3. Adding monitoring and alerting
4. Setting up rate limiting
5. Using a database for conversation history

## Support

For issues or questions:
- Check Vercel documentation: [vercel.com/docs](https://vercel.com/docs)
- Telegram Bot API: [core.telegram.org/bots](https://core.telegram.org/bots)
- Claude API: [docs.anthropic.com](https://docs.anthropic.com)