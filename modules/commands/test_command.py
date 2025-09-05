#!/usr/bin/env python3
"""
Test command for the MeshCore Bot
Handles the 'test' keyword response
"""

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
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the test command"""
        # The test command is handled by keyword matching in the command manager
        # This is just a placeholder for future functionality
        self.logger.debug("Test command executed (handled by keyword matching)")
        return True
