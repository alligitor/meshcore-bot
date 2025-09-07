#!/usr/bin/env python3
"""
Prefix command for the MeshCore Bot
Handles repeater prefix lookups using the w0z.is API
"""

import asyncio
import aiohttp
import time
import json
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
        return "Look up repeaters by two-character prefix. Usage: 'prefix 1A' or 'prefix 82'. Use 'prefix refresh' to update the cache."
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the prefix command"""
        content = message.content.strip()
        
        # Handle exclamation prefix
        if content.startswith('!'):
            content = content[1:].strip()
        
        # Parse the command
        parts = content.split()
        if len(parts) < 2:
            response = "Usage: prefix <two-character-prefix> (e.g., 'prefix 1A') or 'prefix refresh'"
            return await self.send_response(message, response)
        
        command = parts[1].upper()
        
        # Handle refresh command
        if command == "REFRESH":
            await self.refresh_cache()
            response = "🔄 Repeater prefix cache refreshed!"
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
        """Get prefix data from cache or API"""
        # Check if cache is valid
        current_time = time.time()
        if current_time - self.cache_timestamp > self.cache_duration:
            await self.refresh_cache()
        
        # Return cached data for the prefix
        return self.cache_data.get(prefix)
    
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
    
    def format_prefix_response(self, prefix: str, data: Dict[str, Any]) -> str:
        """Format the prefix response"""
        node_count = data['node_count']
        node_names = data['node_names']
        
        response = f"📡 **Prefix {prefix}** ({node_count} repeater{'s' if node_count != 1 else ''}):\n"
        
        for i, name in enumerate(node_names, 1):
            response += f"{i}. {name}\n"
        
        # Add cache info
        cache_age = int(time.time() - self.cache_timestamp)
        if cache_age < 60:
            cache_info = f"{cache_age}s ago"
        elif cache_age < 3600:
            cache_info = f"{cache_age // 60}m ago"
        else:
            cache_info = f"{cache_age // 3600}h ago"
        
        response += f"\n💾 Cache updated {cache_info}"
        
        return response
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
