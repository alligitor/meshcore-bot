#!/usr/bin/env python3
"""
Path Decode Command for the MeshCore Bot
Decodes hex path data to show which repeaters were involved in message routing
"""

import re
import time
import asyncio
from typing import List, Optional, Dict, Any
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
                    SELECT name, public_key, device_type, last_seen, is_active
                    FROM repeater_contacts 
                    WHERE public_key LIKE ?
                    ORDER BY is_active DESC, last_seen DESC
                '''
                
                prefix_pattern = f"{node_id}%"
                results = self.bot.db_manager.execute_query(query, (prefix_pattern,))
                
                if results:
                    # Check for ID collisions (multiple repeaters with same prefix)
                    if len(results) > 1:
                        # Multiple matches - show collision warning
                        repeater_info[node_id] = {
                            'found': True,
                            'collision': True,
                            'matches': len(results),
                            'node_id': node_id,
                            'repeaters': [
                                {
                                    'name': row['name'],
                                    'public_key': row['public_key'],
                                    'device_type': row['device_type'],
                                    'last_seen': row['last_seen'],
                                    'is_active': row['is_active']
                                } for row in results
                            ]
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
                        await asyncio.sleep(2.0)  # Delay between messages (same as other commands)
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
