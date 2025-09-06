#!/usr/bin/env python3
"""
Cat Fact command for the MeshCore Bot
Provides random cat facts as a hidden easter egg command
"""

import random
from .base_command import BaseCommand
from ..models import MeshMessage


class CatfactCommand(BaseCommand):
    """Handles cat fact commands - hidden easter egg"""
    
    # Plugin metadata
    name = "catfact"
    keywords = ['catfact', 'cat', 'meow', 'purr', 'kitten']
    description = "Get a random cat fact (hidden command)"
    category = "hidden"  # Hidden category so it won't appear in help
    cooldown_seconds = 3  # 3 second cooldown per user
    
    # Per-user cooldown tracking
    user_cooldowns = {}  # user_id -> last_execution_time
    
    def __init__(self, bot):
        super().__init__(bot)
        
        # Collection of cat facts
        self.cat_facts = [
            "Cats have a third eyelid called a nictitating membrane that helps keep their eyes moist and protected. 🐱",
            "A group of cats is called a 'clowder' or a 'glaring'. 🐈",
            "Cats can rotate their ears 180 degrees independently of each other. 👂",
            "The oldest known pet cat existed 9,500 years ago and was found buried with its human in Cyprus. 🏺",
            "Cats have over 30 muscles controlling their ears, while humans only have 6. 🎧",
            "A cat's purr vibrates at a frequency of 25-150 Hz, which can promote healing of bones and tissues. 🩹",
            "Cats spend 70% of their lives sleeping - that's 13-16 hours per day! 😴",
            "A cat's nose print is unique, just like human fingerprints. 👃",
            "Cats can't taste sweetness - they lack the taste receptors for sugar. 🍭",
            "The world's richest cat, Blackie, inherited £7 million from his owner in 1988. 💰",
            "Cats have a very small, free-floating clavicle that allows them to always land on their feet. 🦴",
            "A cat's heart beats 140-220 times per minute, about twice as fast as a human's heart. ❤️",
            "Cats have been known to survive falls from heights of over 20 stories due to their righting reflex. 🏢",
            "The technical term for a cat's hairball is a 'bezoar'. 🤮",
            "Cats can jump up to 6 times their body length in a single bound. 🦘",
            "A cat's whiskers are roughly as wide as their body, helping them judge if they can fit through spaces. 📏",
            "Cats have 32 muscles in each ear, compared to humans' 6. 🎯",
            "The oldest cat ever recorded lived to be 38 years and 3 days old. 🎂",
            "Cats can run up to 30 mph in short bursts. 🏃‍♂️",
            "A cat's brain is 90% similar to a human's brain - they have the same regions for emotions. 🧠",
            "Cats have a special organ called the Jacobson's organ that allows them to 'taste' smells. 👅",
            "The first cat in space was a French cat named Félicette, launched in 1963. 🚀",
            "Cats can see in near darkness - they only need 1/6th the light humans need to see. 🌙",
            "A cat's tail contains nearly 10% of all the bones in its body. 🦴",
            "Cats have been domesticated for over 4,000 years, longer than dogs. 🏛️",
            "The world's largest cat measured 48.5 inches long from nose to tail tip. 📏",
            "Cats can make over 100 different sounds, while dogs can only make about 10. 🎵",
            "A cat's sense of smell is 14 times stronger than a human's. 👃",
            "Cats have a 'flehmen response' where they curl their lip to better detect scents. 😬",
            "The first cat show was held in London in 1871. 🏆",
            "Cats can drink seawater to survive - their kidneys can filter out the salt. 🌊",
            "A cat's purr can help lower blood pressure and reduce stress in humans. 🧘‍♀️",
            "Cats have been known to travel hundreds of miles to return to their homes. 🗺️",
            "The smallest cat breed is the Singapura, weighing only 4-8 pounds. ⚖️",
            "Cats can see ultraviolet light, which humans cannot see. 🌈",
            "A cat's tongue is covered in tiny, backward-facing hooks called papillae. 🪝",
            "Cats have been worshipped as gods in ancient Egypt - they never forgot this. 👑",
            "The world's most expensive cat breed is the Ashera, costing up to $125,000. 💎",
            "Cats can rotate their ears 180 degrees and move them independently. 🎧",
            "A cat's heart beats 140-220 times per minute, twice as fast as a human's. 💓"
        ]
    
    def get_help_text(self) -> str:
        # Return empty string so it doesn't appear in help
        return ""
    
    def can_execute(self, message: MeshMessage) -> bool:
        """Override cooldown check to be per-user instead of per-command-instance"""
        # Check if command requires DM and message is not DM
        if self.requires_dm and not message.is_dm:
            return False
        
        # Check per-user cooldown
        if self.cooldown_seconds > 0:
            import time
            current_time = time.time()
            user_id = message.sender_id
            
            if user_id in self.user_cooldowns:
                last_execution = self.user_cooldowns[user_id]
                if (current_time - last_execution) < self.cooldown_seconds:
                    return False
        
        return True
    
    def get_remaining_cooldown(self, user_id: str) -> int:
        """Get remaining cooldown time for a specific user"""
        if self.cooldown_seconds <= 0:
            return 0
        
        import time
        current_time = time.time()
        if user_id in self.user_cooldowns:
            last_execution = self.user_cooldowns[user_id]
            elapsed = current_time - last_execution
            remaining = self.cooldown_seconds - elapsed
            return max(0, int(remaining))
        
        return 0
    
    def _record_execution(self, user_id: str):
        """Record the execution time for a specific user"""
        import time
        self.user_cooldowns[user_id] = time.time()
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the cat fact command"""
        try:
            # Record execution for this user
            self._record_execution(message.sender_id)
            
            # Get a random cat fact
            cat_fact = random.choice(self.cat_facts)
            
            # Send the cat fact
            await self.send_response(message, cat_fact)
            return True
            
        except Exception as e:
            self.logger.error(f"Error in cat fact command: {e}")
            await self.send_response(message, "Meow? Something went wrong getting your cat fact! 🐱")
            return True
