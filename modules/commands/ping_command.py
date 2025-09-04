#!/usr/bin/env python3
"""
Ping command for the MeshCore Bot
Handles the 'ping' keyword response
"""

from .base_command import BaseCommand
from ..models import MeshMessage


class PingCommand(BaseCommand):
    """Handles the ping command"""
    
    def get_help_text(self) -> str:
        return "Responds to 'ping' with 'Pong!'."
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the ping command"""
        # The ping command is handled by keyword matching in the command manager
        # This is just a placeholder for future functionality
        self.logger.debug("Ping command executed (handled by keyword matching)")
        return True
