#!/usr/bin/env python3
"""
MeshCore Bot CLI - Command-line interface for managing the MeshCore bot
"""

import asyncio
import argparse
import sys
from meshcore_bot import MeshCoreBot


class BotCLI:
    """Command-line interface for MeshCore bot management"""
    
    def __init__(self, config_file: str = "config.ini"):
        self.bot = MeshCoreBot(config_file)
    
    async def add_keyword(self, keyword: str, response: str):
        """Add a new keyword-response pair"""
        self.bot.add_keyword(keyword, response)
        print(f"Added keyword '{keyword}' with response: {response}")
    
    async def remove_keyword(self, keyword: str):
        """Remove a keyword-response pair"""
        self.bot.remove_keyword(keyword)
        print(f"Removed keyword '{keyword}'")
    
    async def list_keywords(self):
        """List all keyword-response pairs"""
        if not self.bot.keywords:
            print("No keywords configured")
            return
        
        print("Configured keywords:")
        for keyword, response in self.bot.keywords.items():
            print(f"  {keyword}: {response}")
    
    async def ban_user(self, user_id: str):
        """Ban a user"""
        self.bot.ban_user(user_id)
        print(f"User {user_id} has been banned")
    
    async def unban_user(self, user_id: str):
        """Unban a user"""
        self.bot.unban_user(user_id)
        print(f"User {user_id} has been unbanned")
    
    async def list_banned_users(self):
        """List all banned users"""
        if not self.bot.banned_users:
            print("No banned users")
            return
        
        print("Banned users:")
        for user_id in self.bot.banned_users:
            print(f"  {user_id}")
    
    async def send_message(self, channel: str, message: str):
        """Send a message to a channel"""
        if await self.bot.connect():
            success = await self.bot.send_message(channel, message)
            if success:
                print(f"Message sent to {channel}: {message}")
            else:
                print("Failed to send message")
            self.bot.disconnect()
        else:
            print("Failed to connect to MeshCore node")
    
    async def add_scheduled_message(self, time: str, channel: str, message: str):
        """Add a scheduled message"""
        message_info = f"{channel}:{message}"
        self.bot.config.set('Scheduled_Messages', time, message_info)
        self.bot.save_config()
        print(f"Scheduled message added: {time} -> {channel}: {message}")
    
    async def list_scheduled_messages(self):
        """List all scheduled messages"""
        if self.bot.config.has_section('Scheduled_Messages'):
            messages = dict(self.bot.config.items('Scheduled_Messages'))
            if messages:
                print("Scheduled messages:")
                for time, message_info in messages.items():
                    try:
                        channel, message = message_info.split(':', 1)
                        print(f"  {time}: {channel} -> {message}")
                    except ValueError:
                        print(f"  {time}: {message_info} (invalid format)")
            else:
                print("No scheduled messages")
        else:
            print("No scheduled messages")
    
    async def remove_scheduled_message(self, time: str):
        """Remove a scheduled message"""
        if self.bot.config.has_option('Scheduled_Messages', time):
            self.bot.config.remove_option('Scheduled_Messages', time)
            self.bot.save_config()
            print(f"Removed scheduled message at {time}")
        else:
            print(f"No scheduled message found at {time}")
    
    async def show_status(self):
        """Show bot status and configuration"""
        print("MeshCore Bot Status:")
        print(f"  Bot Name: {self.bot.config.get('Bot', 'bot_name')}")
        print(f"  Enabled: {self.bot.config.getboolean('Bot', 'enabled')}")
        print(f"  Passive Mode: {self.bot.config.getboolean('Bot', 'passive_mode')}")
        print(f"  Rate Limit: {self.bot.config.getint('Bot', 'rate_limit_seconds')} seconds")
        print(f"  Connection Type: {self.bot.config.get('Connection', 'connection_type')}")
        
        if self.bot.config.get('Connection', 'connection_type') == 'serial':
            print(f"  Serial Port: {self.bot.config.get('Connection', 'serial_port')}")
        else:
            print(f"  BLE Device: {self.bot.config.get('Connection', 'ble_device_name')}")
        
        print(f"  Monitor Channels: {', '.join(self.bot.monitor_channels)}")
        print(f"  Respond to DMs: {self.bot.config.getboolean('Channels', 'respond_to_dms')}")
        print(f"  Keywords: {len(self.bot.keywords)}")
        print(f"  Banned Users: {len(self.bot.banned_users)}")
        
        if self.bot.config.has_section('Scheduled_Messages'):
            scheduled_count = len(dict(self.bot.config.items('Scheduled_Messages')))
            print(f"  Scheduled Messages: {scheduled_count}")
    
    async def run_interactive(self):
        """Run interactive CLI mode"""
        print("MeshCore Bot CLI - Interactive Mode")
        print("Type 'help' for available commands, 'quit' to exit")
        
        while True:
            try:
                command = input("\nbot> ").strip()
                if not command:
                    continue
                
                parts = command.split()
                cmd = parts[0].lower()
                
                if cmd == 'quit' or cmd == 'exit':
                    break
                elif cmd == 'help':
                    self.show_help()
                elif cmd == 'status':
                    await self.show_status()
                elif cmd == 'keywords':
                    await self.list_keywords()
                elif cmd == 'add-keyword':
                    if len(parts) >= 3:
                        keyword = parts[1]
                        response = ' '.join(parts[2:])
                        await self.add_keyword(keyword, response)
                    else:
                        print("Usage: add-keyword <keyword> <response>")
                elif cmd == 'remove-keyword':
                    if len(parts) >= 2:
                        await self.remove_keyword(parts[1])
                    else:
                        print("Usage: remove-keyword <keyword>")
                elif cmd == 'ban':
                    if len(parts) >= 2:
                        await self.ban_user(parts[1])
                    else:
                        print("Usage: ban <user_id>")
                elif cmd == 'unban':
                    if len(parts) >= 2:
                        await self.unban_user(parts[1])
                    else:
                        print("Usage: unban <user_id>")
                elif cmd == 'banned':
                    await self.list_banned_users()
                elif cmd == 'send':
                    if len(parts) >= 3:
                        channel = parts[1]
                        message = ' '.join(parts[2:])
                        await self.send_message(channel, message)
                    else:
                        print("Usage: send <channel> <message>")
                elif cmd == 'schedule':
                    await self.list_scheduled_messages()
                elif cmd == 'add-schedule':
                    if len(parts) >= 4:
                        time = parts[1]
                        channel = parts[2]
                        message = ' '.join(parts[3:])
                        await self.add_scheduled_message(time, channel, message)
                    else:
                        print("Usage: add-schedule <time> <channel> <message>")
                elif cmd == 'remove-schedule':
                    if len(parts) >= 2:
                        await self.remove_scheduled_message(parts[1])
                    else:
                        print("Usage: remove-schedule <time>")
                else:
                    print(f"Unknown command: {cmd}")
                    print("Type 'help' for available commands")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def show_help(self):
        """Show help information"""
        print("Available commands:")
        print("  status                    - Show bot status and configuration")
        print("  keywords                  - List all keyword-response pairs")
        print("  add-keyword <k> <r>       - Add keyword-response pair")
        print("  remove-keyword <k>        - Remove keyword-response pair")
        print("  ban <user_id>             - Ban a user")
        print("  unban <user_id>           - Unban a user")
        print("  banned                    - List banned users")
        print("  send <channel> <message>  - Send message to channel")
        print("  schedule                  - List scheduled messages")
        print("  add-schedule <t> <c> <m>  - Add scheduled message (time format: HH:MM)")
        print("  remove-schedule <time>    - Remove scheduled message")
        print("  help                      - Show this help")
        print("  quit/exit                 - Exit CLI")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="MeshCore Bot CLI")
    parser.add_argument('--config', '-c', default='config.ini', help='Configuration file path')
    parser.add_argument('--interactive', '-i', action='store_true', help='Run in interactive mode')
    
    # Command subparsers
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Status command
    subparsers.add_parser('status', help='Show bot status')
    
    # Keywords commands
    keywords_parser = subparsers.add_parser('keywords', help='Manage keywords')
    keywords_subparsers = keywords_parser.add_subparsers(dest='keyword_command')
    keywords_subparsers.add_parser('list', help='List all keywords')
    
    add_keyword_parser = keywords_subparsers.add_parser('add', help='Add keyword')
    add_keyword_parser.add_argument('keyword', help='Keyword to add')
    add_keyword_parser.add_argument('response', help='Response message')
    
    remove_keyword_parser = keywords_subparsers.add_parser('remove', help='Remove keyword')
    remove_keyword_parser.add_argument('keyword', help='Keyword to remove')
    
    # User management commands
    users_parser = subparsers.add_parser('users', help='Manage users')
    users_subparsers = users_parser.add_subparsers(dest='user_command')
    users_subparsers.add_parser('banned', help='List banned users')
    
    ban_parser = users_subparsers.add_parser('ban', help='Ban user')
    ban_parser.add_argument('user_id', help='User ID to ban')
    
    unban_parser = users_subparsers.add_parser('unban', help='Unban user')
    unban_parser.add_argument('user_id', help='User ID to unban')
    
    # Message commands
    send_parser = subparsers.add_parser('send', help='Send message')
    send_parser.add_argument('channel', help='Channel to send to')
    send_parser.add_argument('message', help='Message to send')
    
    # Scheduled messages commands
    schedule_parser = subparsers.add_parser('schedule', help='Manage scheduled messages')
    schedule_subparsers = schedule_parser.add_subparsers(dest='schedule_command')
    schedule_subparsers.add_parser('list', help='List scheduled messages')
    
    add_schedule_parser = schedule_subparsers.add_parser('add', help='Add scheduled message')
    add_schedule_parser.add_argument('time', help='Time (HH:MM format)')
    add_schedule_parser.add_argument('channel', help='Channel')
    add_schedule_parser.add_argument('message', help='Message')
    
    remove_schedule_parser = schedule_subparsers.add_parser('remove', help='Remove scheduled message')
    remove_schedule_parser.add_argument('time', help='Time to remove')
    
    args = parser.parse_args()
    
    if args.interactive or not args.command:
        # Run interactive mode
        cli = BotCLI(args.config)
        asyncio.run(cli.run_interactive())
    else:
        # Run single command
        cli = BotCLI(args.config)
        
        async def run_command():
            if args.command == 'status':
                await cli.show_status()
            elif args.command == 'keywords':
                if args.keyword_command == 'list':
                    await cli.list_keywords()
                elif args.keyword_command == 'add':
                    await cli.add_keyword(args.keyword, args.response)
                elif args.keyword_command == 'remove':
                    await cli.remove_keyword(args.keyword)
            elif args.command == 'users':
                if args.user_command == 'banned':
                    await cli.list_banned_users()
                elif args.user_command == 'ban':
                    await cli.ban_user(args.user_id)
                elif args.user_command == 'unban':
                    await cli.unban_user(args.user_id)
            elif args.command == 'send':
                await cli.send_message(args.channel, args.message)
            elif args.command == 'schedule':
                if args.schedule_command == 'list':
                    await cli.list_scheduled_messages()
                elif args.schedule_command == 'add':
                    await cli.add_scheduled_message(args.time, args.channel, args.message)
                elif args.schedule_command == 'remove':
                    await cli.remove_scheduled_message(args.time)
        
        asyncio.run(run_command())


if __name__ == "__main__":
    main()
