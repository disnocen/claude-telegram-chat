#!/usr/bin/env python3
import os
import json
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
import asyncio
import hashlib
import hmac

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
MAX_CONVERSATION_LENGTH = int(os.getenv('MAX_CONVERSATION_LENGTH', '20'))
SESSION_TIMEOUT_HOURS = int(os.getenv('SESSION_TIMEOUT_HOURS', '24'))
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# In-memory storage (consider using Vercel KV or another database for production)
user_sessions = {}

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

async def send_message(chat_id: int, text: str, parse_mode: str = None):
    import aiohttp
    params = {
        'chat_id': chat_id,
        'text': text
    }
    if parse_mode:
        params['parse_mode'] = parse_mode
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{TELEGRAM_API_URL}/sendMessage", json=params) as resp:
            return await resp.json()

async def edit_message(chat_id: int, message_id: int, text: str):
    import aiohttp
    params = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{TELEGRAM_API_URL}/editMessageText", json=params) as resp:
            return await resp.json()

async def delete_message(chat_id: int, message_id: int):
    import aiohttp
    params = {
        'chat_id': chat_id,
        'message_id': message_id
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{TELEGRAM_API_URL}/deleteMessage", json=params) as resp:
            return await resp.json()

async def handle_start(chat_id: int, user_id: int):
    session = get_or_create_session(user_id)
    session.reset_conversation()
    
    welcome_message = """🤖 **Welcome to Claude Telegram Bot!**

To start chatting with Claude, you need to authenticate:

**Option 1:** Enter the access password
**Option 2:** Enter your Claude API key (starts with 'sk-ant-')

Simply send your password or API key as the next message.

📝 **Commands:**
• `/start` - Start or restart the bot
• `/reset` - Clear conversation history
• `/help` - Show this help message

After authentication, just send any message to chat with Claude!"""
    
    await send_message(chat_id, welcome_message, parse_mode='Markdown')

async def handle_reset(chat_id: int, user_id: int):
    session = get_or_create_session(user_id)
    
    if not session.authenticated:
        await send_message(chat_id, "❌ Please authenticate first using /start")
        return
    
    session.reset_conversation()
    await send_message(chat_id, "✅ Conversation history cleared. Starting fresh!")

async def handle_help(chat_id: int):
    help_message = """📚 **Claude Telegram Bot Help**

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
• Conversations are not logged or saved"""
    
    await send_message(chat_id, help_message, parse_mode='Markdown')

async def handle_message(chat_id: int, user_id: int, message_text: str, message_id: int):
    session = get_or_create_session(user_id)
    
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
                await send_message(chat_id, "✅ **Authentication successful!**\n\nYou can now start chatting with Claude. Just send any message!", parse_mode='Markdown')
                logger.info(f"User {user_id} authenticated with API key")
            except Exception as e:
                await send_message(chat_id, "❌ Invalid API key. Please check and try again.")
                logger.error(f"API key validation failed for user {user_id}: {e}")
        
        elif MASTER_PASSWORD and session.authenticate_with_password(message_text):
            await send_message(chat_id, "✅ **Authentication successful!**\n\nYou can now start chatting with Claude. Just send any message!", parse_mode='Markdown')
            logger.info(f"User {user_id} authenticated with password")
        
        else:
            await send_message(chat_id, "❌ Invalid password or API key. Please try again or use /start to see options.")
        return
    
    if not session.claude_client:
        await send_message(chat_id, "❌ No Claude API key configured. Please restart with /start")
        return
    
    typing_msg = await send_message(chat_id, "🤔 Claude is thinking...")
    typing_msg_id = typing_msg.get('result', {}).get('message_id')
    
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
        
        if typing_msg_id:
            await delete_message(chat_id, typing_msg_id)
        
        if len(assistant_message) > 4096:
            chunks = [assistant_message[i:i+4096] for i in range(0, len(assistant_message), 4096)]
            for chunk in chunks:
                await send_message(chat_id, chunk, parse_mode='Markdown')
        else:
            await send_message(chat_id, assistant_message, parse_mode='Markdown')
        
        logger.info(f"Successfully processed message for user {user_id}")
        
    except Exception as e:
        if typing_msg_id:
            await delete_message(chat_id, typing_msg_id)
        error_message = f"❌ Error: {str(e)}\n\nPlease try again or use /reset to clear the conversation."
        await send_message(chat_id, error_message)
        logger.error(f"Error processing message for user {user_id}: {e}")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            update = json.loads(post_data.decode('utf-8'))
            
            # Clean old sessions periodically
            clean_old_sessions()
            
            # Handle the update asynchronously
            asyncio.run(self.process_update(update))
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'Error')
    
    async def process_update(self, update):
        if 'message' not in update:
            return
        
        message = update['message']
        chat_id = message['chat']['id']
        user_id = message['from']['id']
        message_id = message['message_id']
        text = message.get('text', '')
        
        if text == '/start':
            await handle_start(chat_id, user_id)
        elif text == '/reset':
            await handle_reset(chat_id, user_id)
        elif text == '/help':
            await handle_help(chat_id)
        elif not text.startswith('/'):
            await handle_message(chat_id, user_id, text, message_id)
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Claude Telegram Bot is running!')