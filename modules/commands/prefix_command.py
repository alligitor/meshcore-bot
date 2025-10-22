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
from typing import Dict, List, Optional, Any, Tuple
from .base_command import BaseCommand
from ..models import MeshMessage
from ..utils import abbreviate_location, format_location_for_display


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
        # Get API URL from config, no fallback to regional API
        self.api_url = self.bot.config.get('External_Data', 'repeater_prefix_api_url', fallback="")
        self.cache_data = {}
        self.cache_timestamp = 0
        # Get cache duration from config, with fallback to 1 hour
        self.cache_duration = self.bot.config.getint('External_Data', 'repeater_prefix_cache_hours', fallback=1) * 3600
        self.session = None
        
        # Get geolocation settings from config
        self.show_repeater_locations = self.bot.config.getboolean('Prefix_Command', 'show_repeater_locations', fallback=True)
        self.use_reverse_geocoding = self.bot.config.getboolean('Prefix_Command', 'use_reverse_geocoding', fallback=True)
        self.hide_source = self.bot.config.getboolean('Prefix_Command', 'hide_source', fallback=False)
    
    def get_help_text(self) -> str:
        if not self.api_url or self.api_url.strip() == "":
            location_note = " (with city names)" if self.show_repeater_locations else ""
            return f"Look up repeaters by two-character prefix using local database{location_note}. Usage: 'prefix 1A', 'prefix free' (list available prefixes). Note: API disabled - using local data only."
        
        location_note = " (with city names)" if self.show_repeater_locations else ""
        return f"Look up repeaters by two-character prefix{location_note}. Usage: 'prefix 1A', 'prefix free' (list available prefixes), or 'prefix refresh'."
    
    def matches_keyword(self, message: MeshMessage) -> bool:
        """Check if message starts with 'prefix' keyword"""
        content = message.content.strip()
        
        # Handle exclamation prefix
        if content.startswith('!'):
            content = content[1:].strip()
        
        # Check if message starts with 'prefix' (with or without space)
        content_lower = content.lower()
        return content_lower == 'prefix' or content_lower.startswith('prefix ')
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the prefix command"""
        content = message.content.strip()
        
        # Handle exclamation prefix
        if content.startswith('!'):
            content = content[1:].strip()
        
        # Parse the command
        parts = content.split()
        if len(parts) < 2:
            response = self.get_help_text()
            return await self.send_response(message, response)
        
        command = parts[1].upper()
        
        # Handle refresh command
        if command == "REFRESH":
            if not self.api_url or self.api_url.strip() == "":
                response = "❌ Refresh not available - no API URL configured. Using local database only."
                return await self.send_response(message, response)
            await self.refresh_cache()
            response = "🔄 Repeater prefix cache refreshed!"
            return await self.send_response(message, response)
        
        # Handle free command
        if command == "FREE":
            free_prefixes, total_free = await self.get_free_prefixes()
            if free_prefixes:
                response = self.format_free_prefixes_response(free_prefixes, total_free)
            else:
                response = "❌ Unable to determine free prefixes. Try 'prefix refresh' first."
            return await self.send_response(message, response)
        
        # Validate prefix format
        if len(command) != 2 or not command.isalnum():
            response = "❌ Invalid prefix format. Use two characters (e.g., prefix 1A)"
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
        """Get prefix data from API first, enhanced with local database location data"""
        # Only refresh cache if API is configured
        if self.api_url and self.api_url.strip():
            current_time = time.time()
            if current_time - self.cache_timestamp > self.cache_duration:
                await self.refresh_cache()
        
        # Get API data first (prioritize comprehensive repeater data)
        api_data = None
        if self.api_url and self.api_url.strip() and prefix in self.cache_data:
            api_data = self.cache_data.get(prefix)
        
        # Get local database data for location enhancement
        db_data = await self.get_prefix_data_from_db(prefix)
        
        # If we have API data, enhance it with local location data
        if api_data and db_data:
            return self._enhance_api_data_with_locations(api_data, db_data)
        elif api_data:
            return api_data
        elif db_data:
            return db_data
        
        return None
    
    def _find_flexible_match(self, api_name: str, db_locations: Dict[str, str]) -> Optional[str]:
        """
        Find a flexible match for an API name in the database locations.
        
        Matching strategy:
        1. Exact match (highest priority)
        2. Version number variations (e.g., "Name v4" matches "Name")
        3. Partial match (e.g., "DN Field Repeater" matches "DN Field Repeater v4")
        
        Preserves numbered nodes (e.g., "Airhack 1" vs "Airhack 2" remain distinct)
        """
        # First try exact match
        if api_name in db_locations:
            return api_name
        
        # Try version number variations
        # Remove common version patterns: v1, v2, v3, v4, v5, etc.
        import re
        base_name = re.sub(r'\s+v\d+$', '', api_name, flags=re.IGNORECASE)
        
        if base_name != api_name:  # Version was removed
            # Try to find a database entry that matches the base name
            for db_name in db_locations.keys():
                if db_name.lower() == base_name.lower():
                    return db_name
                # Also try with version numbers
                for version in ['v1', 'v2', 'v3', 'v4', 'v5', 'v6', 'v7', 'v8', 'v9']:
                    versioned_name = f"{base_name} {version}"
                    if db_name.lower() == versioned_name.lower():
                        return db_name
        
        # Try partial matching (but be careful with numbered nodes)
        # Only do partial matching if the API name is shorter than the DB name
        # This helps with cases like "DN Field Repeater" matching "DN Field Repeater v4"
        for db_name in db_locations.keys():
            # Check if API name is a prefix of DB name (but not vice versa)
            if (len(api_name) < len(db_name) and 
                db_name.lower().startswith(api_name.lower()) and
                # Avoid matching numbered nodes (e.g., "Airhack" shouldn't match "Airhack 1")
                not re.search(r'\s+\d+$', api_name)):  # API name doesn't end with a number
                return db_name
        
        return None
    
    def _enhance_api_data_with_locations(self, api_data: Dict[str, Any], db_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance API data with location information from local database using flexible matching"""
        try:
            # Create a mapping of repeater names to location data from database
            db_locations = {}
            for db_repeater in db_data.get('node_names', []):
                # Extract name and location from database format: "Name (Location)"
                if ' (' in db_repeater and db_repeater.endswith(')'):
                    name, location = db_repeater.rsplit(' (', 1)
                    location = location.rstrip(')')
                    # Store just the city/neighborhood part (not full location)
                    db_locations[name] = location
                else:
                    # No location data in database
                    db_locations[db_repeater] = None
            
            # Enhance API node names with location data using flexible matching
            enhanced_names = []
            for api_name in api_data.get('node_names', []):
                # Try to find a flexible match
                matched_db_name = self._find_flexible_match(api_name, db_locations)
                
                if matched_db_name and db_locations[matched_db_name]:
                    # Use the API name but add location from database
                    enhanced_name = f"{api_name} ({db_locations[matched_db_name]})"
                else:
                    enhanced_name = api_name
                enhanced_names.append(enhanced_name)
            
            # Return enhanced API data
            enhanced_data = api_data.copy()
            enhanced_data['node_names'] = enhanced_names
            # Keep original source - we're just caching geocoding results
            
            return enhanced_data
            
        except Exception as e:
            self.logger.error(f"Error enhancing API data with locations: {e}")
            # Return original API data if enhancement fails
            return api_data
    
    async def refresh_cache(self):
        """Refresh the cache from the API"""
        try:
            # Check if API URL is configured
            if not self.api_url or self.api_url.strip() == "":
                self.logger.info("Repeater prefix API URL not configured - skipping API refresh")
                return
            
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
            
            # Query the complete_contact_tracking table for repeaters with matching prefix
            # Include inactive repeaters for location enhancement (they still have valid location data)
            query = '''
                SELECT name, public_key, device_type, last_heard as last_seen, latitude, longitude, city, state, country, role
                FROM complete_contact_tracking 
                WHERE public_key LIKE ? AND role IN ('repeater', 'roomserver')
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
                
                # Add location information if enabled and available
                if self.show_repeater_locations:
                    # Use the utility function to format location with abbreviation
                    location_str = format_location_for_display(
                        city=row['city'],
                        state=row['state'],
                        country=row['country'],
                        max_length=20  # Reasonable limit for location in prefix output
                    )
                    
                    # If we have coordinates but no city, try reverse geocoding
                    # Skip 0,0 coordinates as they indicate "hidden" location
                    if (not location_str and 
                        row['latitude'] is not None and 
                        row['longitude'] is not None and 
                        not (row['latitude'] == 0.0 and row['longitude'] == 0.0) and
                        self.use_reverse_geocoding):
                        try:
                            # Use the enhanced reverse geocoding from repeater manager
                            if hasattr(self.bot, 'repeater_manager'):
                                city = self.bot.repeater_manager._get_city_from_coordinates(
                                    row['latitude'], row['longitude']
                                )
                                if city:
                                    location_str = abbreviate_location(city, 20)
                            else:
                                # Fallback to basic geocoding
                                from geopy.geocoders import Nominatim
                                geolocator = Nominatim(user_agent="meshcore-bot")
                                location = geolocator.reverse(f"{row['latitude']}, {row['longitude']}")
                                if location:
                                    address = location.raw.get('address', {})
                                    # Try neighborhood first, then city, then town, etc.
                                    raw_location = (address.get('neighbourhood') or
                                                  address.get('suburb') or
                                                  address.get('city') or
                                                  address.get('town') or
                                                  address.get('village') or
                                                  address.get('hamlet') or
                                                  address.get('municipality'))
                                    if raw_location:
                                        location_str = abbreviate_location(raw_location, 20)
                        except Exception as e:
                            self.logger.debug(f"Error reverse geocoding {row['latitude']}, {row['longitude']}: {e}")
                    
                    # Add location to name if we have any location info
                    if location_str:
                        name += f" ({location_str})"
                
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
    
    async def get_free_prefixes(self) -> Tuple[List[str], int]:
        """Get list of available (unused) prefixes and total count"""
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
                    FROM complete_contact_tracking 
                    WHERE role IN ('repeater', 'roomserver')
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
            total_free = len(free_prefixes)
            if len(free_prefixes) <= 10:
                selected_prefixes = free_prefixes
            else:
                selected_prefixes = random.sample(free_prefixes, 10)
            
            return selected_prefixes, total_free
            
        except Exception as e:
            self.logger.error(f"Error getting free prefixes: {e}")
            return [], 0
    
    def format_free_prefixes_response(self, free_prefixes: List[str], total_free: int) -> str:
        """Format the free prefixes response"""
        if not free_prefixes:
            return "❌ No free prefixes found (all 254 valid prefixes are in use)"
        
        response = f"Available Prefixes ({len(free_prefixes)} of {total_free} free):\n"
        
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
        
        response += f"\n💡 Generate a custom key: https://gessaman.com/mc-keygen"
        
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
        
        # Add source info (unless hidden by config)
        if not self.hide_source:
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
        else:
            # Remove trailing newline when source is hidden
            response = response.rstrip('\n')
        
        return response
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
