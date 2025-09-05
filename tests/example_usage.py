#!/usr/bin/env python3
"""
Example usage of the MeshCore Bot Framework
This script demonstrates common use cases and how to extend the bot.
"""

import asyncio
import configparser
from meshcore_bot import MeshCoreBot
from meshcore_protocol import MeshCoreMessage, MessageType


class ExtendedMeshCoreBot(MeshCoreBot):
    """Extended bot with additional features"""
    
    def __init__(self, config_file: str = "config.ini"):
        super().__init__(config_file)
        self.message_count = 0
        self.custom_handlers = []
    
    def add_custom_handler(self, handler_func):
        """Add a custom message handler"""
        self.custom_handlers.append(handler_func)
        self.logger.info(f"Added custom handler: {handler_func.__name__}")
    
    async def process_message(self, message: MeshCoreMessage):
        """Override to add custom processing"""
        # Call parent processing first
        await super().process_message(message)
        
        # Run custom handlers
        for handler in self.custom_handlers:
            try:
                await handler(message)
            except Exception as e:
                self.logger.error(f"Custom handler error: {e}")
        
        # Track message count
        self.message_count += 1
        if self.message_count % 10 == 0:
            self.logger.info(f"Processed {self.message_count} messages")


async def weather_handler(message: MeshCoreMessage):
    """Custom handler for weather requests"""
    if "weather" in message.content.lower():
        # Simulate weather API call
        weather_data = "Sunny, 22°C, Humidity: 65%"
        response = f"Weather update: {weather_data}"
        
        # Send response (this would need access to the bot instance)
        # await bot.send_message(message.channel, response)
        print(f"Weather request from {message.sender_id}: {response}")


async def stats_handler(message: MeshCoreMessage):
    """Custom handler for statistics requests"""
    if "stats" in message.content.lower():
        stats = "Bot Statistics:\n- Messages processed: 42\n- Active users: 15\n- Network health: Good"
        print(f"Stats request from {message.sender_id}: {stats}")


async def echo_handler(message: MeshCoreMessage):
    """Custom handler for echo functionality"""
    if message.content.startswith("echo "):
        echo_text = message.content[5:]  # Remove "echo " prefix
        response = f"Echo: {echo_text}"
        print(f"Echo from {message.sender_id}: {response}")


def create_example_config():
    """Create an example configuration file"""
    config = configparser.ConfigParser()
    
    config['Connection'] = {
        'connection_type': 'serial',
        'serial_port': '/dev/ttyUSB0',
        'serial_baudrate': '115200',
        'ble_device_name': 'MeshCore',
        'timeout': '30'
    }
    
    config['Bot'] = {
        'bot_name': 'ExampleBot',
        'node_id': '',
        'enabled': 'true',
        'passive_mode': 'false',
        'rate_limit_seconds': '10'
    }
    
    config['Keywords'] = {
        'test': 'Message received! Hops: {hops}, Path: {path}, From: {sender}',
        'hello': 'Hello {sender}! Welcome to the MeshCore network.',
        'help': 'Available commands: test, hello, help, weather, stats, echo <message>',
        'ping': 'Pong! Response time: {timestamp}',
        'info': 'Bot Info: {sender} sent "{content}" via {channel}'
    }
    
    config['Channels'] = {
        'monitor_channels': 'general,test,emergency,weather',
        'respond_to_dms': 'true'
    }
    
    config['Banned_Users'] = {
        'banned_users': ''
    }
    
    config['Scheduled_Messages'] = {
        '08:00': 'general:Good morning! Weather update coming soon.',
        '12:00': 'general:Lunch time reminder - stay hydrated!',
        '18:00': 'general:Evening update - network status: Good'
    }
    
    config['Logging'] = {
        'log_level': 'INFO',
        'log_file': 'example_bot.log',
        'colored_output': 'true'
    }
    
    config['External_Data'] = {
        'weather_api_key': '',
        'weather_update_interval': '3600',
        'tide_api_key': '',
        'tide_update_interval': '1800'
    }
    
    with open('example_config.ini', 'w') as f:
        config.write(f)
    
    print("Created example_config.ini")


async def run_example_bot():
    """Run the example bot with custom handlers"""
    print("Starting Example MeshCore Bot...")
    
    # Create example config if it doesn't exist
    try:
        with open('example_config.ini', 'r'):
            pass
    except FileNotFoundError:
        create_example_config()
    
    # Create extended bot
    bot = ExtendedMeshCoreBot('example_config.ini')
    
    # Add custom handlers
    bot.add_custom_handler(weather_handler)
    bot.add_custom_handler(stats_handler)
    bot.add_custom_handler(echo_handler)
    
    # Add some example keywords
    bot.add_keyword("weather", "Current weather: Sunny, 22°C")
    bot.add_keyword("stats", "Network stats: 15 nodes, 3 hops max")
    bot.add_keyword("time", "Current time: {timestamp}")
    
    # Start the bot
    try:
        await bot.start()
    except KeyboardInterrupt:
        print("\nShutting down example bot...")
        bot.stop()
    except Exception as e:
        print(f"Error running example bot: {e}")
        bot.stop()


async def demo_offline_mode():
    """Demonstrate bot functionality without actual connection"""
    print("Running offline demo...")
    
    bot = ExtendedMeshCoreBot('example_config.ini')
    
    # Add custom handlers
    bot.add_custom_handler(weather_handler)
    bot.add_custom_handler(stats_handler)
    bot.add_custom_handler(echo_handler)
    
    # Simulate some messages
    from datetime import datetime
    
    test_messages = [
        MeshCoreMessage(
            message_type=MessageType.TEXT,
            sender_id="node1",
            channel="general",
            content="Hello everyone!",
            hops=1,
            path="AB",
            timestamp=datetime.now()
        ),
        MeshCoreMessage(
            message_type=MessageType.TEXT,
            sender_id="node2",
            channel="general",
            content="What's the weather like?",
            hops=2,
            path="CD",
            timestamp=datetime.now()
        ),
        MeshCoreMessage(
            message_type=MessageType.TEXT,
            sender_id="node3",
            channel="test",
            content="test message",
            hops=1,
            path="EF",
            timestamp=datetime.now()
        ),
        MeshCoreMessage(
            message_type=MessageType.TEXT,
            sender_id="node4",
            channel="general",
            content="echo Hello world!",
            hops=3,
            path="GH",
            timestamp=datetime.now()
        ),
        MeshCoreMessage(
            message_type=MessageType.TEXT,
            sender_id="node5",
            channel="general",
            content="Show me the stats",
            hops=1,
            path="IJ",
            timestamp=datetime.now()
        )
    ]
    
    print("Processing test messages...")
    for message in test_messages:
        print(f"\n--- Processing message from {message.sender_id} ---")
        print(f"Channel: {message.channel}")
        print(f"Content: {message.content}")
        print(f"Hops: {message.hops}, Path: {message.path}")
        
        # Check if message should be processed
        if bot.should_process_message(message):
            print("✓ Message will be processed")
            
            # Check for keywords
            keyword_matches = bot.check_keywords(message)
            if keyword_matches:
                print("✓ Keywords matched:")
                for keyword, response in keyword_matches:
                    print(f"  '{keyword}' -> '{response}'")
            else:
                print("✗ No keywords matched")
            
            # Run custom handlers
            for handler in bot.custom_handlers:
                try:
                    await handler(message)
                except Exception as e:
                    print(f"Handler error: {e}")
        else:
            print("✗ Message will not be processed")
    
    print(f"\nDemo complete. Processed {len(test_messages)} messages.")


def show_configuration_examples():
    """Show examples of different configuration options"""
    print("=== Configuration Examples ===\n")
    
    print("1. Basic Bot Configuration:")
    print("""
[Bot]
bot_name = MyMeshBot
enabled = true
passive_mode = false
rate_limit_seconds = 5
""")
    
    print("2. Keyword Response Examples:")
    print("""
[Keywords]
hello = "Hello {sender}! Welcome to the network."
weather = "Weather for {sender}: {content}"
help = "Available commands: hello, weather, help, ping"
ping = "Pong! Response time: {timestamp}"
info = "Message info: {sender} -> {channel} via {path} ({hops} hops)"
""")
    
    print("3. Scheduled Messages:")
    print("""
[Scheduled_Messages]
08:00 = general:Good morning! Network status check.
12:00 = general:Midday reminder - stay connected!
18:00 = general:Evening update - network running smoothly.
22:00 = general:Good night! Network will continue monitoring.
""")
    
    print("4. Channel Management:")
    print("""
[Channels]
monitor_channels = general,emergency,weather,announcements
respond_to_dms = true
""")
    
    print("5. User Management:")
    print("""
[Banned_Users]
banned_users = spam_user,malicious_node,test_user
""")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "demo":
            asyncio.run(demo_offline_mode())
        elif command == "config":
            show_configuration_examples()
        elif command == "create-config":
            create_example_config()
        elif command == "run":
            asyncio.run(run_example_bot())
        else:
            print("Unknown command. Available commands:")
            print("  demo         - Run offline demo")
            print("  config       - Show configuration examples")
            print("  create-config - Create example config file")
            print("  run          - Run the bot (requires connection)")
    else:
        print("MeshCore Bot Example Usage")
        print("=========================")
        print("Available commands:")
        print("  python example_usage.py demo         - Run offline demo")
        print("  python example_usage.py config       - Show configuration examples")
        print("  python example_usage.py create-config - Create example config file")
        print("  python example_usage.py run          - Run the bot (requires connection)")
        print("\nRun 'python example_usage.py demo' to see the bot in action!")
