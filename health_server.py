#!/usr/bin/env python3
import asyncio
from aiohttp import web
import logging

logger = logging.getLogger(__name__)

class HealthServer:
    def __init__(self, port=8080):
        self.port = port
        self.app = web.Application()
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/', self.health_check)
        self.runner = None
        self.bot_status = "starting"
    
    async def health_check(self, request):
        return web.json_response({
            "status": "healthy",
            "bot_status": self.bot_status,
            "service": "claude-telegram-bot"
        })
    
    def set_bot_status(self, status):
        self.bot_status = status
    
    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"Health check server running on port {self.port}")
    
    async def stop(self):
        if self.runner:
            await self.runner.cleanup()