#!/usr/bin/env python3
import os
import json
import logging
import hmac
import hashlib
from typing import Dict, Optional
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
import asyncio
import requests

load_dotenv()

log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, log_level.upper(), logging.INFO)
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
MASTER_PASSWORD = os.getenv('MASTER_PASSWORD')
DEFAULT_CLAUDE_API_KEY = os.getenv('DEFAULT_CLAUDE_API_KEY')
MAX_CONVERSATION_LENGTH = int(os.getenv('MAX_CONVERSATION_LENGTH', '20'))
SESSION_TIMEOUT_HOURS = int(os.getenv('SESSION_TIMEOUT_HOURS', '24'))
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# Simple file-based session storage for Vercel
class SessionStorage:
    def __init__(self):
        self.sessions_file = "/tmp/user_sessions.json"
        self._load_sessions()
    
    def _load_sessions(self):
        try:
            with open(self.sessions_file, 'r') as f:
                data = json.load(f)
                # Convert back to UserSession objects
                self.sessions = {}
                for user_id, session_data in data.items():
                    session = UserSession(int(user_id))
                    session.__dict__.update(session_data)
                    # Recreate Claude client if API key exists
                    if session.api_key:
                        session.claude_client = AsyncAnthropic(api_key=session.api_key)
                    self.sessions[int(user_id)] = session
        except (FileNotFoundError, json.JSONDecodeError):
            self.sessions = {}
    
    def _save_sessions(self):
        # Convert sessions to JSON-serializable format
        data = {}
        for user_id, session in self.sessions.items():
            session_dict = session.__dict__.copy()
            # Remove non-serializable claude_client
            session_dict.pop('claude_client', None)
            # Convert datetime to ISO string
            if 'last_activity' in session_dict and isinstance(session_dict['last_activity'], datetime):
                session_dict['last_activity'] = session_dict['last_activity'].isoformat()
            data[str(user_id)] = session_dict
        
        try:
            with open(self.sessions_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")
    
    def get_session(self, user_id: int):
        return self.sessions.get(user_id)
    
    def create_session(self, user_id: int):
        session = UserSession(user_id)
        self.sessions[user_id] = session
        self._save_sessions()
        return session
    
    def update_session(self, user_id: int, session):
        self.sessions[user_id] = session
        self._save_sessions()
    
    def clean_old_sessions(self):
        current_time = datetime.now()
        expired_sessions = []
        
        for user_id, session in self.sessions.items():
            last_activity = session.last_activity
            if isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(last_activity)
            
            if current_time - last_activity > timedelta(hours=SESSION_TIMEOUT_HOURS):
                expired_sessions.append(user_id)
        
        for user_id in expired_sessions:
            del self.sessions[user_id]
        
        if expired_sessions:
            self._save_sessions()
            logger.info(f"Cleaned {len(expired_sessions)} expired sessions")

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

# Global session storage
storage = SessionStorage()

class TelegramAPI:
    @staticmethod
    def send_message(chat_id: int, text: str, parse_mode: str = None):
        params = {
            'chat_id': chat_id,
            'text': text[:4096]  # Telegram message limit
        }
        if parse_mode:
            params['parse_mode'] = parse_mode
        
        response = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=params)
        return response.json()
    
    @staticmethod
    def edit_message(chat_id: int, message_id: int, text: str):
        params = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text[:4096]
        }
        
        response = requests.post(f"{TELEGRAM_API_URL}/editMessageText", json=params)
        return response.json()
    
    @staticmethod
    def delete_message(chat_id: int, message_id: int):
        params = {
            'chat_id': chat_id,
            'message_id': message_id
        }
        
        response = requests.post(f"{TELEGRAM_API_URL}/deleteMessage", json=params)
        return response.json()

async def handle_start_command(chat_id: int, user_id: int):
    session = storage.get_session(user_id)
    if not session:
        session = storage.create_session(user_id)
    
    session.reset_conversation()
    storage.update_session(user_id, session)
    
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
    
    TelegramAPI.send_message(chat_id, welcome_message, parse_mode='Markdown')

async def handle_reset_command(chat_id: int, user_id: int):
    session = storage.get_session(user_id)
    if not session:
        session = storage.create_session(user_id)
    
    if not session.authenticated:
        TelegramAPI.send_message(chat_id, "❌ Please authenticate first using /start")
        return
    
    session.reset_conversation()
    storage.update_session(user_id, session)
    TelegramAPI.send_message(chat_id, "✅ Conversation history cleared. Starting fresh!")

async def handle_help_command(chat_id: int):
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
• Your API key is stored only temporarily
• Conversations are not logged permanently"""
    
    TelegramAPI.send_message(chat_id, help_message, parse_mode='Markdown')

async def handle_regular_message(chat_id: int, user_id: int, message_text: str, message_id: int):
    session = storage.get_session(user_id)
    if not session:
        session = storage.create_session(user_id)
    
    if not session.authenticated:
        # Handle authentication
        if message_text.startswith('sk-ant-'):
            try:
                # Test API key
                test_client = AsyncAnthropic(api_key=message_text)
                await test_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hi"}]
                )
                session.authenticate_with_api_key(message_text)
                storage.update_session(user_id, session)
                TelegramAPI.send_message(
                    chat_id, 
                    "✅ **Authentication successful!**\n\nYou can now start chatting with Claude. Just send any message!",
                    parse_mode='Markdown'
                )
                logger.info(f"User {user_id} authenticated with API key")
            except Exception as e:
                TelegramAPI.send_message(chat_id, "❌ Invalid API key. Please check and try again.")
                logger.error(f"API key validation failed for user {user_id}: {e}")
        
        elif MASTER_PASSWORD and session.authenticate_with_password(message_text):
            storage.update_session(user_id, session)
            TelegramAPI.send_message(
                chat_id,
                "✅ **Authentication successful!**\n\nYou can now start chatting with Claude. Just send any message!",
                parse_mode='Markdown'
            )
            logger.info(f"User {user_id} authenticated with password")
        
        else:
            TelegramAPI.send_message(
                chat_id, 
                "❌ Invalid password or API key. Please try again or use /start to see options."
            )
        return
    
    if not session.claude_client:
        TelegramAPI.send_message(chat_id, "❌ No Claude API key configured. Please restart with /start")
        return
    
    # Send thinking message
    thinking_response = TelegramAPI.send_message(chat_id, "🤔 Claude is thinking...")
    thinking_msg_id = thinking_response.get('result', {}).get('message_id')
    
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
        storage.update_session(user_id, session)
        
        # Delete thinking message
        if thinking_msg_id:
            TelegramAPI.delete_message(chat_id, thinking_msg_id)
        
        # Send response (split if too long)
        if len(assistant_message) > 4096:
            chunks = [assistant_message[i:i+4096] for i in range(0, len(assistant_message), 4096)]
            for chunk in chunks:
                TelegramAPI.send_message(chat_id, chunk, parse_mode='Markdown')
        else:
            TelegramAPI.send_message(chat_id, assistant_message, parse_mode='Markdown')
        
        logger.info(f"Successfully processed message for user {user_id}")
        
    except Exception as e:
        if thinking_msg_id:
            TelegramAPI.delete_message(chat_id, thinking_msg_id)
        error_message = f"❌ Error: {str(e)}\n\nPlease try again or use /reset to clear the conversation."
        TelegramAPI.send_message(chat_id, error_message)
        logger.error(f"Error processing message for user {user_id}: {e}")

def verify_webhook(request_body: bytes, signature: str) -> bool:
    """Verify that the request is from Telegram"""
    if not BOT_TOKEN:
        return False
    
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    expected_signature = hmac.new(secret_key, request_body, hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected_signature}", signature)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # Basic security check (optional - Telegram doesn't always send this header)
            telegram_signature = self.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
            
            # Parse the update
            try:
                update = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                logger.error("Invalid JSON in webhook")
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Invalid JSON')
                return
            
            # Clean old sessions periodically
            storage.clean_old_sessions()
            
            # Process the update
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
        
        logger.info(f"Processing message from user {user_id}: {text[:50]}...")
        
        if text == '/start':
            await handle_start_command(chat_id, user_id)
        elif text == '/reset':
            await handle_reset_command(chat_id, user_id)
        elif text == '/help':
            await handle_help_command(chat_id)
        elif not text.startswith('/'):
            await handle_regular_message(chat_id, user_id, text, message_id)
    
    def do_GET(self):
        # Health check endpoint
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Claude Telegram Bot Webhook is running!')