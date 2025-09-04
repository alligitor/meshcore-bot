#!/usr/bin/env python3
"""
Channel management functionality for the MeshCore Bot
Handles channel fetching, naming, and operations
"""

import asyncio
from typing import Dict, Any


class ChannelManager:
    """Manages channel operations and information"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
    
    async def fetch_channels(self):
        """Fetch channels from the MeshCore node"""
        self.logger.info("Fetching channels from MeshCore node...")
        try:
            # Wait a moment for the device to be ready
            await asyncio.sleep(2)
            
            # Try to fetch channels 0-9 (common channel range)
            channels = {}
            
            for channel_num in range(10):
                try:
                    self.logger.debug(f"Fetching channel {channel_num}...")
                    
                    # Send the get_channel command and wait for the response
                    # The meshcore library will automatically handle the command and dispatch events
                    from meshcore_cli.meshcore_cli import next_cmd
                    
                    # Create a future to capture the channel info event
                    channel_event = None
                    
                    async def on_channel_info(event):
                        nonlocal channel_event
                        if event.payload.get('channel_idx') == channel_num:
                            channel_event = event
                    
                    # Subscribe to channel info events
                    from meshcore import EventType
                    subscription = self.bot.meshcore.subscribe(EventType.CHANNEL_INFO, on_channel_info)
                    
                    # Send the command
                    await next_cmd(self.bot.meshcore, ["get_channel", str(channel_num)])
                    
                    # Wait a moment for the event to be processed
                    await asyncio.sleep(0.5)
                    
                    # Unsubscribe
                    self.bot.meshcore.unsubscribe(subscription)
                    
                    # Check if we got the channel info
                    if channel_event and channel_event.payload:
                        channels[channel_num] = channel_event.payload
                        self.logger.debug(f"Found channel {channel_num}: {channel_event.payload}")
                        
                        # Store channel key for decryption
                        channel_secret = channel_event.payload.get('channel_secret', b'')
                        if isinstance(channel_secret, bytes) and len(channel_secret) == 16:
                            # Convert to hex for easier handling
                            channels[channel_num]['channel_key_hex'] = channel_secret.hex()
                            self.logger.debug(f"Channel {channel_num} has key: {channels[channel_num]['channel_key_hex']}")
                        
                        # Check if this is an empty channel (all-zero channel secret)
                        if isinstance(channel_secret, bytes) and channel_secret == b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00':
                            self.logger.debug(f"Found empty channel {channel_num}, stopping channel fetch")
                            break
                    else:
                        self.logger.debug(f"No channel {channel_num} found")
                        # If we can't get channel info, assume no more channels
                        break
                    
                    # Add a small delay between requests
                    await asyncio.sleep(0.5)
                except Exception as e:
                    self.logger.debug(f"Error fetching channel {channel_num}: {e}")
                    # Don't break on first error, continue trying other channels
                    continue
            
            if channels:
                self.bot.meshcore.channels = channels
                self.logger.info(f"Successfully fetched {len(channels)} channels from MeshCore node")
                for num, info in channels.items():
                    self.logger.info(f"  Channel {num}: {info}")
            else:
                self.logger.warning("No channels found on MeshCore node")
                self.bot.meshcore.channels = {}
                
        except Exception as e:
            self.logger.error(f"Failed to fetch channels: {e}")
            self.bot.meshcore.channels = {}
    
    def get_channel_name(self, channel_num: int) -> str:
        """Get channel name from channel number"""
        if channel_num in self.bot.meshcore.channels:
            channel_info = self.bot.meshcore.channels[channel_num]
            
            # Handle different possible data structures
            if isinstance(channel_info, dict):
                # Check for channel_name (CLI format) or name (fallback)
                return channel_info.get('channel_name', channel_info.get('name', f"Channel{channel_num}"))
            elif hasattr(channel_info, 'channel_name'):
                return channel_info.channel_name
            elif hasattr(channel_info, 'name'):
                return channel_info.name
            elif hasattr(channel_info, 'payload') and isinstance(channel_info.payload, dict):
                return channel_info.payload.get('channel_name', channel_info.payload.get('name', f"Channel{channel_num}"))
            else:
                return f"Channel{channel_num}"
        else:
            self.logger.warning(f"Channel {channel_num} not found in fetched channels")
            return f"Channel{channel_num}"
    
    def get_channel_number(self, channel_name: str) -> int:
        """Get channel number from channel name"""
        for num, channel_info in self.bot.meshcore.channels.items():
            # Handle different possible data structures
            if isinstance(channel_info, dict):
                # Check for channel_name (CLI format) or name (fallback)
                if (channel_info.get('channel_name', '').lower() == channel_name.lower() or 
                    channel_info.get('name', '').lower() == channel_name.lower()):
                    return num
            elif hasattr(channel_info, 'channel_name'):
                if channel_info.channel_name.lower() == channel_name.lower():
                    return num
            elif hasattr(channel_info, 'name'):
                if channel_info.name.lower() == channel_name.lower():
                    return num
        
        self.logger.warning(f"Channel name '{channel_name}' not found in fetched channels")
        # Return 0 as fallback, but log a warning
        return 0
    
    def get_channel_key(self, channel_num: int) -> str:
        """Get channel encryption key from channel number"""
        if channel_num in self.bot.meshcore.channels:
            channel_info = self.bot.meshcore.channels[channel_num]
            if isinstance(channel_info, dict):
                return channel_info.get('channel_key_hex', '')
        return ''
    
    def get_channel_info(self, channel_num: int) -> dict:
        """Get complete channel information including name and key"""
        if channel_num in self.bot.meshcore.channels:
            channel_info = self.bot.meshcore.channels[channel_num]
            if isinstance(channel_info, dict):
                return {
                    'name': self.get_channel_name(channel_num),
                    'key': self.get_channel_key(channel_num),
                    'info': channel_info
                }
        return {'name': f"Channel{channel_num}", 'key': '', 'info': {}}
