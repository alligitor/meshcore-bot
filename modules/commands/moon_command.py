#!/usr/bin/env python3
"""
Moon Command - Provides moon phase and position information
"""

from .base_command import BaseCommand
from ..solar_conditions import get_moon
from ..models import MeshMessage


class MoonCommand(BaseCommand):
    """Command to get moon information"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.keywords = ['moon']
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the moon command"""
        try:
            # Get moon information using default location
            moon_info = get_moon()
            
            # Send response based on message type
            response = f"🌙 Moon Info:\n{moon_info}"
            if message.is_dm:
                await self.bot.command_manager.send_dm(message.sender_id, response)
            else:
                await self.bot.command_manager.send_channel_message(message.channel, response)
            return True
            
        except Exception as e:
            error_msg = f"Error getting moon info: {e}"
            if message.is_dm:
                await self.bot.command_manager.send_dm(message.sender_id, error_msg)
            else:
                await self.bot.command_manager.send_channel_message(message.channel, error_msg)
            return False
    
    def get_help_text(self):
        """Get help text for this command"""
        return "Get moon phase, rise/set times and position"
