#!/usr/bin/env python3
"""
Help command for the MeshCore Bot
Provides help information for commands and general usage
"""

from .base_command import BaseCommand
from ..models import MeshMessage


class HelpCommand(BaseCommand):
    """Handles the help command"""
    
    # Plugin metadata
    name = "help"
    keywords = ['help']
    description = "Shows commands. Use 'help <command>' for details."
    category = "basic"
    
    def get_help_text(self) -> str:
        return self.description
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the help command"""
        # The help command is now handled by keyword matching in the command manager
        # This is just a placeholder for future functionality
        self.logger.debug("Help command executed (handled by keyword matching)")
        return True
    
    def get_specific_help(self, command_name: str) -> str:
        """Get help text for a specific command"""
        # Map command aliases to their actual command names
        command_aliases = {
            '@': 'at_phrase',
            't': 't_phrase',
            'advert': 'advert',
            'test': 'test',
            'ping': 'ping',
            'help': 'help'
        }
        
        # Normalize the command name
        normalized_name = command_aliases.get(command_name, command_name)
        
        # Get the command instance
        command = self.bot.command_manager.commands.get(normalized_name)
        
        if command:
            return f"**Help for '{command_name}':**\n{command.get_help_text()}"
        else:
            return f"**Unknown command: '{command_name}'**\n\nAvailable commands:\n" + self.get_available_commands_list()
    
    def get_general_help(self) -> str:
        """Get general help text"""
        help_text = "**MeshCore Bot Help**\n\n"
        help_text += "**Available Commands:**\n"
        help_text += self.get_available_commands_list()
        help_text += "\n**Usage Examples:**\n"
        help_text += "• `help @` - Get help for @{string} syntax\n"
        help_text += "• `help t` - Get help for t {string} syntax\n"
        help_text += "• `help advert` - Get help for advert command\n"
        help_text += "• `help test` - Get help for test command\n"
        help_text += "• `help ping` - Get help for ping command\n"
        help_text += "\n**Custom Syntax:**\n"
        help_text += "• `t phrase` - Acknowledgment with phrase (channels & DMs)\n"
        help_text += "• `@{string}` - Acknowledgment with string (DMs only)\n"
        help_text += "• `advert` - Send flood advert (DMs only, 1-hour cooldown)\n"
        
        return help_text
    
    def get_available_commands_list(self) -> str:
        """Get a formatted list of available commands"""
        commands_list = ""
        
        # Group commands by category
        basic_commands = ['test', 'ping', 'help']
        custom_syntax = ['t_phrase', 'at_phrase']  # Use the actual command key
        special_commands = ['advert']
        
        commands_list += "**Basic Commands:**\n"
        for cmd in basic_commands:
            if cmd in self.bot.command_manager.commands:
                help_text = self.bot.command_manager.commands[cmd].get_help_text()
                commands_list += f"• `{cmd}` - {help_text}\n"
        
        commands_list += "\n**Custom Syntax:**\n"
        for cmd in custom_syntax:
            if cmd in self.bot.command_manager.commands:
                help_text = self.bot.command_manager.commands[cmd].get_help_text()
                # Add user-friendly aliases
                if cmd == 't_phrase':
                    commands_list += f"• `t phrase` - {help_text}\n"
                elif cmd == 'at_phrase':
                    commands_list += f"• `@{{string}}` - {help_text}\n"
                else:
                    commands_list += f"• `{cmd}` - {help_text}\n"
        
        commands_list += "\n**Special Commands:**\n"
        for cmd in special_commands:
            if cmd in self.bot.command_manager.commands:
                help_text = self.bot.command_manager.commands[cmd].get_help_text()
                commands_list += f"• `{cmd}` - {help_text}\n"
        
        return commands_list
    

