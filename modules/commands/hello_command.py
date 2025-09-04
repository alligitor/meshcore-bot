#!/usr/bin/env python3
"""
Hello command for the MeshCore Bot
Responds to various greetings with robot-themed responses
"""

import random
from .base_command import BaseCommand
from ..models import MeshMessage


class HelloCommand(BaseCommand):
    """Handles various greeting commands"""
    
    def __init__(self, bot):
        super().__init__(bot)
        # Robot greetings from popular culture
        self.robot_greetings = [
            "Greetings, human!",
            "Hello, meatbag!",
            "Salutations, carbon-based lifeform!",
            "Greetings, organic entity!",
            "Hello, biological unit!",
            "Salutations, flesh creature!",
            "Greetings, meat-based organism!",
            "Hello, carbon unit!",
            "Salutations, organic being!",
            "Greetings, biological entity!",
            "Hello, meat-based lifeform!",
            "Salutations, carbon creature!",
            "Greetings, flesh unit!",
            "Hello, organic organism!",
            "Salutations, biological creature!"
        ]
    
    def get_help_text(self) -> str:
        return "Responds to greetings with robot-themed responses."
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the hello command"""
        # The hello command is handled by keyword matching in the command manager
        # This is just a placeholder for future functionality
        self.logger.debug("Hello command executed (handled by keyword matching)")
        return True
    
    def get_random_greeting(self) -> str:
        """Get a random robot greeting"""
        return random.choice(self.robot_greetings)
