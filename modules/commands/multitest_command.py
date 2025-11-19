#!/usr/bin/env python3
"""
Multitest command for the MeshCore Bot
Listens for a period of time and collects all unique paths from incoming messages
"""

import asyncio
import time
from typing import Set, Optional
from .base_command import BaseCommand
from ..models import MeshMessage
from ..utils import calculate_packet_hash


class MultitestCommand(BaseCommand):
    """Handles the multitest command - listens for multiple path variations"""
    
    # Plugin metadata
    name = "multitest"
    keywords = ['multitest', 'mt']
    description = "Listens for 6 seconds and collects all unique paths from incoming messages"
    category = "meshcore_info"
    
    def __init__(self, bot):
        super().__init__(bot)
        self.listening = False
        self.collected_paths: Set[str] = set()
        self.listening_start_time = 0
        self.listening_duration = 6.0  # 6 seconds listening window
        self.target_packet_hash: Optional[str] = None  # Hash of the message we're tracking
    
    def get_help_text(self) -> str:
        return self.translate('commands.multitest.help', fallback="Listens for 6 seconds and collects all unique paths from incoming messages")
    
    def matches_keyword(self, message: MeshMessage) -> bool:
        """Check if message matches multitest keyword"""
        content = message.content.strip()
        
        # Handle exclamation prefix
        if content.startswith('!'):
            content = content[1:].strip()
        
        content_lower = content.lower()
        
        # Check for exact match or keyword followed by space
        for keyword in self.keywords:
            if content_lower == keyword or content_lower.startswith(keyword + ' '):
                return True
        
        return False
    
    def extract_path_from_rf_data(self, rf_data: dict) -> Optional[str]:
        """Extract path in prefix string format from RF data routing_info"""
        try:
            routing_info = rf_data.get('routing_info')
            if not routing_info:
                return None
            
            path_nodes = routing_info.get('path_nodes', [])
            if not path_nodes:
                # Try to extract from path_hex if path_nodes not available
                path_hex = routing_info.get('path_hex', '')
                if path_hex:
                    # Convert hex string to node list (every 2 characters = 1 node)
                    path_nodes = [path_hex[i:i+2] for i in range(0, len(path_hex), 2)]
            
            if path_nodes:
                # Validate and format path nodes
                valid_parts = []
                for node in path_nodes:
                    # Convert to string if needed
                    node_str = str(node).lower().strip()
                    # Check if it's a 2-character hex value
                    if len(node_str) == 2 and all(c in '0123456789abcdef' for c in node_str):
                        valid_parts.append(node_str)
                
                if valid_parts:
                    return ','.join(valid_parts)
            
            return None
        except Exception as e:
            self.logger.debug(f"Error extracting path from RF data: {e}")
            return None
    
    def extract_path_from_message(self, message: MeshMessage) -> Optional[str]:
        """Extract path in prefix string format from a message"""
        if not message.path:
            return None
        
        # Check if it's a direct connection
        if "Direct" in message.path or "0 hops" in message.path:
            return None
        
        # Try to extract path nodes from the path string
        # Path strings are typically in format: "node1,node2,node3 via ROUTE_TYPE_*"
        # or just "node1,node2,node3"
        path_string = message.path
        
        # Remove route type suffix if present
        if " via ROUTE_TYPE_" in path_string:
            path_string = path_string.split(" via ROUTE_TYPE_")[0]
        
        # Check if it looks like a comma-separated path
        if ',' in path_string:
            # Clean up any extra info (like hop counts in parentheses)
            # Example: "01,7e,55,86 (4 hops)" -> "01,7e,55,86"
            if '(' in path_string:
                path_string = path_string.split('(')[0].strip()
            
            # Validate that all parts are 2-character hex values
            parts = path_string.split(',')
            valid_parts = []
            for part in parts:
                part = part.strip()
                # Check if it's a 2-character hex value
                if len(part) == 2 and all(c in '0123456789abcdefABCDEF' for c in part):
                    valid_parts.append(part.lower())
            
            if valid_parts:
                return ','.join(valid_parts)
        
        return None
    
    def get_rf_data_for_message(self, message: MeshMessage) -> Optional[dict]:
        """Get RF data for a message by looking it up in recent RF data"""
        try:
            # Try multiple correlation strategies
            # Strategy 1: Use sender_pubkey to find recent RF data
            if message.sender_pubkey:
                # Try full pubkey first
                recent_rf_data = self.bot.message_handler.find_recent_rf_data(message.sender_pubkey)
                if recent_rf_data:
                    return recent_rf_data
                
                # Try pubkey prefix (first 16 chars)
                if len(message.sender_pubkey) >= 16:
                    pubkey_prefix = message.sender_pubkey[:16]
                    recent_rf_data = self.bot.message_handler.find_recent_rf_data(pubkey_prefix)
                    if recent_rf_data:
                        return recent_rf_data
            
            # Strategy 2: Look through recent RF data for matching pubkey
            if message.sender_pubkey and self.bot.message_handler.recent_rf_data:
                # Search recent RF data for matching pubkey
                for rf_data in reversed(self.bot.message_handler.recent_rf_data):
                    rf_pubkey = rf_data.get('pubkey_prefix', '')
                    if rf_pubkey and message.sender_pubkey.startswith(rf_pubkey):
                        return rf_data
            
            # Strategy 3: Use most recent RF data as fallback
            # This is less reliable but might work if timing is very close
            if self.bot.message_handler.recent_rf_data:
                # Get the most recent RF data entry within a short time window
                current_time = time.time()
                recent_entries = [
                    rf for rf in self.bot.message_handler.recent_rf_data
                    if current_time - rf.get('timestamp', 0) < 5.0  # Within last 5 seconds
                ]
                if recent_entries:
                    most_recent = max(recent_entries, key=lambda x: x.get('timestamp', 0))
                    return most_recent
            
            return None
        except Exception as e:
            self.logger.debug(f"Error getting RF data for message: {e}")
            return None
    
    def on_message_received(self, message: MeshMessage):
        """Callback method called by message handler when a message is received during listening"""
        if not self.listening or not self.target_packet_hash:
            return
        
        # Check if we're still in the listening window
        elapsed = time.time() - self.listening_start_time
        if elapsed >= self.listening_duration:
            return
        
        # Get RF data for this message (contains pre-calculated packet hash)
        rf_data = self.get_rf_data_for_message(message)
        if not rf_data:
            # Can't get RF data, skip this message
            return
        
        # Use pre-calculated packet hash if available, otherwise calculate it
        message_hash = rf_data.get('packet_hash')
        if not message_hash and rf_data.get('raw_hex'):
            # Fallback: calculate hash if not stored (for older RF data)
            message_hash = calculate_packet_hash(rf_data['raw_hex'])
        
        if not message_hash:
            # Can't determine hash, skip this message
            return
        
        # Only collect paths if this message has the same hash as the target
        # This ensures we only track variations of the same original message
        if message_hash == self.target_packet_hash:
            # Try to extract path from RF data first (more reliable)
            path = self.extract_path_from_rf_data(rf_data)
            
            # Fallback to message path if RF data extraction failed
            if not path:
                path = self.extract_path_from_message(message)
            
            if path:
                self.collected_paths.add(path)
                self.logger.debug(f"Collected path during listening: {path} (hash: {message_hash})")
            else:
                # Log when we have a matching hash but can't extract path
                routing_info = rf_data.get('routing_info', {})
                path_length = routing_info.get('path_length', 0)
                if path_length == 0:
                    self.logger.debug(f"Matched hash {message_hash} but path is direct (0 hops)")
                else:
                    self.logger.debug(f"Matched hash {message_hash} but couldn't extract path from routing_info: {routing_info}")
        # Note: We don't log hash mismatches to avoid spam - only matching hashes are logged
    
    def _scan_recent_rf_data(self):
        """Scan recent RF data for packets with matching hash (for messages that haven't been processed yet)"""
        if not self.target_packet_hash:
            return
        
        try:
            current_time = time.time()
            # Look at RF data from the last few seconds (before listening started, in case packets arrived just before)
            for rf_data in self.bot.message_handler.recent_rf_data:
                # Check if this RF data is recent enough
                rf_timestamp = rf_data.get('timestamp', 0)
                time_diff = current_time - rf_timestamp
                
                # Include RF data from slightly before listening started (up to 2 seconds) and during listening
                if -2.0 <= time_diff <= self.listening_duration:
                    packet_hash = rf_data.get('packet_hash')
                    if packet_hash == self.target_packet_hash:
                        # Extract path from this RF data
                        path = self.extract_path_from_rf_data(rf_data)
                        if path:
                            self.collected_paths.add(path)
                            self.logger.debug(f"Collected path from RF data scan: {path} (hash: {packet_hash}, time: {time_diff:.2f}s)")
        except Exception as e:
            self.logger.debug(f"Error scanning recent RF data: {e}")
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the multitest command"""
        self.logger.info("Multitest command executed - starting listening window")
        
        # Get RF data for the triggering message (contains pre-calculated packet hash)
        rf_data = self.get_rf_data_for_message(message)
        if not rf_data:
            response = "Error: Could not find packet data for this message. Please try again."
            await self.send_response(message, response)
            return True
        
        # Use pre-calculated packet hash if available, otherwise calculate it
        packet_hash = rf_data.get('packet_hash')
        if not packet_hash and rf_data.get('raw_hex'):
            # Fallback: calculate hash if not stored (for older RF data)
            packet_hash = calculate_packet_hash(rf_data['raw_hex'])
        
        if not packet_hash:
            response = "Error: Could not calculate packet hash for this message. Please try again."
            await self.send_response(message, response)
            return True
        
        # Store the packet hash to track
        self.target_packet_hash = packet_hash
        self.logger.info(f"Tracking packet hash: {self.target_packet_hash}")
        
        # Also extract path from the triggering message itself
        initial_path = self.extract_path_from_message(message)
        # Also try to extract from RF data (more reliable)
        if not initial_path and rf_data:
            initial_path = self.extract_path_from_rf_data(rf_data)
        
        if initial_path:
            self.logger.debug(f"Initial path from triggering message: {initial_path}")
        
        # Register this command instance as the active listener
        # Store reference in message handler so it can call on_message_received
        self.bot.message_handler.multitest_listener = self
        
        # Start listening
        self.listening = True
        self.collected_paths = set()
        if initial_path:
            self.collected_paths.add(initial_path)  # Include the initial path
        self.listening_start_time = time.time()
        
        # Also scan recent RF data for matching hashes (in case messages haven't been processed yet)
        self._scan_recent_rf_data()
        
        try:
            # Wait for the listening duration
            await asyncio.sleep(self.listening_duration)
        finally:
            # Stop listening and unregister (but keep target_packet_hash for error messages)
            self.listening = False
            self.bot.message_handler.multitest_listener = None
        
        # Do a final scan of RF data in case any matching packets arrived
        self._scan_recent_rf_data()
        
        # Store hash for error message before clearing it
        tracking_hash = self.target_packet_hash
        
        # Format the collected paths
        if self.collected_paths:
            # Sort paths for consistent output
            sorted_paths = sorted(self.collected_paths)
            response = f"Found {len(sorted_paths)} unique path(s):\n" + "\n".join(sorted_paths)
        else:
            # Provide more helpful error message with diagnostic info
            matching_packets = 0
            if self.bot.message_handler.recent_rf_data and tracking_hash:
                for rf_data in self.bot.message_handler.recent_rf_data:
                    if rf_data.get('packet_hash') == tracking_hash:
                        matching_packets += 1
            
            if tracking_hash is None:
                response = ("Error: Could not determine packet hash for tracking. "
                           "The triggering message may not have valid packet data.")
            elif matching_packets > 0:
                response = (f"No paths extracted from {matching_packets} matching packet(s) "
                           f"(hash: {tracking_hash}). "
                           f"Packets may be direct (0 hops) or path extraction failed.")
            else:
                response = (f"No matching packets found during {self.listening_duration}s window. "
                           f"Tracking hash: {tracking_hash}. ")
        
        # Clear the hash after we're done with it
        self.target_packet_hash = None
        
        # Wait for bot TX rate limiter cooldown to expire before sending
        # This ensures we respond even if another command put the bot on cooldown
        await self.bot.bot_tx_rate_limiter.wait_for_tx()
        
        # Also wait for user rate limiter if needed
        if not self.bot.rate_limiter.can_send():
            wait_time = self.bot.rate_limiter.time_until_next()
            if wait_time > 0:
                self.logger.info(f"Waiting {wait_time:.1f} seconds for rate limiter")
                await asyncio.sleep(wait_time + 0.1)  # Small buffer
        
        # Send the response
        await self.send_response(message, response)
        
        return True

