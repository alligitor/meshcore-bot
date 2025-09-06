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
    
    # Plugin metadata
    name = "hello"
    keywords = ['hello', 'hi', 'hey', 'howdy', 'greetings', 'salutations', 'good morning', 'good afternoon', 'good evening', 'good night', 'yo', 'sup', 'whats up', 'what\'s up', 'morning', 'afternoon', 'evening', 'night', 'gday', 'g\'day', 'hola', 'bonjour', 'ciao', 'namaste', 'aloha', 'shalom', 'konnichiwa', 'guten tag', 'buenos dias', 'buenas tardes', 'buenas noches']
    description = "Responds to greetings with robot-themed responses"
    category = "basic"
    
    def __init__(self, bot):
        super().__init__(bot)
        
        # Time-neutral greeting openings
        self.greeting_openings = [
            "Hello", "Greetings", "Salutations", "Hi", "Hey", "Howdy", "Yo", "Sup", 
            "What's up", "Good day", "Well met", "Hail", "Ahoy", "Bonjour", "Hola", 
            "Ciao", "Namaste", "Aloha", "Shalom", "Konnichiwa", "Guten tag", "G'day", 
            "How goes it", "What's good", "Peace", "Respect", "Blessings", "Cheers", 
            "Welcome", "Nice to see you", "Pleasure to meet you", "Good to see you", 
            "Long time no see", "Fancy meeting you here"
        ]
        
        # Time-based greeting openings
        self.morning_greetings = [
            "Good morning", "Top o' the morning", "Buenos dias", "Bonjour", 
            "Guten morgen", "Buongiorno", "Bom dia", "Dobro jutro", "Dobroye utro",
            "Selamat pagi", "Ohayou gozaimasu", "Sabah al-khair", "Boker tov"
        ]
        
        self.afternoon_greetings = [
            "Good afternoon", "Buenas tardes", "Boa tarde", "Dobro dan", 
            "Dobryy den", "Selamat siang", "Konnichiwa", "Ahlan bi-nahar", 
            "Tzoharaim tovim"
        ]
        
        self.evening_greetings = [
            "Good evening", "Buenas noches", "Boa noite", "Dobro veče", 
            "Dobryy vecher", "Selamat malam", "Konbanwa", "Ahlan bi-layl", 
            "Erev tov"
        ]
        
        # Randomized human descriptors
        self.human_descriptors = [
            # Classic robot references
            "human", "carbon-based lifeform", "organic entity", "biological unit", 
            "flesh creature", "meat-based organism", "carbon unit", "organic being", 
            "biological entity", "meat-based lifeform", "carbon creature", "flesh unit", 
            "organic organism", "biological creature", "meat mech", "flesh bot", "organic automaton",
            "biological android", "carbon construct", "flesh drone", "organic robot",
            "biological machine", "meat cyborg", "flesh android", "organic droid", "biological bot",
            "carbon android", "meat unit", "flesh construct", "organic mech", "biological droid",
            "meat-based bot", "flesh-based unit", "organic-based entity", "biological-based organism",
            "carbon-based unit", "meat-based entity", "flesh-based creature", "organic-based unit",
            
            # Scientific/technical
            "DNA-based lifeform", "neural network user", "bipedal mammal", 
            "water-based organism", "protein assembler", "ATP consumer",
            "cellular automaton", "genetic algorithm", "biochemical processor",
            "metabolic engine", "neural pathway",
            
            # Friendly and approachable
            "human friend", "fellow sentient being", "earthling", "fellow traveler", 
            "kindred spirit", "digital companion", "friend", "buddy", "pal", "mate",
            "fellow human", "earth dweller", "terrestrial being", "planet walker",
            
            # Playful and humorous
            "humanoid", "organic", "biological", "carbon-based buddy",
            "flesh-based friend", "organic pal", "biological buddy", "carbon companion",
            "carbon sack", "organic pipe"
        ]
    
    def get_help_text(self) -> str:
        return self.description
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the hello command"""
        # Get bot name from config
        bot_name = self.bot.config.get('Bot', 'bot_name', fallback='Bot')
        # Get random robot greeting
        random_greeting = self.get_random_greeting()
        response = f"{random_greeting} I'm {bot_name}."
        return await self.send_response(message, response)
    
    def get_random_greeting(self) -> str:
        """Generate a random robot greeting by combining opening and descriptor"""
        import datetime
        import pytz
        
        # Get configured timezone or use system timezone
        timezone_str = self.bot.config.get('Bot', 'timezone', fallback='')
        
        if timezone_str:
            try:
                # Use configured timezone
                tz = pytz.timezone(timezone_str)
                current_time = datetime.datetime.now(tz)
            except pytz.exceptions.UnknownTimeZoneError:
                # Fallback to system timezone if configured timezone is invalid
                current_time = datetime.datetime.now()
        else:
            # Use system timezone
            current_time = datetime.datetime.now()
        
        # Get current hour to determine time of day
        current_hour = current_time.hour
        
        # Choose appropriate greeting based on time of day
        if 5 <= current_hour < 12:  # Morning (5 AM - 12 PM)
            greeting_pool = self.morning_greetings + self.greeting_openings
        elif 12 <= current_hour < 17:  # Afternoon (12 PM - 5 PM)
            greeting_pool = self.afternoon_greetings + self.greeting_openings
        elif 17 <= current_hour < 22:  # Evening (5 PM - 10 PM)
            greeting_pool = self.evening_greetings + self.greeting_openings
        else:  # Night/Late night (10 PM - 5 AM)
            greeting_pool = self.evening_greetings + self.greeting_openings
        
        opening = random.choice(greeting_pool)
        descriptor = random.choice(self.human_descriptors)
        
        # Add some variety in punctuation and formatting
        punctuation_options = ["!", ".", "!", "!", "!"]  # Favor exclamation marks
        punctuation = random.choice(punctuation_options)
        
        # Sometimes add a comma, sometimes not
        if random.choice([True, False]):
            return f"{opening}, {descriptor}{punctuation}"
        else:
            return f"{opening} {descriptor}{punctuation}"
