#!/usr/bin/env python3
"""
At-Phrase command for the MeshCore Bot
Handles the '@{string}' syntax for acknowledgments (DM only)
"""

from .base_command import BaseCommand
from ..models import MeshMessage


class AtPhraseCommand(BaseCommand):
    """Handles the @{string} command (DM and non-Public channels)"""
    
    # Plugin metadata
    name = "at_phrase"
    keywords = ['@', '@string', 'string']
    description = "Responds to '@{string}' with ack + connection info (DM and non-Public channels)"
    category = "custom_syntax"
    requires_dm = False  # Allow in channels, but restrict to non-Public channels in matches_custom_syntax
    
    def get_help_text(self) -> str:
        return "Responds to '@{string}' with ack + connection info (DM and non-Public channels)."
    
    def matches_custom_syntax(self, message: MeshMessage) -> bool:
        """Check if message matches @_phrase syntax"""
        # Strip exclamation mark if present (for command-style messages)
        content = message.content.strip()
        if content.startswith('!'):
            content = content[1:].strip()
        
        # Handle "@{string}" phrase syntax (DM and non-Public channels only)
        if content.startswith('@') and len(content) > 1:
            # Check if this is a DM or a non-Public channel
            is_allowed = message.is_dm
            if not message.is_dm and message.channel:
                # Allow in all channels except "Public"
                is_allowed = message.channel.lower() != "public"
            
            if is_allowed:
                phrase = content[1:].strip()  # Get everything after "@" and strip whitespace
                return bool(phrase)  # Make sure there's actually a phrase
        return False
    
    def get_response_format(self) -> str:
        """Get the response format from config"""
        if self.bot.config.has_section('Custom_Syntax'):
            format_str = self.bot.config.get('Custom_Syntax', '@_phrase', fallback=None)
            return self._strip_quotes_from_config(format_str) if format_str else None
        return None
    
    def format_response(self, message: MeshMessage, response_format: str) -> str:
        """Override to handle phrase extraction"""
        # Strip exclamation mark if present (for command-style messages)
        content = message.content.strip()
        if content.startswith('!'):
            content = content[1:].strip()
        phrase = content[1:].strip()  # Get everything after "@"
        
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
            self.logger.warning(f"Error formatting @_phrase response: {e}")
            return response_format
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the @{string} command"""
        return await self.handle_keyword_match(message)
