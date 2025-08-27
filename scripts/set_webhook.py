#!/usr/bin/env python3
import os
import sys
import requests
import argparse
from dotenv import load_dotenv

load_dotenv()

def set_webhook(bot_token: str, webhook_url: str, secret_token: str = None):
    """Set webhook for Telegram bot"""
    telegram_api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    
    payload = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token
    
    print(f"Setting webhook to: {webhook_url}")
    if secret_token:
        print(f"Using secret token: {secret_token[:10]}...")
    
    response = requests.post(telegram_api_url, json=payload)
    result = response.json()
    
    if result.get('ok'):
        print("✅ Webhook set successfully!")
        print(f"Description: {result.get('description', '')}")
        return True
    else:
        print("❌ Failed to set webhook!")
        print(f"Error: {result.get('description', 'Unknown error')}")
        return False

def get_webhook_info(bot_token: str):
    """Get current webhook information"""
    info_response = requests.get(f"https://api.telegram.org/bot{bot_token}/getWebhookInfo")
    info = info_response.json()
    
    if info.get('ok'):
        webhook_info = info.get('result', {})
        print("\n📋 Current Webhook Info:")
        print(f"  URL: {webhook_info.get('url', 'Not set')}")
        print(f"  Has certificate: {webhook_info.get('has_custom_certificate', False)}")
        print(f"  Pending updates: {webhook_info.get('pending_update_count', 0)}")
        print(f"  Max connections: {webhook_info.get('max_connections', 0)}")
        print(f"  Allowed updates: {webhook_info.get('allowed_updates', 'All')}")
        
        if webhook_info.get('last_error_date'):
            from datetime import datetime
            error_date = datetime.fromtimestamp(webhook_info['last_error_date'])
            print(f"  Last error date: {error_date}")
            
        if webhook_info.get('last_error_message'):
            print(f"  Last error: {webhook_info.get('last_error_message')}")
        
        if webhook_info.get('last_synchronization_error_date'):
            sync_error_date = datetime.fromtimestamp(webhook_info['last_synchronization_error_date'])
            print(f"  Last sync error: {sync_error_date}")
    else:
        print("❌ Failed to get webhook info!")
        print(f"Error: {info.get('description', 'Unknown error')}")

def delete_webhook(bot_token: str):
    """Delete webhook (switch to polling)"""
    response = requests.post(f"https://api.telegram.org/bot{bot_token}/deleteWebhook")
    result = response.json()
    
    if result.get('ok'):
        print("✅ Webhook deleted successfully!")
        print("Bot is now in polling mode")
        return True
    else:
        print("❌ Failed to delete webhook!")
        print(f"Error: {result.get('description', 'Unknown error')}")
        return False

def test_webhook(webhook_url: str):
    """Test if webhook endpoint is accessible"""
    try:
        response = requests.get(webhook_url, timeout=10)
        if response.status_code == 200:
            print(f"✅ Webhook endpoint is accessible: {response.status_code}")
            return True
        else:
            print(f"⚠️ Webhook endpoint returned: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ Webhook endpoint is not accessible: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Manage Telegram Bot Webhook')
    parser.add_argument('--info', action='store_true', help='Show webhook info')
    parser.add_argument('--delete', action='store_true', help='Delete webhook')
    parser.add_argument('--test', action='store_true', help='Test webhook endpoint')
    parser.add_argument('--url', help='Webhook URL')
    parser.add_argument('--secret', help='Secret token for webhook security')
    
    args = parser.parse_args()
    
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN not found in environment variables")
        print("Make sure you have BOT_TOKEN set in your .env file")
        sys.exit(1)
    
    # Show webhook info
    if args.info:
        get_webhook_info(BOT_TOKEN)
        return
    
    # Delete webhook
    if args.delete:
        delete_webhook(BOT_TOKEN)
        return
    
    # Get webhook URL
    webhook_url = args.url or os.getenv('VERCEL_URL', '')
    if not webhook_url:
        webhook_url = input("Enter your Vercel deployment URL (e.g., https://your-project.vercel.app): ")
    
    webhook_url = f"{webhook_url.rstrip('/')}/api/webhook"
    
    # Test webhook endpoint if requested
    if args.test:
        test_webhook(webhook_url)
        return
    
    # Set webhook
    secret_token = args.secret or os.getenv('WEBHOOK_SECRET')
    if set_webhook(BOT_TOKEN, webhook_url, secret_token):
        get_webhook_info(BOT_TOKEN)

if __name__ == '__main__':
    main()