#!/usr/bin/env python3
"""
Advert command for the MeshCore Bot
Handles the 'advert' command for sending flood adverts
"""

import time
from .base_command import BaseCommand
from ..models import MeshMessage


class AdvertCommand(BaseCommand):
    """Handles the advert command"""
    
    def get_help_text(self) -> str:
        return "Sends flood advert (DM only, 1hr cooldown)."
    
    def can_execute(self, message: MeshMessage) -> bool:
        """Check if advert command can be executed"""
        # Only works in DMs
        if not message.is_dm:
            return False
        
        # Check cooldown
        if self.bot.last_advert_time:
            current_time = time.time()
            if (current_time - self.bot.last_advert_time) < 3600:  # 1 hour
                return False
        
        return True
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the advert command"""
        try:
            # Check if enough time has passed since last advert (1 hour)
            current_time = time.time()
            if self.bot.last_advert_time and (current_time - self.bot.last_advert_time) < 3600:
                remaining_time = 3600 - (current_time - self.bot.last_advert_time)
                remaining_minutes = int(remaining_time // 60)
                response = f"Advert cooldown active. Please wait {remaining_minutes} more minutes before requesting another advert."
                await self.bot.command_manager.send_dm(message.sender_id, response)
                return True
            
            self.logger.info(f"User {message.sender_id} requested flood advert")
            
            # Send flood advert
            from meshcore_cli.meshcore_cli import next_cmd
            result = await next_cmd(self.bot.meshcore, ["flood_advert"])
            
            # Update last advert time
            self.bot.last_advert_time = current_time
            
            if result and hasattr(result, 'type'):
                if result.type == 'command_error':
                    response = f"Failed to send flood advert: {result.payload}"
                    self.logger.error(response)
                else:
                    response = "Flood advert sent successfully!"
                    self.logger.info("Flood advert sent successfully via DM command")
            else:
                response = "Flood advert sent successfully!"
                self.logger.info("Flood advert sent successfully via DM command (no result returned)")
            
            await self.bot.command_manager.send_dm(message.sender_id, response)
            return True
            
        except Exception as e:
            error_msg = f"Error sending flood advert: {e}"
            self.logger.error(error_msg)
            await self.bot.command_manager.send_dm(message.sender_id, error_msg)
            return False
