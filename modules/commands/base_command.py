#!/usr/bin/env python3
"""
Base command class for all MeshCore Bot commands
Provides common functionality and interface for command implementations
"""

from abc import ABC, abstractmethod
from typing import Optional
from ..models import MeshMessage


class BaseCommand(ABC):
    """Base class for all bot commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
    
    @abstractmethod
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the command with the given message"""
        pass
    
    def get_help_text(self) -> str:
        """Get help text for this command"""
        return "No help available for this command."
    
    def can_execute(self, message: MeshMessage) -> bool:
        """Check if this command can be executed with the given message"""
        return True
