#!/usr/bin/env python3
"""
Test command for the MeshCore Bot
Handles the 'test' keyword response
"""

import re
from .base_command import BaseCommand
from ..models import MeshMessage


class TestCommand(BaseCommand):
    """Handles the test command"""
    
    # Plugin metadata
    name = "test"
    keywords = ['test']
    description = "Responds to 'test' with connection info"
    category = "basic"
    
    def get_help_text(self) -> str:
        return self.description
    
    def matches_keyword(self, message: MeshMessage) -> bool:
        """Override to implement special test keyword matching with optional phrase"""
        # Strip exclamation mark if present (for command-style messages)
        content = message.content.strip()
        if content.startswith('!'):
            content = content[1:].strip()
        
        # Handle "test" alone or "test " with phrase
        if content.lower() == "test":
            return True  # Just "test" by itself
        elif (content.startswith('test ') or content.startswith('Test ')) and len(content) > 5:
            phrase = content[5:].strip()  # Get everything after "test " and strip whitespace
            return bool(phrase)  # Make sure there's actually a phrase
        
        return False
    
    def get_response_format(self) -> str:
        """Get the response format from config"""
        if self.bot.config.has_section('Keywords'):
            format_str = self.bot.config.get('Keywords', 'test', fallback=None)
            return self._strip_quotes_from_config(format_str) if format_str else None
        return None
    
    def format_response(self, message: MeshMessage, response_format: str) -> str:
        """Override to handle phrase extraction"""
        # Strip exclamation mark if present (for command-style messages)
        content = message.content.strip()
        if content.startswith('!'):
            content = content[1:].strip()
        
        # Extract phrase if present, otherwise use empty string
        if content.lower() == "test":
            phrase = ""
        else:
            phrase = content[5:].strip()  # Get everything after "test "
        
        try:
            connection_info = self.build_enhanced_connection_info(message)
            timestamp = self.format_timestamp(message)
            
            # Format phrase part - add colon and space if phrase exists
            phrase_part = f": {phrase}" if phrase else ""
            
            return response_format.format(
                sender=message.sender_id or "Unknown",
                phrase=phrase,
                phrase_part=phrase_part,
                connection_info=connection_info,
                path=message.path or "Unknown",
                timestamp=timestamp,
                snr=message.snr or "Unknown"
            )
        except (KeyError, ValueError) as e:
            self.logger.warning(f"Error formatting test response: {e}")
            return response_format
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the test command"""
        return await self.handle_keyword_match(message)
