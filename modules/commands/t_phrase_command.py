#!/usr/bin/env python3
"""
T-Phrase command for the MeshCore Bot
Handles the 't phrase' syntax for acknowledgments
"""

from .base_command import BaseCommand
from ..models import MeshMessage


class TPhraseCommand(BaseCommand):
    """Handles the t_phrase command"""
    
    def get_help_text(self) -> str:
        return "Responds to 't phrase' with ack + connection info."
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the t_phrase command"""
        # The t_phrase command is handled by custom syntax matching in the command manager
        # This is just a placeholder for future functionality
        self.logger.debug("T-Phrase command executed (handled by custom syntax matching)")
        return True
