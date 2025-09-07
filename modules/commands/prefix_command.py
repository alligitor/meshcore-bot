#!/usr/bin/env python3
"""
Prefix command for the MeshCore Bot
Handles repeater prefix lookups using the w0z.is API
"""

import asyncio
import aiohttp
import time
import json
import random
from typing import Dict, List, Optional, Any
from .base_command import BaseCommand
from ..models import MeshMessage


class PrefixCommand(BaseCommand):
    """Handles repeater prefix lookups"""
    
    # Plugin metadata
    name = "prefix"
    keywords = ['prefix', 'repeater', 'lookup']
    description = "Look up repeaters by two-character prefix (e.g., 'prefix 1A')"
    category = "meshcore_info"
    requires_dm = False
    cooldown_seconds = 2
    
    def __init__(self, bot):
        super().__init__(bot)
        # Get API URL from config, with fallback to default
        self.api_url = self.bot.config.get('External_Data', 'repeater_prefix_api_url', 
                                          fallback="https://map.w0z.is/api/stats/repeater-prefixes?region=seattle")
        self.cache_data = {}
        self.cache_timestamp = 0
        # Get cache duration from config, with fallback to 1 hour
        self.cache_duration = self.bot.config.getint('External_Data', 'repeater_prefix_cache_hours', fallback=1) * 3600
        self.session = None
    
    def get_help_text(self) -> str:
        return "Look up repeaters by two-character prefix. Uses API data with local database fallback. Usage: 'prefix 1A', 'prefix free' (list available prefixes), or 'prefix refresh'."
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the prefix command"""
        content = message.content.strip()
        
        # Handle exclamation prefix
        if content.startswith('!'):
            content = content[1:].strip()
        
        # Parse the command
        parts = content.split()
        if len(parts) < 2:
            response = "Usage: prefix <two-character-prefix> (e.g., 'prefix 1A'), 'prefix free', or 'prefix refresh'"
            return await self.send_response(message, response)
        
        command = parts[1].upper()
        
        # Handle refresh command
        if command == "REFRESH":
            await self.refresh_cache()
            response = "🔄 Repeater prefix cache refreshed!"
            return await self.send_response(message, response)
        
        # Handle free command
        if command == "FREE":
            free_prefixes = await self.get_free_prefixes()
            if free_prefixes:
                response = self.format_free_prefixes_response(free_prefixes)
            else:
                response = "❌ Unable to determine free prefixes. Try 'prefix refresh' first."
            return await self.send_response(message, response)
        
        # Validate prefix format
        if len(command) != 2 or not command.isalnum():
            response = "❌ Invalid prefix format. Use two characters (e.g., '1A', '82', 'BD')"
            return await self.send_response(message, response)
        
        # Get prefix data
        prefix_data = await self.get_prefix_data(command)
        
        if prefix_data is None:
            response = f"❌ No repeaters found with prefix '{command}'"
            return await self.send_response(message, response)
        
        # Format response
        response = self.format_prefix_response(command, prefix_data)
        return await self.send_response(message, response)
    
    async def get_prefix_data(self, prefix: str) -> Optional[Dict[str, Any]]:
        """Get prefix data from cache, API, or database fallback"""
        # Check if cache is valid
        current_time = time.time()
        if current_time - self.cache_timestamp > self.cache_duration:
            await self.refresh_cache()
        
        # Return cached data for the prefix if available
        if prefix in self.cache_data:
            return self.cache_data.get(prefix)
        
        # Fallback to database if API cache is empty or prefix not found
        return await self.get_prefix_data_from_db(prefix)
    
    async def refresh_cache(self):
        """Refresh the cache from the API"""
        try:
            self.logger.info("Refreshing repeater prefix cache from API")
            
            # Create session if it doesn't exist
            if self.session is None:
                self.session = aiohttp.ClientSession()
            
            # Fetch data from API
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(self.api_url, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Clear existing cache
                    self.cache_data.clear()
                    
                    # Process and cache the data
                    for item in data.get('data', []):
                        prefix = item.get('prefix', '').upper()
                        if prefix:
                            self.cache_data[prefix] = {
                                'node_count': int(item.get('node_count', 0)),
                                'node_names': item.get('node_names', [])
                            }
                    
                    self.cache_timestamp = time.time()
                    self.logger.info(f"Cache refreshed with {len(self.cache_data)} prefixes")
                    
                else:
                    self.logger.error(f"API request failed with status {response.status}")
                    
        except asyncio.TimeoutError:
            self.logger.error("API request timed out")
        except aiohttp.ClientError as e:
            self.logger.error(f"API request failed: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse API response: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error refreshing cache: {e}")
    
    async def get_prefix_data_from_db(self, prefix: str) -> Optional[Dict[str, Any]]:
        """Get prefix data from the bot's SQLite database as fallback"""
        try:
            self.logger.info(f"Looking up prefix '{prefix}' in local database")
            
            # Query the repeater_contacts table for repeaters with matching prefix
            query = '''
                SELECT name, public_key, device_type, last_seen
                FROM repeater_contacts 
                WHERE is_active = 1 
                AND public_key LIKE ?
                ORDER BY name
            '''
            
            # The prefix should match the first two characters of the public key
            prefix_pattern = f"{prefix}%"
            
            results = self.bot.db_manager.execute_query(query, (prefix_pattern,))
            
            if not results:
                self.logger.info(f"No repeaters found in database with prefix '{prefix}'")
                return None
            
            # Extract node names and count
            node_names = []
            for row in results:
                name = row['name']
                device_type = row['device_type']
                # Add device type indicator for clarity
                if device_type == 2:
                    name += " (Repeater)"
                elif device_type == 3:
                    name += " (Room Server)"
                node_names.append(name)
            
            self.logger.info(f"Found {len(node_names)} repeaters in database with prefix '{prefix}'")
            
            return {
                'node_count': len(node_names),
                'node_names': node_names,
                'source': 'database'
            }
            
        except Exception as e:
            self.logger.error(f"Error querying database for prefix '{prefix}': {e}")
            return None
    
    async def get_free_prefixes(self) -> List[str]:
        """Get list of available (unused) prefixes"""
        try:
            # Get all used prefixes from both API cache and database
            used_prefixes = set()
            
            # Always try to refresh cache if it's empty or stale
            current_time = time.time()
            if not self.cache_data or current_time - self.cache_timestamp > self.cache_duration:
                self.logger.info("Refreshing cache for free prefixes lookup")
                await self.refresh_cache()
            
            # Add prefixes from API cache
            for prefix in self.cache_data.keys():
                used_prefixes.add(prefix.upper())
            
            self.logger.info(f"Found {len(used_prefixes)} used prefixes from API cache")
            
            # Add prefixes from database
            try:
                query = '''
                    SELECT DISTINCT SUBSTR(public_key, 1, 2) as prefix
                    FROM repeater_contacts 
                    WHERE is_active = 1 
                    AND LENGTH(public_key) >= 2
                '''
                results = self.bot.db_manager.execute_query(query)
                for row in results:
                    prefix = row['prefix'].upper()
                    if len(prefix) == 2:
                        used_prefixes.add(prefix)
            except Exception as e:
                self.logger.warning(f"Error getting prefixes from database: {e}")
            
            # Generate all valid hex prefixes (01-FE, excluding 00 and FF)
            all_prefixes = []
            for i in range(1, 255):  # 1 to 254 (exclude 0 and 255)
                prefix = f"{i:02X}"
                all_prefixes.append(prefix)
            
            # Find free prefixes
            free_prefixes = []
            for prefix in all_prefixes:
                if prefix not in used_prefixes:
                    free_prefixes.append(prefix)
            
            self.logger.info(f"Found {len(free_prefixes)} free prefixes out of {len(all_prefixes)} total valid prefixes")
            
            # Randomly select up to 10 free prefixes
            if len(free_prefixes) <= 10:
                return free_prefixes
            else:
                return random.sample(free_prefixes, 10)
            
        except Exception as e:
            self.logger.error(f"Error getting free prefixes: {e}")
            return []
    
    def format_free_prefixes_response(self, free_prefixes: List[str]) -> str:
        """Format the free prefixes response"""
        if not free_prefixes:
            return "❌ No free prefixes found (all 254 valid prefixes are in use)"
        
        response = f"🆓 **Available Prefixes** ({len(free_prefixes)} shown):\n"
        
        # Format as a grid for better readability
        for i, prefix in enumerate(free_prefixes, 1):
            response += f"{prefix}"
            if i % 5 == 0:  # New line every 5 prefixes
                response += "\n"
            elif i < len(free_prefixes):  # Add space if not the last item
                response += " "
        
        # Add newline if the last line wasn't complete
        if len(free_prefixes) % 5 != 0:
            response += "\n"
        
        response += f"\n💡 Use 'prefix <XX>' to check if a prefix is available"
        
        return response
    
    def format_prefix_response(self, prefix: str, data: Dict[str, Any]) -> str:
        """Format the prefix response"""
        node_count = data['node_count']
        node_names = data['node_names']
        source = data.get('source', 'api')
        
        # Get bot name for database responses
        bot_name = self.bot.config.get('Bot', 'bot_name', fallback='Bot')
        
        if source == 'database':
            # Database response format
            response = f"{bot_name} has heard {node_count} repeater{'s' if node_count != 1 else ''} with prefix {prefix}:\n"
        else:
            # API response format
            response = f"📡 Prefix {prefix} ({node_count} repeater{'s' if node_count != 1 else ''}):\n"
        
        for i, name in enumerate(node_names, 1):
            response += f"{i}. {name}\n"
        
        # Add source info
        if source == 'database':
            # No additional info needed for database responses
            pass
        else:
            # Add API source info - extract domain from API URL
            try:
                from urllib.parse import urlparse
                parsed_url = urlparse(self.api_url)
                domain = parsed_url.netloc
                response += f"\nSource: {domain}"
            except Exception:
                # Fallback if URL parsing fails
                response += f"\nSource: API"
        
        return response
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
