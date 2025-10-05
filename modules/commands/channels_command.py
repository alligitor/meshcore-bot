#!/usr/bin/env python3
"""
Channels command for the MeshCore Bot
Lists common hashtag channels for the region with multi-message support
"""

from .base_command import BaseCommand
from ..models import MeshMessage
import asyncio


class ChannelsCommand(BaseCommand):
    """Handles the channels command"""
    
    # Plugin metadata
    name = "channels"
    keywords = ['channels', 'channel']
    description = "Lists hashtag channels with sub-categories. Use 'channels' for general, 'channels list' for all categories, 'channels <category>' for specific categories, 'channels #channel' for specific channel info."
    category = "basic"
    
    def get_help_text(self) -> str:
        return "Lists hashtag channels with sub-categories. Use 'channels' for general, 'channels list' for all categories, 'channels <category>' for specific categories, 'channels #channel' for specific channel info."
    
    def matches_keyword(self, message: MeshMessage) -> bool:
        """Check if this command matches the message content based on keywords"""
        if not self.keywords:
            return False
        
        # Strip exclamation mark if present (for command-style messages)
        content = message.content.strip()
        if content.startswith('!'):
            content = content[1:].strip()
        content_lower = content.lower()
        
        # Don't match if this looks like a subcommand of another command
        # (e.g., "stats channels" should not match "channels" command)
        if ' ' in content_lower:
            parts = content_lower.split()
            if len(parts) > 1 and parts[0] not in ['channels', 'channel']:
                return False
        
        for keyword in self.keywords:
            keyword_lower = keyword.lower()
            
            # Check for exact match first
            if keyword_lower == content_lower:
                return True
            
            # Check for word boundary matches using regex
            import re
            # Create a regex pattern that matches the keyword at word boundaries
            # Use custom word boundary that treats underscores as separators
            # (?<![a-zA-Z0-9]) = negative lookbehind for alphanumeric characters (not underscore)
            # (?![a-zA-Z0-9]) = negative lookahead for alphanumeric characters (not underscore)
            # This allows underscores to act as word boundaries
            pattern = r'(?<![a-zA-Z0-9])' + re.escape(keyword_lower) + r'(?![a-zA-Z0-9])'
            if re.search(pattern, content_lower):
                return True
        
        return False
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the channels command"""
        try:
            # Parse the command to check for sub-commands
            content = message.content.strip()
            if content.startswith('!'):
                content = content[1:].strip()
            
            # Check for sub-command (e.g., "channels seattle", "channel seahawks", "channels list", "channels #bot")
            sub_command = None
            specific_channel = None
            if content.lower().startswith('channels ') or content.lower().startswith('channel '):
                parts = content.split(' ', 1)
                if len(parts) > 1:
                    sub_command = parts[1].strip().lower()
                    
                    # Handle special "list" command to show all categories
                    if sub_command == 'list':
                        await self._show_all_categories(message)
                        return True
                    
                    # Check if user is asking for a specific channel (starts with #)
                    if sub_command.startswith('#'):
                        specific_channel = sub_command
                        sub_command = None
                    else:
                        # Check if this might be a channel search (not a category)
                        # Try to find a channel that matches this name across all categories
                        found_channel = self._find_channel_by_name(sub_command)
                        if found_channel:
                            specific_channel = '#' + found_channel
                            sub_command = None
            
            # Handle specific channel request
            if specific_channel:
                await self._show_specific_channel(message, specific_channel)
                return True
            
            # Load channels from config (with sub-command support)
            channels = self._load_channels_from_config(sub_command)
            
            if not channels:
                if sub_command:
                    await self.send_response(message, f"No channels configured for '{sub_command}'. Use 'channels' for general channels.")
                else:
                    await self.send_response(message, "No channels configured. Contact admin to add channels.")
                return True
            
            # Build channel list (names only, no descriptions)
            channel_list = []
            for channel_name, description in channels.items():
                channel_list.append(channel_name)  # Just the channel name
            
            # Split into multiple messages if needed (130 character limit)
            messages = self._split_into_messages(channel_list, sub_command)
            
            # Send each message with a small delay between them
            for i, msg_content in enumerate(messages):
                if i > 0:
                    # Small delay between messages to prevent overwhelming the network
                    await asyncio.sleep(0.5)
                
                await self.send_response(message, msg_content)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in channels command: {e}")
            await self.send_response(message, f"Error retrieving channels: {e}")
            return False
    
    def _load_channels_from_config(self, sub_command: str = None) -> dict:
        """Load channels from the Channels_List config section with optional sub-command filtering"""
        channels = {}
        
        if self.bot.config.has_section('Channels_List'):
            for channel_name, description in self.bot.config.items('Channels_List'):
                # Skip empty or commented lines
                if channel_name.strip() and not channel_name.startswith('#'):
                    # Strip quotes if present
                    if description.startswith('"') and description.endswith('"'):
                        description = description[1:-1]
                    
                    # Handle sub-command filtering
                    if sub_command:
                        # Check if this channel belongs to the sub-command
                        if not channel_name.startswith(f'{sub_command}.'):
                            continue
                        # Remove the sub-command prefix for display
                        display_name = channel_name[len(sub_command) + 1:]  # Remove 'subcommand.'
                    else:
                        # For general channels, only show channels that don't have sub-command prefixes
                        if '.' in channel_name:
                            continue
                        display_name = channel_name
                    
                    # Add # prefix if not already present
                    if not display_name.startswith('#'):
                        display_name = '#' + display_name
                    
                    channels[display_name] = description
        
        return channels
    
    async def _show_all_categories(self, message: MeshMessage):
        """Show all available channel categories"""
        try:
            categories = self._get_all_categories()
            
            if not categories:
                await self.send_response(message, "No channel categories configured.")
                return
            
            # Build category list
            category_list = []
            for category, count in categories.items():
                category_list.append(f"{category} ({count} channels)")
            
            # Split into multiple messages if needed
            messages = self._split_into_messages(category_list, "Available categories")
            
            # Send each message with a small delay between them
            for i, msg_content in enumerate(messages):
                if i > 0:
                    await asyncio.sleep(0.5)
                await self.send_response(message, msg_content)
                
        except Exception as e:
            self.logger.error(f"Error showing categories: {e}")
            await self.send_response(message, f"Error retrieving categories: {e}")
    
    def _get_all_categories(self) -> dict:
        """Get all available channel categories and their channel counts"""
        categories = {}
        
        if self.bot.config.has_section('Channels_List'):
            for channel_name, description in self.bot.config.items('Channels_List'):
                # Skip empty or commented lines
                if channel_name.strip() and not channel_name.startswith('#'):
                    # Check if this is a sub-command channel (has a dot)
                    if '.' in channel_name:
                        category = channel_name.split('.')[0]
                        if category not in categories:
                            categories[category] = 0
                        categories[category] += 1
                    else:
                        # General channels (no category)
                        if 'general' not in categories:
                            categories['general'] = 0
                        categories['general'] += 1
        
        return categories
    
    def _find_channel_by_name(self, search_name: str) -> str:
        """Find a channel by partial name match across all categories"""
        search_name_lower = search_name.lower()
        
        if self.bot.config.has_section('Channels_List'):
            for config_name, description in self.bot.config.items('Channels_List'):
                # Skip empty or commented lines
                if config_name.strip() and not config_name.startswith('#'):
                    # Handle sub-command channels
                    if '.' in config_name:
                        category, name = config_name.split('.', 1)
                        # Check if the channel name matches (case insensitive)
                        if name.lower() == search_name_lower:
                            return name
                    else:
                        # Check general channels
                        if config_name.lower() == search_name_lower:
                            return config_name
        
        return None
    
    async def _show_specific_channel(self, message: MeshMessage, channel_name: str):
        """Show description for a specific channel"""
        try:
            # Search for the channel in all categories
            found_channel = None
            found_category = None
            
            if self.bot.config.has_section('Channels_List'):
                for config_name, description in self.bot.config.items('Channels_List'):
                    # Skip empty or commented lines
                    if config_name.strip() and not config_name.startswith('#'):
                        # Handle sub-command channels
                        if '.' in config_name:
                            category, name = config_name.split('.', 1)
                            display_name = '#' + name
                        else:
                            display_name = '#' + config_name
                        
                        # Check if this matches the requested channel
                        if display_name.lower() == channel_name.lower():
                            found_channel = display_name
                            found_category = category if '.' in config_name else 'general'
                            break
            
            if found_channel:
                # Get the description
                if found_category == 'general':
                    config_key = found_channel[1:]  # Remove #
                else:
                    config_key = f"{found_category}.{found_channel[1:]}"  # Remove #
                
                description = self.bot.config.get('Channels_List', config_key, fallback='No description available')
                
                # Strip quotes if present
                if description.startswith('"') and description.endswith('"'):
                    description = description[1:-1]
                
                response = f"{found_channel}: {description}"
                await self.send_response(message, response)
            else:
                await self.send_response(message, f"Channel {channel_name} not found. Use 'channels list' to see available channels.")
                
        except Exception as e:
            self.logger.error(f"Error showing specific channel: {e}")
            await self.send_response(message, f"Error retrieving channel info: {e}")
    
    def _split_into_messages(self, channel_list: list, sub_command: str = None) -> list:
        """Split channel list into multiple messages if they exceed 130 characters"""
        messages = []
        
        # Set appropriate header based on sub-command
        if sub_command == "Available categories":
            current_message = "Available Categories: "
        elif sub_command:
            current_message = f"{sub_command.title()}: "
        else:
            current_message = "Common channels: "
        
        current_length = len(current_message)
        
        for channel in channel_list:
            # Check if adding this channel would exceed the limit
            if current_length + len(channel) + 2 > 130:  # +2 for ", " separator
                # Start a new message
                if sub_command == "Available categories":
                    expected_header = "Available Categories: "
                else:
                    expected_header = f"{sub_command.title()} channels: " if sub_command else "Common channels: "
                
                if current_message != expected_header:
                    messages.append(current_message.rstrip(", "))
                    current_message = "Channels (cont): "
                    current_length = len(current_message)
                else:
                    # If even the first channel is too long, just send it alone
                    messages.append(f"{expected_header}{channel}")
                    current_message = "Channels (cont): "
                    current_length = len(current_message)
                    continue
            
            # Add channel to current message
            if sub_command == "Available categories":
                header = "Available Categories: "
            else:
                header = f"{sub_command.title()} channels: " if sub_command else "Common channels: "
            if current_message == header or current_message == "Channels (cont): ":
                current_message += channel
            else:
                current_message += f", {channel}"
            current_length = len(current_message)
        
        # Add the last message if it has content
        if sub_command == "Available categories":
            header = "Available Categories: "
        else:
            header = f"{sub_command.title()} channels: " if sub_command else "Common channels: "
        if current_message != header and current_message != "Channels (cont): ":
            messages.append(current_message)
        
        # If no messages were created, send a default message
        if not messages:
            if sub_command:
                messages.append(f"No {sub_command} channels configured")
            else:
                messages.append("No channels configured")
        
        return messages
