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
        """Override to implement special test keyword matching"""
        content_lower = message.content.lower().strip()
        
        # For "test", only match if it's the first word or its own word
        # Split by whitespace and clean up punctuation
        words = re.findall(r'\b\w+\b', content_lower)
        if words and (words[0] == "test" or "test" in words):
            return True
        
        return False
    
    def get_response_format(self) -> str:
        """Get the response format from config"""
        if self.bot.config.has_section('Keywords'):
            format_str = self.bot.config.get('Keywords', 'test', fallback=None)
            return self._strip_quotes_from_config(format_str) if format_str else None
        return None
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the test command"""
        return await self.handle_keyword_match(message)
