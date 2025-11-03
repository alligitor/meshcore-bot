#!/usr/bin/env python3
"""
Channel management functionality for the MeshCore Bot
Handles efficient concurrent channel fetching with caching
"""

import asyncio
import sys
import os
from typing import Dict, Any, List, Optional
from meshcore import EventType


class ChannelManager:
    """Manages channel operations and information with enhanced concurrent fetching"""
    
    def __init__(self, bot, max_channels: int = 8):
        """
        Initialize the channel manager
        
        Args:
            bot: The MeshCore bot instance
            max_channels: Maximum number of channels to fetch (default 8)
        """
        self.bot = bot
        self.logger = bot.logger
        self.max_channels = max_channels
        self._channels_cache: Dict[int, Dict[str, Any]] = {}
        self._cache_valid = False
        self._fetch_timeout = 2.0  # Timeout for individual channel fetches
    
    async def fetch_channels(self):
        """Fetch channels from the MeshCore node using enhanced concurrent fetching"""
        self.logger.info("Fetching channels from MeshCore node using enhanced concurrent method...")
        try:
            # Wait a moment for the device to be ready
            await asyncio.sleep(2)
            
            # Fetch all channels concurrently
            channels = await self.fetch_all_channels(force_refresh=True)
            
            if channels:
                self.logger.info(f"Successfully fetched {len(channels)} channels from MeshCore node")
                for channel in channels:
                    channel_name = channel.get('channel_name', f'Channel{channel.get("channel_idx", "?")}')
                    channel_idx = channel.get('channel_idx', '?')
                    if channel_name:  # Only log non-empty channel names
                        self.logger.info(f"  Channel {channel_idx}: {channel_name}")
                    else:
                        self.logger.debug(f"  Channel {channel_idx}: (empty)")
            else:
                self.logger.warning("No channels found on MeshCore node")
                self.bot.meshcore.channels = {}
                
        except Exception as e:
            self.logger.error(f"Failed to fetch channels: {e}")
            self.bot.meshcore.channels = {}
    
    async def fetch_all_channels(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all channels efficiently using optimized sequential requests
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh data
            
        Returns:
            List of channel dictionaries with channel info
        """
        if not force_refresh and self._cache_valid:
            return self._get_cached_channels()
        
        self.logger.info(f"Fetching all channels (0-{self.max_channels-1}) with optimized sequential method...")
        
        # Clear cache for fresh fetch
        self._channels_cache.clear()
        valid_channels = []
        
        # Fetch channels sequentially but with optimized logic
        for channel_idx in range(self.max_channels):
            try:
                result = await self._fetch_single_channel(channel_idx)
                
                if result and result.get("channel_name"):
                    self._channels_cache[channel_idx] = result
                    valid_channels.append(result)
                    self.logger.debug(f"Found channel {channel_idx}: {result.get('channel_name')}")
                elif result and not result.get("channel_name"):
                    # Empty channel - log but don't stop
                    self.logger.debug(f"Channel {channel_idx} is empty")
                else:
                    # No response - channel doesn't exist
                    self.logger.debug(f"Channel {channel_idx} not found")
                
                # Small delay between requests to avoid overwhelming the device
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.debug(f"Error fetching channel {channel_idx}: {e}")
                continue
        
        self._cache_valid = True
        self.logger.info(f"Successfully fetched {len(valid_channels)} channels")
        
        # Update the bot's meshcore channels for compatibility
        self.bot.meshcore.channels = self._channels_cache
        
        return valid_channels
    
    async def _fetch_single_channel(self, channel_idx: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a single channel with error handling
        
        Args:
            channel_idx: The channel index to fetch
            
        Returns:
            Channel info dictionary or None if not configured
        """
        try:
            # Create a future to capture the channel info event
            channel_event = None
            event_received = asyncio.Event()
            
            async def on_channel_info(event):
                nonlocal channel_event
                if event.payload.get('channel_idx') == channel_idx:
                    channel_event = event
                    event_received.set()
            
            # Subscribe to channel info events
            subscription = self.bot.meshcore.subscribe(EventType.CHANNEL_INFO, on_channel_info)
            
            try:
                # Send the command (suppress raw JSON output)
                from meshcore_cli.meshcore_cli import next_cmd
                
                with open(os.devnull, 'w') as devnull:
                    old_stdout = sys.stdout
                    sys.stdout = devnull
                    try:
                        await next_cmd(self.bot.meshcore, ["get_channel", str(channel_idx)])
                    finally:
                        sys.stdout = old_stdout
                
                # Wait for the event with timeout
                try:
                    await asyncio.wait_for(event_received.wait(), timeout=self._fetch_timeout)
                except asyncio.TimeoutError:
                    self.logger.debug(f"Timeout waiting for channel {channel_idx} response")
                    return None
                
                # Check if we got the channel info
                if channel_event and channel_event.payload:
                    payload = channel_event.payload
                    
                    # Store channel key for decryption
                    channel_secret = payload.get('channel_secret', b'')
                    if isinstance(channel_secret, bytes) and len(channel_secret) == 16:
                        # Convert to hex for easier handling
                        payload['channel_key_hex'] = channel_secret.hex()
                    
                    # Check if this is an empty channel (all-zero channel secret)
                    if isinstance(channel_secret, bytes) and channel_secret == b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00':
                        self.logger.debug(f"Channel {channel_idx} is empty (all-zero secret)")
                        return None
                    
                    return payload
                else:
                    self.logger.debug(f"No channel {channel_idx} found")
                    return None
                    
            finally:
                # Unsubscribe
                self.bot.meshcore.unsubscribe(subscription)
                
        except asyncio.TimeoutError:
            self.logger.debug(f"Timeout fetching channel {channel_idx}")
            return None
        except Exception as e:
            self.logger.debug(f"Error fetching channel {channel_idx}: {e}")
            return None
    
    def _get_cached_channels(self) -> List[Dict[str, Any]]:
        """Get channels from cache, sorted by index"""
        return [
            self._channels_cache[idx] 
            for idx in sorted(self._channels_cache.keys())
        ]
    
    async def get_channel(self, channel_idx: int, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get a specific channel, optionally from cache
        
        Args:
            channel_idx: The channel index
            use_cache: If True, return from cache if available
            
        Returns:
            Channel info dictionary or None
        """
        if use_cache and channel_idx in self._channels_cache:
            return self._channels_cache[channel_idx]
        
        result = await self._fetch_single_channel(channel_idx)
        
        if result:
            self._channels_cache[channel_idx] = result
        
        return result
    
    def get_channel_name(self, channel_num: int) -> str:
        """Get channel name from channel number"""
        if channel_num in self._channels_cache:
            channel_info = self._channels_cache[channel_num]
            return channel_info.get('channel_name', f"Channel{channel_num}")
        else:
            self.logger.warning(f"Channel {channel_num} not found in cached channels")
            return f"Channel{channel_num}"
    
    def get_channel_number(self, channel_name: str) -> Optional[int]:
        """
        Get channel number from channel name
        
        Args:
            channel_name: The channel name to look up
            
        Returns:
            Channel number if found, None if not found (to distinguish from channel 0)
        """
        for num, channel_info in self._channels_cache.items():
            if channel_info.get('channel_name', '').lower() == channel_name.lower():
                return num
        
        self.logger.warning(f"Channel name '{channel_name}' not found in cached channels")
        return None
    
    def get_channel_key(self, channel_num: int) -> str:
        """Get channel encryption key from channel number"""
        if channel_num in self._channels_cache:
            channel_info = self._channels_cache[channel_num]
            return channel_info.get('channel_key_hex', '')
        return ''
    
    def get_channel_info(self, channel_num: int) -> dict:
        """Get complete channel information including name and key"""
        if channel_num in self._channels_cache:
            channel_info = self._channels_cache[channel_num]
            return {
                'name': self.get_channel_name(channel_num),
                'key': self.get_channel_key(channel_num),
                'info': channel_info
            }
        return {'name': f"Channel{channel_num}", 'key': '', 'info': {}}
    
    def get_channel_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find a channel by name from cache
        
        Args:
            name: The channel name to search for
            
        Returns:
            Channel info dictionary or None
        """
        if not self._cache_valid:
            self.logger.warning("Cache not valid, call fetch_all_channels() first")
            return None
        
        name_lower = name.lower()
        for channel in self._channels_cache.values():
            if channel.get("channel_name", "").lower() == name_lower:
                return channel
        
        return None
    
    def get_configured_channels(self) -> List[Dict[str, Any]]:
        """
        Get only configured channels from cache
        
        Returns:
            List of configured channels
        """
        if not self._cache_valid:
            self.logger.warning("Cache not valid, call fetch_all_channels() first")
            return []
        
        return [
            ch for ch in self._channels_cache.values()
            if ch.get("channel_name") and ch["channel_name"].strip()
        ]
    
    def invalidate_cache(self):
        """Invalidate the channels cache"""
        self._cache_valid = False
        self.logger.debug("Channels cache invalidated")
