#!/usr/bin/env python3
"""
Base command class for all MeshCore Bot commands
Provides common functionality and interface for command implementations
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
from ..models import MeshMessage


class BaseCommand(ABC):
    """Base class for all bot commands - Plugin Interface"""
    
    # Plugin metadata - to be overridden by subclasses
    name: str = ""
    keywords: List[str] = []  # All trigger words for this command (including name and aliases)
    description: str = ""
    requires_dm: bool = False
    cooldown_seconds: int = 0
    category: str = "general"
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self._last_execution_time = 0
    
    @abstractmethod
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the command with the given message"""
        pass
    
    def get_help_text(self) -> str:
        """Get help text for this command"""
        return self.description or "No help available for this command."
    
    def can_execute(self, message: MeshMessage) -> bool:
        """Check if this command can be executed with the given message"""
        # Check if command requires DM and message is not DM
        if self.requires_dm and not message.is_dm:
            return False
        
        # Check cooldown
        if self.cooldown_seconds > 0:
            import time
            current_time = time.time()
            if (current_time - self._last_execution_time) < self.cooldown_seconds:
                return False
        
        return True
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get plugin metadata for discovery and registration"""
        return {
            'name': self.name,
            'keywords': self.keywords,
            'description': self.description,
            'requires_dm': self.requires_dm,
            'cooldown_seconds': self.cooldown_seconds,
            'category': self.category,
            'class_name': self.__class__.__name__,
            'module_name': self.__class__.__module__
        }
    
    async def send_response(self, message: MeshMessage, content: str) -> bool:
        """Unified method for sending responses to users"""
        try:
            if message.is_dm:
                return await self.bot.command_manager.send_dm(message.sender_id, content)
            else:
                return await self.bot.command_manager.send_channel_message(message.channel, content)
        except Exception as e:
            self.logger.error(f"Failed to send response: {e}")
            return False
    
    def _record_execution(self):
        """Record the execution time for cooldown tracking"""
        import time
        self._last_execution_time = time.time()
    
    def get_remaining_cooldown(self) -> int:
        """Get remaining cooldown time in seconds"""
        if self.cooldown_seconds <= 0:
            return 0
        
        import time
        current_time = time.time()
        elapsed = current_time - self._last_execution_time
        remaining = self.cooldown_seconds - elapsed
        return max(0, int(remaining))
    
    def matches_keyword(self, message: MeshMessage) -> bool:
        """Check if this command matches the message content based on keywords"""
        if not self.keywords:
            return False
        
        # Strip exclamation mark if present (for command-style messages)
        content = message.content.strip()
        if content.startswith('!'):
            content = content[1:].strip()
        content_lower = content.lower()
        
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
    
    def matches_custom_syntax(self, message: MeshMessage) -> bool:
        """Check if this command matches custom syntax patterns"""
        # Override in subclasses for custom syntax matching
        return False
    
    def should_execute(self, message: MeshMessage) -> bool:
        """Check if this command should execute for the given message"""
        return (self.matches_keyword(message) or self.matches_custom_syntax(message)) and self.can_execute(message)
    
    def build_enhanced_connection_info(self, message: MeshMessage) -> str:
        """Build enhanced connection info with SNR, RSSI, and parsed route information"""
        # Extract just the hops and path info without the route type
        routing_info = message.path or "Unknown routing"
        
        # Clean up the routing info to remove the "via ROUTE_TYPE_*" part
        if "via ROUTE_TYPE_" in routing_info:
            # Extract just the hops and path part
            parts = routing_info.split(" via ROUTE_TYPE_")
            if len(parts) > 0:
                routing_info = parts[0]
        
        # Add SNR and RSSI
        snr_info = f"SNR: {message.snr or 'Unknown'} dB"
        rssi_info = f"RSSI: {message.rssi or 'Unknown'} dBm"
        
        # Build enhanced connection info
        connection_info = f"{routing_info} | {snr_info} | {rssi_info}"
        
        return connection_info
    
    def format_timestamp(self, message: MeshMessage) -> str:
        """Format message timestamp for display"""
        if message.timestamp and message.timestamp != 'unknown':
            try:
                from datetime import datetime
                dt = datetime.fromtimestamp(message.timestamp)
                return dt.strftime("%H:%M:%S")
            except:
                return str(message.timestamp)
        else:
            return "Unknown"
    
    def format_response(self, message: MeshMessage, response_format: str) -> str:
        """Format a response string with message data"""
        try:
            connection_info = self.build_enhanced_connection_info(message)
            timestamp = self.format_timestamp(message)
            
            return response_format.format(
                sender=message.sender_id or "Unknown",
                connection_info=connection_info,
                path=message.path or "Unknown",
                timestamp=timestamp,
                snr=message.snr or "Unknown",
                rssi=message.rssi or "Unknown"
            )
        except (KeyError, ValueError) as e:
            self.logger.warning(f"Error formatting response: {e}")
            return response_format
    
    def get_response_format(self) -> Optional[str]:
        """Get the response format for this command from config"""
        # Override in subclasses to provide custom response formats
        return None
    
    def _strip_quotes_from_config(self, value: str) -> str:
        """Strip quotes from config values if present"""
        if value and value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value
    
    async def handle_keyword_match(self, message: MeshMessage) -> bool:
        """Handle keyword matching and response generation"""
        response_format = self.get_response_format()
        if response_format:
            response = self.format_response(message, response_format)
            return await self.send_response(message, response)
        else:
            # Fall back to execute method
            return await self.execute(message)
