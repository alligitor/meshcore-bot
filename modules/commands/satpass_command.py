#!/usr/bin/env python3
"""
Satellite Pass Command - Provides satellite pass information
"""

from .base_command import BaseCommand
from ..solar_conditions import get_next_satellite_pass
from ..models import MeshMessage


class SatpassCommand(BaseCommand):
    """Command to get satellite pass information"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.keywords = ['satpass']
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the satpass command"""
        try:
            # Check if user provided a satellite number
            content = message.content.strip()
            if content == 'satpass':
                # No satellite specified, show help
                help_text = "🛰️ Satellite Pass Info\nUsage: satpass <NORAD_number>\nExamples:\n• satpass 25544 (ISS)\n• satpass 33591 (NOAA-15)"
                
                # Send help based on message type
                if message.is_dm:
                    await self.bot.command_manager.send_dm(message.sender_id, help_text)
                else:
                    await self.bot.command_manager.send_channel_message(message.channel, help_text)
                return True
            
            # Extract satellite number from command
            parts = content.split()
            if len(parts) < 2:
                error_msg = "Please provide a satellite NORAD number. Example: satpass 25544"
                if message.is_dm:
                    await self.bot.command_manager.send_dm(message.sender_id, error_msg)
                else:
                    await self.bot.command_manager.send_channel_message(message.channel, error_msg)
                return True
            
            satellite = parts[1]
            
            # Get satellite pass information
            pass_info = get_next_satellite_pass(satellite)
            
            # Send response based on message type
            response = f"🛰️ Satellite Pass:\n{pass_info}"
            if message.is_dm:
                await self.bot.command_manager.send_dm(message.sender_id, response)
            else:
                await self.bot.command_manager.send_channel_message(message.channel, response)
            return True
            
        except Exception as e:
            error_msg = f"Error getting satellite pass info: {e}"
            if message.is_dm:
                await self.bot.command_manager.send_dm(message.sender_id, error_msg)
            else:
                await self.bot.command_manager.send_channel_message(message.channel, error_msg)
            return False
    
    def get_help_text(self):
        """Get help text for this command"""
        return "Get satellite pass info: satpass <NORAD_number>"
