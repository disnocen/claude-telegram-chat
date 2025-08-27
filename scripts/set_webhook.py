#!/usr/bin/env python3
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
VERCEL_URL = os.getenv('VERCEL_URL', '')

if not BOT_TOKEN:
    print("Error: BOT_TOKEN not found in environment variables")
    sys.exit(1)

if not VERCEL_URL:
    VERCEL_URL = input("Enter your Vercel deployment URL (e.g., https://your-project.vercel.app): ")

webhook_url = f"{VERCEL_URL.rstrip('/')}/api/webhook"
telegram_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"

print(f"Setting webhook to: {webhook_url}")

response = requests.post(telegram_api_url, json={"url": webhook_url})
result = response.json()

if result.get('ok'):
    print("✅ Webhook set successfully!")
    print(f"Description: {result.get('description', '')}")
    
    # Get webhook info
    info_response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo")
    info = info_response.json()
    
    if info.get('ok'):
        webhook_info = info.get('result', {})
        print("\nWebhook Info:")
        print(f"  URL: {webhook_info.get('url')}")
        print(f"  Has certificate: {webhook_info.get('has_custom_certificate')}")
        print(f"  Pending updates: {webhook_info.get('pending_update_count')}")
        if webhook_info.get('last_error_message'):
            print(f"  Last error: {webhook_info.get('last_error_message')}")
else:
    print("❌ Failed to set webhook!")
    print(f"Error: {result.get('description', 'Unknown error')}")
    sys.exit(1)