#!/usr/bin/env python3
"""
Joke command for the MeshCore Bot
Provides clean, family-friendly jokes from the JokeAPI
"""

import aiohttp
import asyncio
from .base_command import BaseCommand
from ..models import MeshMessage


class JokeCommand(BaseCommand):
    """Handles joke commands with category support"""
    
    # Plugin metadata
    name = "joke"
    keywords = ['joke', 'jokes']
    description = "Get a random joke or joke from specific category (usage: joke [category])"
    category = "entertainment"
    cooldown_seconds = 3  # 3 second cooldown per user to prevent API abuse
    requires_dm = False  # Works in both channels and DMs
    
    # Supported categories
    SUPPORTED_CATEGORIES = {
        'programming': 'Programming',
        'misc': 'Miscellaneous', 
        'miscellaneous': 'Miscellaneous',
        'dark': 'Dark',
        'pun': 'Pun',
        'spooky': 'Spooky',
        'christmas': 'Christmas'
    }
    
    # API configuration
    JOKE_API_BASE = "https://v2.jokeapi.dev/joke"
    BLACKLIST_FLAGS = "nsfw,religious,political,racist,sexist,explicit"
    TIMEOUT = 10  # seconds
    
    def __init__(self, bot):
        super().__init__(bot)
        
        # Per-user cooldown tracking
        self.user_cooldowns = {}  # user_id -> last_execution_time
        
        # Load configuration
        self.joke_enabled = bot.config.getboolean('Bot', 'joke_enabled', fallback=True)
        self.seasonal_jokes = bot.config.getboolean('Bot', 'seasonal_jokes', fallback=True)
    
    def get_help_text(self) -> str:
        categories = ", ".join(self.SUPPORTED_CATEGORIES.keys())
        return f"Usage: joke [category] - Get a random joke or from categories: {categories}"
    
    def matches_keyword(self, message: MeshMessage) -> bool:
        """Check if message starts with a joke keyword"""
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
        # Check if joke command is enabled
        if not self.joke_enabled:
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
            remaining = self.cooldown_seconds - elapsed
            return max(0, int(remaining))
        
        return 0
    
    def _record_execution(self, user_id: str):
        """Record the execution time for a specific user"""
        import time
        self.user_cooldowns[user_id] = time.time()
    
    def get_seasonal_default(self) -> str:
        """Get the seasonal default category based on current month"""
        if not self.seasonal_jokes:
            return None
        
        try:
            from datetime import datetime
            current_month = datetime.now().month
            
            if current_month == 10:  # October
                return "Spooky"
            elif current_month == 12:  # December
                return "Christmas"
            else:
                return None  # No seasonal default for other months
                
        except Exception as e:
            self.logger.error(f"Error getting seasonal default: {e}")
            return None
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the joke command"""
        content = message.content.strip()
        
        # Parse the command to extract category
        parts = content.split()
        if len(parts) < 2:
            # No category specified, check for seasonal defaults
            category = self.get_seasonal_default()
        else:
            # Category specified
            category_input = parts[1].lower()
            category = self.SUPPORTED_CATEGORIES.get(category_input)
            
            if category is None:
                # Invalid category
                categories = ", ".join(self.SUPPORTED_CATEGORIES.keys())
                await self.send_response(message, f"Invalid category. Available categories: {categories}")
                return True
        
        try:
            # Record execution for this user
            self._record_execution(message.sender_id)
            
            # Get joke from API
            joke_data = await self.get_joke_from_api(category)
            
            if joke_data is None:
                if category and category.lower() in ['dark']:
                    await self.send_response(message, f"Sorry, no {category.lower()} jokes are available right now. Try again later!")
                else:
                    await self.send_response(message, "Sorry, couldn't fetch a joke right now. Try again later!")
                return True
            
            # Format and send the joke
            joke_text = self.format_joke(joke_data)
            await self.send_response(message, joke_text)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in joke command: {e}")
            await self.send_response(message, "Sorry, something went wrong getting a joke!")
            return True
    
    async def get_joke_from_api(self, category: str = None) -> dict:
        """Get a joke from the JokeAPI"""
        try:
            # Build the API URL
            # For dark jokes, don't use safe-mode since users expect dark humor
            # For other categories, use safe-mode to ensure family-friendly content
            if category and category.lower() == 'dark':
                url = f"{self.JOKE_API_BASE}/{category}?blacklistFlags={self.BLACKLIST_FLAGS}"
            else:
                url = f"{self.JOKE_API_BASE}/{category or 'Any'}?blacklistFlags={self.BLACKLIST_FLAGS}&safe-mode"
            
            self.logger.debug(f"Fetching joke from: {url}")
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check if the API returned an error
                        if data.get('error', False):
                            self.logger.warning(f"JokeAPI returned error: {data.get('message', 'Unknown error')}")
                            return None
                        
                        # Check flags to ensure it's clean (always check blacklist flags)
                        flags = data.get('flags', {})
                        if any(flags.get(flag, False) for flag in ['nsfw', 'religious', 'political', 'racist', 'sexist', 'explicit']):
                            self.logger.warning("JokeAPI returned flagged joke, skipping")
                            return None
                        
                        # For dark jokes, we allow safe: false since users expect dark humor
                        # For other categories, we require safe: true (when not using safe-mode)
                        if category and category.lower() == 'dark':
                            # Dark jokes can have safe: false, just check blacklist flags
                            self.logger.debug("Dark joke accepted (safe: false allowed for dark humor)")
                        else:
                            # For non-dark jokes, ensure they're safe
                            if not data.get('safe', False):
                                self.logger.warning("JokeAPI returned unsafe joke for non-dark category, skipping")
                                return None
                        
                        return data
                    elif response.status == 400:
                        # 400 error usually means no jokes available for this category
                        self.logger.info(f"No jokes available for category: {category}")
                        return None
                    else:
                        self.logger.error(f"JokeAPI returned status {response.status}")
                        return None
                        
        except asyncio.TimeoutError:
            self.logger.error("Timeout fetching joke from JokeAPI")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching joke from JokeAPI: {e}")
            return None
    
    def format_joke(self, joke_data: dict) -> str:
        """Format the joke data into a readable string"""
        try:
            joke_type = joke_data.get('type', 'single')
            
            if joke_type == 'twopart':
                # Two-part joke (setup + delivery)
                setup = joke_data.get('setup', '')
                delivery = joke_data.get('delivery', '')
                
                if setup and delivery:
                    return f"🎭 {setup}\n\n{delivery}"
                else:
                    return f"🎭 {setup or delivery}"
            
            elif joke_type == 'single':
                # Single joke
                joke = joke_data.get('joke', '')
                
                if joke:
                    return f"🎭 {joke}"
                else:
                    return "🎭 No joke content available"
            
            else:
                # Unknown type, try to extract any text
                joke_text = joke_data.get('joke', '') or joke_data.get('setup', '') or joke_data.get('delivery', '')
                if joke_text:
                    return f"🎭 {joke_text}"
                else:
                    return "🎭 No joke content available"
                    
        except Exception as e:
            self.logger.error(f"Error formatting joke: {e}")
            return "🎭 Sorry, couldn't format the joke properly!"
