#!/usr/bin/env python3
"""
At-Phrase command for the MeshCore Bot
Handles the '@{string}' syntax for acknowledgments (DM only)
"""

from .base_command import BaseCommand
from ..models import MeshMessage


class AtPhraseCommand(BaseCommand):
    """Handles the @{string} command (DM only)"""
    
    def get_help_text(self) -> str:
        return "Responds to '@{string}' with ack + connection info (DM only)."
    
    def can_execute(self, message: MeshMessage) -> bool:
        """Check if @{string} command can be executed"""
        # Only works in DMs
        return message.is_dm
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the @{string} command"""
        # The @{string} command is handled by custom syntax matching in the command manager
        # This is just a placeholder for future functionality
        self.logger.debug("At-Phrase command executed (handled by custom syntax matching)")
        return True
