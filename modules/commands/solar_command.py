#!/usr/bin/env python3
"""
Solar Command - Provides solar conditions and HF band information
"""

from .base_command import BaseCommand
from ..solar_conditions import solar_conditions, hf_band_conditions
from ..models import MeshMessage


class SolarCommand(BaseCommand):
    """Command to get solar conditions"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.keywords = ['solar']
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the solar command"""
        try:
            # Get solar conditions (more readable format)
            solar_info = solar_conditions()
            
            # Send response (solar only, more readable)
            response = f"☀️ Solar: {solar_info}"
            
            # Send response based on message type
            if message.is_dm:
                await self.bot.command_manager.send_dm(message.sender_id, response)
            else:
                await self.bot.command_manager.send_channel_message(message.channel, response)
            return True
            
        except Exception as e:
            error_msg = f"Error getting solar info: {e}"
            if message.is_dm:
                await self.bot.command_manager.send_dm(message.sender_id, error_msg)
            else:
                await self.bot.command_manager.send_channel_message(message.channel, error_msg)
            return False
    
    def get_help_text(self):
        """Get help text for this command"""
        return "Get solar conditions and HF band status"
