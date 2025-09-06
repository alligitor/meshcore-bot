#!/usr/bin/env python3
"""
T-Phrase command for the MeshCore Bot
Handles the 't phrase' syntax for acknowledgments
"""

from .base_command import BaseCommand
from ..models import MeshMessage


class TPhraseCommand(BaseCommand):
    """Handles the t_phrase command"""
    
    # Plugin metadata
    name = "t_phrase"
    keywords = ['t phrase', 'phrase']  # Removed 't' to avoid conflicts
    description = "Responds to 't phrase' with ack + connection info"
    category = "custom_syntax"
    
    def get_help_text(self) -> str:
        return "Responds to 't phrase' with ack + connection info."
    
    def matches_custom_syntax(self, message: MeshMessage) -> bool:
        """Check if message matches t_phrase syntax"""
        # Strip exclamation mark if present (for command-style messages)
        content = message.content.strip()
        if content.startswith('!'):
            content = content[1:].strip()
        
        # Handle "t " or "T " phrase syntax
        if (content.startswith('t ') or content.startswith('T ')) and len(content) > 2:
            phrase = content[2:].strip()  # Get everything after "t " or "T " and strip whitespace
            return bool(phrase)  # Make sure there's actually a phrase
        return False
    
    def get_response_format(self) -> str:
        """Get the response format from config"""
        if self.bot.config.has_section('Custom_Syntax'):
            format_str = self.bot.config.get('Custom_Syntax', 't_phrase', fallback=None)
            return self._strip_quotes_from_config(format_str) if format_str else None
        return None
    
    def format_response(self, message: MeshMessage, response_format: str) -> str:
        """Override to handle phrase extraction"""
        # Strip exclamation mark if present (for command-style messages)
        content = message.content.strip()
        if content.startswith('!'):
            content = content[1:].strip()
        phrase = content[2:].strip()  # Get everything after "t " or "T "
        
        try:
            connection_info = self.build_enhanced_connection_info(message)
            timestamp = self.format_timestamp(message)
            
            return response_format.format(
                sender=message.sender_id or "Unknown",
                phrase=phrase,
                connection_info=connection_info,
                path=message.path or "Unknown",
                timestamp=timestamp,
                snr=message.snr or "Unknown"
            )
        except (KeyError, ValueError) as e:
            self.logger.warning(f"Error formatting t_phrase response: {e}")
            return response_format
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the t_phrase command"""
        return await self.handle_keyword_match(message)
