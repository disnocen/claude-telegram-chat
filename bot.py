#!/usr/bin/env python3
import os
import asyncio
import logging
import signal
from typing import Dict, Optional
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
import hashlib
import json
try:
    from health_server import HealthServer
except ImportError:
    HealthServer = None

load_dotenv()

log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, log_level.upper(), logging.INFO)
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH')
MASTER_PASSWORD = os.getenv('MASTER_PASSWORD')
DEFAULT_CLAUDE_API_KEY = os.getenv('DEFAULT_CLAUDE_API_KEY')
SESSION_STRING = os.getenv('SESSION_STRING', '')
HEALTH_CHECK_PORT = int(os.getenv('PORT', '8080'))  # Render.com uses PORT env var
MAX_CONVERSATION_LENGTH = int(os.getenv('MAX_CONVERSATION_LENGTH', '20'))
SESSION_TIMEOUT_HOURS = int(os.getenv('SESSION_TIMEOUT_HOURS', '24'))

if not all([BOT_TOKEN, API_ID, API_HASH]):
    raise ValueError("Please set BOT_TOKEN, API_ID, and API_HASH in .env file")

session = StringSession(SESSION_STRING) if SESSION_STRING else StringSession()
bot = TelegramClient(session, API_ID, API_HASH)

class UserSession:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.authenticated = False
        self.api_key: Optional[str] = None
        self.conversation_history = []
        self.last_activity = datetime.now()
        self.claude_client: Optional[AsyncAnthropic] = None
    
    def authenticate_with_password(self, password: str) -> bool:
        if MASTER_PASSWORD and password == MASTER_PASSWORD:
            self.authenticated = True
            self.api_key = DEFAULT_CLAUDE_API_KEY
            if self.api_key:
                self.claude_client = AsyncAnthropic(api_key=self.api_key)
            return True
        return False
    
    def authenticate_with_api_key(self, api_key: str) -> bool:
        self.authenticated = True
        self.api_key = api_key
        self.claude_client = AsyncAnthropic(api_key=api_key)
        return True
    
    def add_message(self, role: str, content: str):
        self.conversation_history.append({
            "role": role,
            "content": content
        })
        self.last_activity = datetime.now()
        
        if len(self.conversation_history) > MAX_CONVERSATION_LENGTH:
            self.conversation_history = self.conversation_history[-MAX_CONVERSATION_LENGTH:]
    
    def reset_conversation(self):
        self.conversation_history = []

user_sessions: Dict[int, UserSession] = {}

def get_or_create_session(user_id: int) -> UserSession:
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    return user_sessions[user_id]

def clean_old_sessions():
    current_time = datetime.now()
    expired_sessions = []
    for user_id, session in user_sessions.items():
        if current_time - session.last_activity > timedelta(hours=SESSION_TIMEOUT_HOURS):
            expired_sessions.append(user_id)
    
    for user_id in expired_sessions:
        del user_sessions[user_id]

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user_id = event.sender_id
    session = get_or_create_session(user_id)
    session.reset_conversation()
    
    welcome_message = """
🤖 **Welcome to Claude Telegram Bot!**

To start chatting with Claude, you need to authenticate:

**Option 1:** Enter the access password
**Option 2:** Enter your Claude API key (starts with 'sk-ant-')

Simply send your password or API key as the next message.

📝 **Commands:**
• `/start` - Start or restart the bot
• `/reset` - Clear conversation history
• `/help` - Show this help message

After authentication, just send any message to chat with Claude!
"""
    
    await event.respond(welcome_message)

@bot.on(events.NewMessage(pattern='/reset'))
async def reset_handler(event):
    user_id = event.sender_id
    session = get_or_create_session(user_id)
    
    if not session.authenticated:
        await event.respond("❌ Please authenticate first using /start")
        return
    
    session.reset_conversation()
    await event.respond("✅ Conversation history cleared. Starting fresh!")

@bot.on(events.NewMessage(pattern='/help'))
async def help_handler(event):
    help_message = """
📚 **Claude Telegram Bot Help**

**Commands:**
• `/start` - Start or restart authentication
• `/reset` - Clear conversation history
• `/help` - Show this help message

**How to use:**
1. Start with `/start`
2. Authenticate with password or API key
3. Send any message to chat with Claude
4. Use `/reset` to clear conversation history

**Tips:**
• Claude remembers your conversation context
• Long conversations are automatically trimmed
• Sessions expire after 24 hours of inactivity

**Privacy:**
• Your API key is stored only in memory
• Conversations are not logged or saved
"""
    await event.respond(help_message)

@bot.on(events.NewMessage)
async def message_handler(event):
    if event.message.text and event.message.text.startswith('/'):
        return
    
    user_id = event.sender_id
    session = get_or_create_session(user_id)
    message_text = event.message.text or ""
    
    if not session.authenticated:
        if message_text.startswith('sk-ant-'):
            try:
                test_client = AsyncAnthropic(api_key=message_text)
                await test_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hi"}]
                )
                session.authenticate_with_api_key(message_text)
                await event.respond("✅ **Authentication successful!**\n\nYou can now start chatting with Claude. Just send any message!")
                logger.info(f"User {user_id} authenticated with API key")
            except Exception as e:
                await event.respond("❌ Invalid API key. Please check and try again.")
                logger.error(f"API key validation failed for user {user_id}: {e}")
        
        elif MASTER_PASSWORD and session.authenticate_with_password(message_text):
            await event.respond("✅ **Authentication successful!**\n\nYou can now start chatting with Claude. Just send any message!")
            logger.info(f"User {user_id} authenticated with password")
        
        else:
            await event.respond("❌ Invalid password or API key. Please try again or use /start to see options.")
        return
    
    if not session.claude_client:
        await event.respond("❌ No Claude API key configured. Please restart with /start")
        return
    
    typing_message = await event.respond("🤔 Claude is thinking...")
    
    try:
        session.add_message("user", message_text)
        
        system_prompt = """You are Claude, a helpful AI assistant created by Anthropic. You're chatting with a user through Telegram. 
        Be conversational, helpful, and engaging. Keep responses concise but informative, suitable for a chat interface.
        You can use Telegram markdown formatting: *bold*, _italic_, `code`, ```code blocks```"""
        
        response = await session.claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=system_prompt,
            messages=session.conversation_history,
            temperature=0.7
        )
        
        assistant_message = response.content[0].text
        session.add_message("assistant", assistant_message)
        
        await typing_message.delete()
        
        if len(assistant_message) > 4096:
            chunks = [assistant_message[i:i+4096] for i in range(0, len(assistant_message), 4096)]
            for chunk in chunks:
                await event.respond(chunk, parse_mode='markdown')
        else:
            await event.respond(assistant_message, parse_mode='markdown')
        
        logger.info(f"Successfully processed message for user {user_id}")
        
    except Exception as e:
        await typing_message.delete()
        error_message = f"❌ Error: {str(e)}\n\nPlease try again or use /reset to clear the conversation."
        await event.respond(error_message)
        logger.error(f"Error processing message for user {user_id}: {e}")

async def periodic_cleanup():
    while True:
        await asyncio.sleep(3600)
        clean_old_sessions()
        logger.info("Cleaned up old sessions")

async def main():
    health_server = None
    
    # Start health check server if available
    if HealthServer:
        health_server = HealthServer(port=HEALTH_CHECK_PORT)
        await health_server.start()
        health_server.set_bot_status("starting")
    
    try:
        await bot.start(bot_token=BOT_TOKEN)
        logger.info("Bot started successfully!")
        
        if health_server:
            health_server.set_bot_status("running")
        
        if not SESSION_STRING:
            session_string = bot.session.save()
            logger.info(f"Session string (save this in .env as SESSION_STRING):\n{session_string}")
        
        asyncio.create_task(periodic_cleanup())
        
        # Handle graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Shutting down gracefully...")
            if health_server:
                health_server.set_bot_status("stopping")
            asyncio.create_task(shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        await bot.run_until_disconnected()
    finally:
        if health_server:
            await health_server.stop()

async def shutdown():
    await bot.disconnect()
    logger.info("Bot disconnected")

if __name__ == '__main__':
    asyncio.run(main())