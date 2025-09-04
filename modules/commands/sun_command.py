#!/usr/bin/env python3
"""
Sun Command - Provides sunrise/sunset information
"""

from .base_command import BaseCommand
from ..solar_conditions import get_sun
from ..models import MeshMessage


class SunCommand(BaseCommand):
    """Command to get sun information"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.keywords = ['sun']
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the sun command"""
        try:
            # Get sun information using default location
            sun_info = get_sun()
            
            # Send response based on message type
            response = f"☀️ Sun Info:\n{sun_info}"
            if message.is_dm:
                await self.bot.command_manager.send_dm(message.sender_id, response)
            else:
                await self.bot.command_manager.send_channel_message(message.channel, response)
            return True
            
        except Exception as e:
            error_msg = f"Error getting sun info: {e}"
            if message.is_dm:
                await self.bot.command_manager.send_dm(message.sender_id, error_msg)
            else:
                await self.bot.command_manager.send_channel_message(message.channel, error_msg)
            return False
    
    def get_help_text(self):
        """Get help text for this command"""
        return "Get sunrise/sunset times and sun position"
