#!/usr/bin/env python3
"""
Dad Joke Command for MeshCore Bot
Fetches dad jokes from icanhazdadjoke.com API
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any
from .base_command import BaseCommand
from ..models import MeshMessage

logger = logging.getLogger("MeshCoreBot")

class DadJokeCommand(BaseCommand):
    """Handles dad joke commands using icanhazdadjoke.com API"""
    
    # Plugin metadata
    name = "dadjoke"
    keywords = ['dadjoke', 'dad joke', 'dadjokes', 'dad jokes']
    description = "Get a random dad joke from icanhazdadjoke.com"
    category = "fun"
    cooldown_seconds = 3
    
    # API configuration
    DAD_JOKE_API_URL = "https://icanhazdadjoke.com/"
    TIMEOUT = 10  # seconds
    
    def __init__(self, bot):
        super().__init__(bot)
        
        # Per-user cooldown tracking
        self.user_cooldowns = {}  # user_id -> last_execution_time
        
        # Load configuration
        self.dadjoke_enabled = bot.config.getboolean('Bot', 'dadjoke_enabled', fallback=True)
    
    def get_help_text(self) -> str:
        return "Usage: dadjoke - Get a random dad joke"
    
    def matches_keyword(self, message: MeshMessage) -> bool:
        """Check if message starts with a dad joke keyword"""
        content = message.content.strip()
        if content.startswith('!'):
            content = content[1:].strip()
        content_lower = content.lower()
        for keyword in self.keywords:
            # Match if keyword is at start followed by space or end of message
            if content_lower == keyword or content_lower.startswith(keyword + ' '):
                return True
        return False
    
    def can_execute(self, message: MeshMessage) -> bool:
        """Override cooldown check to be per-user instead of per-command-instance"""
        # Check if dadjoke command is enabled
        if not self.dadjoke_enabled:
            return False
        
        # Check if command requires DM and message is not DM
        if self.requires_dm and not message.is_dm:
            return False
        
        # Check per-user cooldown
        if self.cooldown_seconds > 0:
            import time
            current_time = time.time()
            user_id = message.sender_id
            
            if user_id in self.user_cooldowns:
                last_execution = self.user_cooldowns[user_id]
                if (current_time - last_execution) < self.cooldown_seconds:
                    return False
        
        return True
    
    def get_remaining_cooldown(self, user_id: str) -> int:
        """Get remaining cooldown time for a specific user"""
        if self.cooldown_seconds <= 0:
            return 0
        
        import time
        current_time = time.time()
        if user_id in self.user_cooldowns:
            last_execution = self.user_cooldowns[user_id]
            elapsed = current_time - last_execution
            if elapsed < self.cooldown_seconds:
                remaining = self.cooldown_seconds - elapsed
                return max(0, int(remaining))
        
        return 0
    
    def _record_execution(self, user_id: str):
        """Record the execution time for a specific user"""
        import time
        self.user_cooldowns[user_id] = time.time()
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the dad joke command"""
        try:
            # Record execution for this user
            self._record_execution(message.sender_id)
            
            # Get dad joke from API
            joke_data = await self.get_dad_joke_from_api()
            
            if joke_data is None:
                await self.send_response(message, "Sorry, couldn't fetch a dad joke right now. Try again later!")
                return True
            
            # Format and send the joke
            joke_text = self.format_dad_joke(joke_data)
            await self.send_response(message, joke_text)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in dad joke command: {e}")
            await self.send_response(message, "Sorry, something went wrong getting a dad joke!")
            return True
    
    async def get_dad_joke_from_api(self) -> Optional[Dict[str, Any]]:
        """Get a dad joke from icanhazdadjoke.com API"""
        try:
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'MeshCoreBot (https://github.com/adam/meshcore-bot)'
            }
            
            self.logger.debug(f"Fetching dad joke from: {self.DAD_JOKE_API_URL}")
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.DAD_JOKE_API_URL, 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check if the API returned an error
                        if data.get('status') != 200:
                            self.logger.warning(f"Dad joke API returned error status: {data.get('status')}")
                            return None
                        
                        # Validate required fields
                        if not data.get('joke'):
                            self.logger.warning("Dad joke API returned joke without content")
                            return None
                        
                        return data
                    else:
                        self.logger.error(f"Dad joke API returned status {response.status}")
                        return None
                        
        except asyncio.TimeoutError:
            self.logger.error("Timeout fetching dad joke from API")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching dad joke from API: {e}")
            return None
    
    def format_dad_joke(self, joke_data: Dict[str, Any]) -> str:
        """Format the dad joke data into a readable string"""
        try:
            joke = joke_data.get('joke', '')
            
            if joke:
                return f"🥸 {joke}"
            else:
                return "🥸 No dad joke content available"
                    
        except Exception as e:
            self.logger.error(f"Error formatting dad joke: {e}")
            return "🥸 Sorry, couldn't format the dad joke properly!"
