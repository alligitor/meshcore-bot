#!/usr/bin/env python3
"""
HF Conditions Command - Provides HF band conditions for ham radio
"""

from .base_command import BaseCommand
from ..solar_conditions import hf_band_conditions
from ..models import MeshMessage


class HfcondCommand(BaseCommand):
    """Command to get HF band conditions"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.keywords = ['hfcond']
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the hfcond command"""
        try:
            # Get HF band conditions
            hf_info = hf_band_conditions()
            
            # Send response based on message type
            response = f"📡 HF Band Conditions:\n{hf_info}"
            if message.is_dm:
                await self.bot.command_manager.send_dm(message.sender_id, response)
            else:
                await self.bot.command_manager.send_channel_message(message.channel, response)
            return True
            
        except Exception as e:
            error_msg = f"Error getting HF conditions: {e}"
            if message.is_dm:
                await self.bot.command_manager.send_dm(message.sender_id, error_msg)
            else:
                await self.bot.command_manager.send_channel_message(message.channel, error_msg)
            return False
    
    def get_help_text(self):
        """Get help text for this command"""
        return "Get HF band conditions for ham radio"
