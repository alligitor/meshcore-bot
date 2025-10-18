#!/usr/bin/env python3
"""
Path Decode Command for the MeshCore Bot
Decodes hex path data to show which repeaters were involved in message routing
"""

import re
import time
import asyncio
import math
from typing import List, Optional, Dict, Any, Tuple
from .base_command import BaseCommand
from ..models import MeshMessage


class PathCommand(BaseCommand):
    """Command for decoding path data to repeater names"""
    
    # Plugin metadata
    name = "path"
    keywords = ["path", "decode", "route"]
    description = "Decode hex path data to show which repeaters were involved in message routing"
    requires_dm = False
    cooldown_seconds = 1
    category = "meshcore_info"
    
    def __init__(self, bot):
        super().__init__(bot)
        # Get bot location from config for geographic proximity calculations
        # Check if geographic guessing is enabled (bot has location configured)
        self.geographic_guessing_enabled = False
        self.bot_latitude = None
        self.bot_longitude = None
        
        # Get proximity calculation method from config
        self.proximity_method = bot.config.get('Path_Command', 'proximity_method', fallback='simple')
        self.path_proximity_fallback = bot.config.getboolean('Path_Command', 'path_proximity_fallback', fallback=True)
        self.max_proximity_range = bot.config.getfloat('Path_Command', 'max_proximity_range', fallback=200.0)
        
        try:
            # Try to get location from Bot section
            if bot.config.has_section('Bot'):
                lat = bot.config.getfloat('Bot', 'bot_latitude', fallback=None)
                lon = bot.config.getfloat('Bot', 'bot_longitude', fallback=None)
                
                if lat is not None and lon is not None:
                    # Validate coordinates
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        self.bot_latitude = lat
                        self.bot_longitude = lon
                        self.geographic_guessing_enabled = True
                        self.logger.info(f"Geographic proximity guessing enabled with bot location: {lat:.4f}, {lon:.4f}")
                        self.logger.info(f"Proximity method: {self.proximity_method}")
                    else:
                        self.logger.warning(f"Invalid bot coordinates in config: {lat}, {lon}")
                else:
                    self.logger.info("Bot location not configured - geographic proximity guessing disabled")
            else:
                self.logger.info("Bot section not found - geographic proximity guessing disabled")
        except Exception as e:
            self.logger.warning(f"Error reading bot location from config: {e} - geographic proximity guessing disabled")
    
    def matches_keyword(self, message: MeshMessage) -> bool:
        """Check if message starts with 'path' keyword"""
        content = message.content.strip()
        
        # Handle exclamation prefix
        if content.startswith('!'):
            content = content[1:].strip()
        
        # Check if message starts with any of our keywords
        content_lower = content.lower()
        for keyword in self.keywords:
            # Check for exact match or keyword followed by space
            if content_lower == keyword or content_lower.startswith(keyword + ' '):
                return True
        return False
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute path decode command"""
        self.logger.info(f"Path command executed with content: {message.content}")
        
        # Store the current message for use in _extract_path_from_recent_messages
        self._current_message = message
        
        # Parse the message content to extract path data
        content = message.content.strip()
        parts = content.split()
        
        if len(parts) < 2:
            # No arguments provided - try to extract path from current message
            response = await self._extract_path_from_recent_messages()
        else:
            # Extract path data from the command
            path_input = " ".join(parts[1:])
            response = await self._decode_path(path_input)
        
        # Send the response (may be split into multiple messages if long)
        await self._send_path_response(message, response)
        return True
    
    async def _decode_path(self, path_input: str) -> str:
        """Decode hex path data to repeater names"""
        try:
            # Parse the path input - handle various formats
            # Examples: "11,98,a4,49,cd,5f,01" or "11 98 a4 49 cd 5f 01" or "1198a449cd5f01"
            path_input = path_input.replace(',', ' ').replace(':', ' ')
            
            # Extract hex values using regex
            hex_pattern = r'[0-9a-fA-F]{2}'
            hex_matches = re.findall(hex_pattern, path_input)
            
            if not hex_matches:
                return "❌ No valid hex values found in path data. Use format like: 11,98,a4,49,cd,5f,01"
            
            # Convert to uppercase for consistency
            # hex_matches preserves the order from the original path
            node_ids = [match.upper() for match in hex_matches]
            
            self.logger.info(f"Decoding path with {len(node_ids)} nodes: {','.join(node_ids)}")
            
            # Look up repeater names for each node ID (order preserved)
            repeater_info = await self._lookup_repeater_names(node_ids)
            
            # Format the response
            return self._format_path_response(node_ids, repeater_info)
            
        except Exception as e:
            self.logger.error(f"Error decoding path: {e}")
            return f"❌ Error decoding path: {e}"
    
    async def _lookup_repeater_names(self, node_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Look up repeater names for given node IDs"""
        repeater_info = {}
        
        try:
            # First try to get data from API cache (like prefix command does)
            api_data = await self._get_api_cache_data()
            
            # Query the database for repeaters with matching prefixes
            # Node IDs are typically the first 2 characters of the public key
            for node_id in node_ids:
                # Check API cache first
                if api_data and node_id in api_data:
                    api_prefix_data = api_data[node_id]
                    if api_prefix_data['node_names']:
                        # Use API data
                        if len(api_prefix_data['node_names']) > 1:
                            # Multiple matches - show collision warning
                            repeater_info[node_id] = {
                                'found': True,
                                'collision': True,
                                'matches': len(api_prefix_data['node_names']),
                                'node_id': node_id,
                                'repeaters': [
                                    {
                                        'name': name,
                                        'public_key': f"{node_id}...",
                                        'device_type': 'Unknown',
                                        'last_seen': 'API',
                                        'is_active': True,
                                        'source': 'api'
                                    } for name in api_prefix_data['node_names']
                                ]
                            }
                        else:
                            # Single match
                            repeater_info[node_id] = {
                                'name': api_prefix_data['node_names'][0],
                                'public_key': f"{node_id}...",
                                'device_type': 'Unknown',
                                'last_seen': 'API',
                                'is_active': True,
                                'found': True,
                                'collision': False,
                                'source': 'api'
                            }
                        continue
                
                # Fallback to database if API cache doesn't have this prefix
                query = '''
                    SELECT name, public_key, device_type, last_seen, is_active, latitude, longitude, city, state, country
                    FROM repeater_contacts 
                    WHERE public_key LIKE ?
                    ORDER BY is_active DESC, last_seen DESC
                '''
                
                prefix_pattern = f"{node_id}%"
                results = self.bot.db_manager.execute_query(query, (prefix_pattern,))
                
                if results:
                    # Check for ID collisions (multiple repeaters with same prefix)
                    if len(results) > 1:
                        # Multiple matches - try geographic proximity selection
                        repeaters_data = [
                            {
                                'name': row['name'],
                                'public_key': row['public_key'],
                                'device_type': row['device_type'],
                                'last_seen': row['last_seen'],
                                'is_active': row['is_active'],
                                'latitude': row['latitude'],
                                'longitude': row['longitude'],
                                'city': row['city'],
                                'state': row['state'],
                                'country': row['country']
                            } for row in results
                        ]
                        
                        # Try to select the most likely repeater using geographic proximity
                        # Only attempt if geographic guessing is enabled
                        if self.geographic_guessing_enabled:
                            selected_repeater, confidence = self._select_repeater_by_proximity(repeaters_data, node_id, node_ids)
                            
                            if selected_repeater and confidence >= 0.5:
                                # High confidence geographic selection
                                repeater_info[node_id] = {
                                    'name': selected_repeater['name'],
                                    'public_key': selected_repeater['public_key'],
                                    'device_type': selected_repeater['device_type'],
                                    'last_seen': selected_repeater['last_seen'],
                                    'is_active': selected_repeater['is_active'],
                                    'found': True,
                                    'collision': False,
                                    'geographic_guess': True,
                                    'confidence': confidence
                                }
                            else:
                                # Low confidence or no geographic data - show collision warning
                                repeater_info[node_id] = {
                                    'found': True,
                                    'collision': True,
                                    'matches': len(results),
                                    'node_id': node_id,
                                    'repeaters': repeaters_data
                                }
                        else:
                            # Geographic guessing disabled - show collision warning
                            repeater_info[node_id] = {
                                'found': True,
                                'collision': True,
                                'matches': len(results),
                                'node_id': node_id,
                                'repeaters': repeaters_data
                            }
                    else:
                        # Single match
                        row = results[0]
                        repeater_info[node_id] = {
                            'name': row['name'],
                            'public_key': row['public_key'],
                            'device_type': row['device_type'],
                            'last_seen': row['last_seen'],
                            'is_active': row['is_active'],
                            'found': True,
                            'collision': False
                        }
                else:
                    # Also check device contacts for active repeaters
                    device_matches = []
                    if hasattr(self.bot.meshcore, 'contacts'):
                        for contact_key, contact_data in self.bot.meshcore.contacts.items():
                            public_key = contact_data.get('public_key', contact_key)
                            if public_key.startswith(node_id):
                                # Check if this is a repeater
                                if hasattr(self.bot, 'repeater_manager') and self.bot.repeater_manager._is_repeater_device(contact_data):
                                    name = contact_data.get('adv_name', contact_data.get('name', 'Unknown'))
                                    device_matches.append({
                                        'name': name,
                                        'public_key': public_key,
                                        'device_type': contact_data.get('type', 'Unknown'),
                                        'last_seen': 'Active',
                                        'is_active': True,
                                        'source': 'device'
                                    })
                    
                    if device_matches:
                        if len(device_matches) > 1:
                            # Multiple device matches - show collision warning
                            repeater_info[node_id] = {
                                'found': True,
                                'collision': True,
                                'matches': len(device_matches),
                                'node_id': node_id,
                                'repeaters': device_matches
                            }
                        else:
                            # Single device match
                            match = device_matches[0]
                            repeater_info[node_id] = {
                                'name': match['name'],
                                'public_key': match['public_key'],
                                'device_type': match['device_type'],
                                'last_seen': match['last_seen'],
                                'is_active': match['is_active'],
                                'found': True,
                                'collision': False,
                                'source': 'device'
                            }
                    else:
                        repeater_info[node_id] = {
                            'found': False,
                            'node_id': node_id
                        }
        
        except Exception as e:
            self.logger.error(f"Error looking up repeater names: {e}")
            # Return basic info for all nodes
            for node_id in node_ids:
                repeater_info[node_id] = {
                    'found': False,
                    'node_id': node_id,
                    'error': str(e)
                }
        
        return repeater_info
    
    async def _get_api_cache_data(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """Get API cache data from the prefix command if available"""
        try:
            # Try to get the prefix command instance and its cache data
            if hasattr(self.bot, 'command_manager'):
                prefix_cmd = self.bot.command_manager.commands.get('prefix')
                if prefix_cmd and hasattr(prefix_cmd, 'cache_data'):
                    # Check if cache is valid
                    current_time = time.time()
                    if current_time - prefix_cmd.cache_timestamp > prefix_cmd.cache_duration:
                        await prefix_cmd.refresh_cache()
                    return prefix_cmd.cache_data
        except Exception as e:
            self.logger.warning(f"Could not get API cache data: {e}")
        return None
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate haversine distance between two points in kilometers"""
        # Convert latitude and longitude from degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in kilometers
        earth_radius = 6371.0
        return earth_radius * c
    
    def _select_repeater_by_proximity(self, repeaters: List[Dict[str, Any]], node_id: str = None, path_context: List[str] = None) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Select the most likely repeater based on geographic proximity.
        
        Args:
            repeaters: List of repeaters to choose from
            node_id: The current node ID being processed
            path_context: Full path for context (for path proximity method)
        
        Returns:
            Tuple of (selected_repeater, confidence_score)
            confidence_score: 0.0 to 1.0, where 1.0 is very confident
        """
        if not repeaters:
            return None, 0.0
        
        # Check if geographic guessing is enabled
        if not self.geographic_guessing_enabled:
            return None, 0.0
        
        # Filter repeaters that have location data
        repeaters_with_location = []
        for repeater in repeaters:
            lat = repeater.get('latitude')
            lon = repeater.get('longitude')
            if lat is not None and lon is not None:
                # Skip 0,0 coordinates (hidden location)
                if not (lat == 0.0 and lon == 0.0):
                    repeaters_with_location.append(repeater)
        
        # If no repeaters have location data, we can't make a geographic guess
        if not repeaters_with_location:
            return None, 0.0
        
        # Choose proximity calculation method
        if self.proximity_method == 'path' and path_context and node_id:
            result = self._select_by_path_proximity(repeaters_with_location, node_id, path_context)
            if result[0] is not None:
                return result
            elif self.path_proximity_fallback:
                # Fall back to simple proximity if path proximity fails
                return self._select_by_simple_proximity(repeaters_with_location)
            else:
                return None, 0.0
        else:
            return self._select_by_simple_proximity(repeaters_with_location)
    
    def _select_by_simple_proximity(self, repeaters_with_location: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], float]:
        """Select repeater based on proximity to bot location"""
        # If only one repeater has location data, check if it's within range
        if len(repeaters_with_location) == 1:
            repeater = repeaters_with_location[0]
            distance = self._calculate_distance(
                self.bot_latitude, self.bot_longitude,
                repeater['latitude'], repeater['longitude']
            )
            # Apply maximum range threshold
            if self.max_proximity_range > 0 and distance > self.max_proximity_range:
                return None, 0.0  # Reject if beyond maximum range
            return repeater, 0.6
        
        # Calculate distances for all repeaters with location data
        distances = []
        for repeater in repeaters_with_location:
            distance = self._calculate_distance(
                self.bot_latitude, self.bot_longitude,
                repeater['latitude'], repeater['longitude']
            )
            distances.append((distance, repeater))
        
        # Sort by distance (closest first)
        distances.sort(key=lambda x: x[0])
        
        closest_distance, closest_repeater = distances[0]
        
        # Apply maximum range threshold
        if self.max_proximity_range > 0 and closest_distance > self.max_proximity_range:
            return None, 0.0  # Reject if closest repeater is beyond maximum range
        
        # Calculate confidence based on distance difference
        if len(distances) == 1:
            # Only one repeater with location data
            return closest_repeater, 0.6
        else:
            # Multiple repeaters with location data
            second_closest_distance = distances[1][0]
            distance_ratio = closest_distance / second_closest_distance if second_closest_distance > 0 else 0
            
            # Higher confidence if there's a significant distance difference
            if distance_ratio < 0.5:  # Closest is less than half the distance of second closest
                confidence = 0.9
            elif distance_ratio < 0.7:  # Closest is less than 70% of second closest
                confidence = 0.8
            elif distance_ratio < 0.9:  # Closest is less than 90% of second closest
                confidence = 0.7
            else:
                # Distances are too similar, but we can still make a selection
                # Use tie-breaker strategies for identical coordinates
                if distance_ratio == 1.0:  # Identical distances
                    # Try tie-breaker strategies
                    selected_repeater = self._apply_tie_breakers(distances)
                    confidence = 0.5  # Moderate confidence for tie-breaker selection
                else:
                    # Very similar distances, low confidence
                    confidence = 0.4
                
                return closest_repeater, confidence
    
    def _apply_tie_breakers(self, distances: List[Tuple[float, Dict[str, Any]]]) -> Dict[str, Any]:
        """Apply tie-breaker strategies when repeaters have identical coordinates"""
        # Get all repeaters with the same (minimum) distance
        min_distance = distances[0][0]
        tied_repeaters = [repeater for distance, repeater in distances if distance == min_distance]
        
        # Tie-breaker 1: Prefer active repeaters
        active_repeaters = [r for r in tied_repeaters if r.get('is_active', True)]
        if len(active_repeaters) == 1:
            return active_repeaters[0]
        elif len(active_repeaters) > 1:
            tied_repeaters = active_repeaters
        
        # Tie-breaker 2: Prefer repeaters with more recent last_seen
        # (This is a simple heuristic - in practice, you might want more sophisticated logic)
        try:
            # Sort by last_seen (more recent first)
            tied_repeaters.sort(key=lambda r: r.get('last_seen', ''), reverse=True)
        except:
            pass  # If sorting fails, continue with next tie-breaker
        
        # Tie-breaker 3: Alphabetical order (deterministic)
        tied_repeaters.sort(key=lambda r: r.get('name', ''))
        
        return tied_repeaters[0]
    
    def _select_by_path_proximity(self, repeaters_with_location: List[Dict[str, Any]], node_id: str, path_context: List[str]) -> Tuple[Optional[Dict[str, Any]], float]:
        """Select repeater based on proximity to previous/next nodes in path"""
        try:
            # Find current node position in path
            current_index = path_context.index(node_id) if node_id in path_context else -1
            if current_index == -1:
                return None, 0.0
            
            # Get previous and next node locations
            prev_location = None
            next_location = None
            
            # Get previous node location
            if current_index > 0:
                prev_node_id = path_context[current_index - 1]
                prev_location = self._get_node_location(prev_node_id)
            
            # Get next node location  
            if current_index < len(path_context) - 1:
                next_node_id = path_context[current_index + 1]
                next_location = self._get_node_location(next_node_id)
            
            # If we have both previous and next locations, use both for proximity
            if prev_location and next_location:
                return self._select_by_dual_proximity(repeaters_with_location, prev_location, next_location)
            elif prev_location:
                return self._select_by_single_proximity(repeaters_with_location, prev_location, "previous")
            elif next_location:
                return self._select_by_single_proximity(repeaters_with_location, next_location, "next")
            else:
                return None, 0.0
                
        except Exception as e:
            self.logger.warning(f"Error in path proximity calculation: {e}")
            return None, 0.0
    
    def _get_node_location(self, node_id: str) -> Optional[Tuple[float, float]]:
        """Get location for a node ID from the database"""
        try:
            # Query database for node location
            query = '''
                SELECT latitude, longitude FROM repeater_contacts 
                WHERE public_key LIKE ? AND latitude IS NOT NULL AND longitude IS NOT NULL
                AND latitude != 0 AND longitude != 0
                LIMIT 1
            '''
            prefix_pattern = f"{node_id}%"
            results = self.bot.db_manager.execute_query(query, (prefix_pattern,))
            
            if results:
                row = results[0]
                return (row['latitude'], row['longitude'])
            return None
        except Exception as e:
            self.logger.warning(f"Error getting location for node {node_id}: {e}")
            return None
    
    def _select_by_dual_proximity(self, repeaters: List[Dict[str, Any]], prev_location: Tuple[float, float], next_location: Tuple[float, float]) -> Tuple[Optional[Dict[str, Any]], float]:
        """Select repeater based on proximity to both previous and next nodes"""
        best_repeater = None
        best_score = float('inf')
        
        for repeater in repeaters:
            # Calculate distance to previous node
            prev_distance = self._calculate_distance(
                prev_location[0], prev_location[1],
                repeater['latitude'], repeater['longitude']
            )
            
            # Calculate distance to next node
            next_distance = self._calculate_distance(
                next_location[0], next_location[1],
                repeater['latitude'], repeater['longitude']
            )
            
            # Combined score (lower is better)
            # Weight both distances equally
            combined_score = (prev_distance + next_distance) / 2
            
            if combined_score < best_score:
                best_score = combined_score
                best_repeater = repeater
        
        if best_repeater:
            # Apply maximum range threshold
            if self.max_proximity_range > 0 and best_score > self.max_proximity_range:
                return None, 0.0  # Reject if beyond maximum range
            
            # Calculate confidence based on how much better this choice is
            confidence = min(0.9, max(0.6, 1.0 - (best_score / 100.0)))  # Scale confidence based on distance
            return best_repeater, confidence
        
        return None, 0.0
    
    def _select_by_single_proximity(self, repeaters: List[Dict[str, Any]], reference_location: Tuple[float, float], direction: str) -> Tuple[Optional[Dict[str, Any]], float]:
        """Select repeater based on proximity to single reference node"""
        distances = []
        for repeater in repeaters:
            distance = self._calculate_distance(
                reference_location[0], reference_location[1],
                repeater['latitude'], repeater['longitude']
            )
            distances.append((distance, repeater))
        
        # Sort by distance (closest first)
        distances.sort(key=lambda x: x[0])
        
        if not distances:
            return None, 0.0
        
        closest_distance, closest_repeater = distances[0]
        
        # Apply maximum range threshold
        if self.max_proximity_range > 0 and closest_distance > self.max_proximity_range:
            return None, 0.0  # Reject if beyond maximum range
        
        # Calculate confidence based on distance difference
        if len(distances) == 1:
            return closest_repeater, 0.7  # Higher confidence for single reference
        else:
            second_closest_distance = distances[1][0]
            distance_ratio = closest_distance / second_closest_distance if second_closest_distance > 0 else 0
            
            # Higher confidence for path proximity
            if distance_ratio < 0.5:
                confidence = 0.9
            elif distance_ratio < 0.7:
                confidence = 0.8
            else:
                confidence = 0.7
            
            return closest_repeater, confidence
    
    def _format_path_response(self, node_ids: List[str], repeater_info: Dict[str, Dict[str, Any]]) -> str:
        """Format the path decode response (max 130 chars per line)
        
        Maintains the order of repeaters as they appear in the path (first to last)
        """
        # Build response lines in path order (first to last as message traveled)
        lines = []
        
        # Process nodes in path order (first to last as message traveled)
        for node_id in node_ids:
            info = repeater_info.get(node_id, {})
            
            if info.get('found', False):
                if info.get('collision', False):
                    # Multiple repeaters with same prefix
                    matches = info.get('matches', 0)
                    line = f"{node_id}: {matches} repeaters"
                elif info.get('geographic_guess', False):
                    # Geographic proximity selection
                    name = info['name']
                    confidence = info.get('confidence', 0.0)
                    
                    # Truncate name if too long
                    if len(name) > 20:
                        name = name[:17] + "..."
                    
                    # Add confidence indicator
                    if confidence >= 0.9:
                        confidence_indicator = "🎯"
                    elif confidence >= 0.8:
                        confidence_indicator = "📍"
                    else:
                        confidence_indicator = "~"
                    
                    line = f"{node_id}: {name} {confidence_indicator}"
                else:
                    # Single repeater found
                    name = info['name']
                    
                    # Truncate name if too long
                    if len(name) > 27:
                        name = name[:24] + "..."
                    
                    line = f"{node_id}: {name}"
            else:
                # Unknown repeater
                line = f"{node_id}: Unknown"
            
            # Ensure line fits within 130 character limit
            if len(line) > 130:
                line = line[:127] + "..."
            
            lines.append(line)
        
        # Return all lines - let _send_path_response handle the splitting
        return "\n".join(lines)
    
    async def _send_path_response(self, message: MeshMessage, response: str):
        """Send path response, splitting into multiple messages if necessary"""
        if len(response) <= 130:
            # Single message is fine
            await self.bot.command_manager.send_response(message, response)
        else:
            # Split into multiple messages
            lines = response.split('\n')
            current_message = ""
            message_count = 0
            
            for i, line in enumerate(lines):
                # Check if adding this line would exceed 130 characters
                if len(current_message) + len(line) + 1 > 130:  # +1 for newline
                    # Send current message and start new one
                    if current_message:
                        # Add ellipsis on new line to end of continued message (if not the last message)
                        if i < len(lines):
                            current_message += "\n..."
                        await self.bot.command_manager.send_response(message, current_message.rstrip())
                        await asyncio.sleep(3.0)  # Delay between messages (same as other commands)
                        message_count += 1
                    
                    # Start new message with ellipsis on new line at beginning (if not first message)
                    if message_count > 0:
                        current_message = f"...\n{line}"
                    else:
                        current_message = line
                else:
                    # Add line to current message
                    if current_message:
                        current_message += f"\n{line}"
                    else:
                        current_message = line
            
            # Send the last message if there's content
            if current_message:
                await self.bot.command_manager.send_response(message, current_message)
    
    async def _extract_path_from_recent_messages(self) -> str:
        """Extract path from the current message's path information (same as test command)"""
        try:
            # Use the path information from the current message being processed
            # This is the same reliable source that the test command uses
            if hasattr(self, '_current_message') and self._current_message and self._current_message.path:
                path_string = self._current_message.path
                self.logger.info(f"Using path from current message: {path_string}")
                
                # Check if it's a direct connection
                if "Direct" in path_string or "0 hops" in path_string:
                    return "📡 Direct connection (0 hops)"
                
                # Try to extract path nodes from the path string
                # Path strings are typically in format: "node1,node2,node3 via ROUTE_TYPE_*"
                if " via ROUTE_TYPE_" in path_string:
                    # Extract just the path part before the route type
                    path_part = path_string.split(" via ROUTE_TYPE_")[0]
                else:
                    path_part = path_string
                
                # Check if it looks like a comma-separated path
                if ',' in path_part:
                    path_input = path_part
                    self.logger.info(f"Found path from current message: {path_input}")
                    return await self._decode_path(path_input)
                else:
                    # Single node or unknown format
                    return f"📡 Path: {path_string}"
            else:
                return "❌ No path information available in current message"
                
        except Exception as e:
            self.logger.error(f"Error extracting path from current message: {e}")
            return f"❌ Error extracting path from current message: {e}"
    
    def get_help(self) -> str:
        """Get help text for the path command"""
        return """Path: !path [hex] - Decode path to show repeaters. Use !path alone for recent message path, or !path [7e,01] for specific path."""
    
    def get_help_text(self) -> str:
        """Get help text for the path command (used by help system)"""
        return self.get_help()
