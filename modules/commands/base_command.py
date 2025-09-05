#!/usr/bin/env python3
"""
Base command class for all MeshCore Bot commands
Provides common functionality and interface for command implementations
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from ..models import MeshMessage


class BaseCommand(ABC):
    """Base class for all bot commands - Plugin Interface"""
    
    # Plugin metadata - to be overridden by subclasses
    name: str = ""
    keywords: List[str] = []
    description: str = ""
    aliases: List[str] = []
    requires_dm: bool = False
    cooldown_seconds: int = 0
    category: str = "general"
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self._last_execution_time = 0
    
    @abstractmethod
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the command with the given message"""
        pass
    
    def get_help_text(self) -> str:
        """Get help text for this command"""
        return self.description or "No help available for this command."
    
    def can_execute(self, message: MeshMessage) -> bool:
        """Check if this command can be executed with the given message"""
        # Check if command requires DM and message is not DM
        if self.requires_dm and not message.is_dm:
            return False
        
        # Check cooldown
        if self.cooldown_seconds > 0:
            import time
            current_time = time.time()
            if (current_time - self._last_execution_time) < self.cooldown_seconds:
                return False
        
        return True
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get plugin metadata for discovery and registration"""
        return {
            'name': self.name,
            'keywords': self.keywords,
            'description': self.description,
            'aliases': self.aliases,
            'requires_dm': self.requires_dm,
            'cooldown_seconds': self.cooldown_seconds,
            'category': self.category,
            'class_name': self.__class__.__name__,
            'module_name': self.__class__.__module__
        }
    
    async def send_response(self, message: MeshMessage, content: str) -> bool:
        """Unified method for sending responses to users"""
        try:
            if message.is_dm:
                return await self.bot.command_manager.send_dm(message.sender_id, content)
            else:
                return await self.bot.command_manager.send_channel_message(message.channel, content)
        except Exception as e:
            self.logger.error(f"Failed to send response: {e}")
            return False
    
    def _record_execution(self):
        """Record the execution time for cooldown tracking"""
        import time
        self._last_execution_time = time.time()
    
    def get_remaining_cooldown(self) -> int:
        """Get remaining cooldown time in seconds"""
        if self.cooldown_seconds <= 0:
            return 0
        
        import time
        current_time = time.time()
        elapsed = current_time - self._last_execution_time
        remaining = self.cooldown_seconds - elapsed
        return max(0, int(remaining))
