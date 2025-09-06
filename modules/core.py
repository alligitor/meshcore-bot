#!/usr/bin/env python3
"""
Core MeshCore Bot functionality
Contains the main bot class and message processing logic
"""

import asyncio
import configparser
import logging
import colorlog
import time
import threading
import schedule
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# Import the official meshcore package
import meshcore
from meshcore import EventType

# Import command functions from meshcore-cli
from meshcore_cli.meshcore_cli import send_cmd, send_chan_msg

# Import our modules
from .rate_limiter import RateLimiter, BotTxRateLimiter
from .message_handler import MessageHandler
from .command_manager import CommandManager
from .channel_manager import ChannelManager
from .scheduler import MessageScheduler
from .repeater_manager import RepeaterManager


class MeshCoreBot:
    """MeshCore Bot using official meshcore package"""
    
    def __init__(self, config_file: str = "config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()
        
        # Setup logging
        self.setup_logging()
        
        # Connection
        self.meshcore = None
        self.connected = False
        
        # Initialize database manager first (needed by plugins)
        db_path = self.config.get('Bot', 'db_path', fallback='meshcore_bot.db')
        self.logger.info(f"Initializing database manager with database: {db_path}")
        try:
            from .db_manager import DBManager
            self.db_manager = DBManager(self, db_path)
            self.logger.info("Database manager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize database manager: {e}")
            raise
        
        # Initialize modules
        self.rate_limiter = RateLimiter(
            self.config.getint('Bot', 'rate_limit_seconds', fallback=10)
        )
        self.bot_tx_rate_limiter = BotTxRateLimiter(
            self.config.getfloat('Bot', 'bot_tx_rate_limit_seconds', fallback=1.0)
        )
        self.message_handler = MessageHandler(self)
        self.command_manager = CommandManager(self)
        self.channel_manager = ChannelManager(self)
        self.scheduler = MessageScheduler(self)
        
        # Initialize repeater manager
        self.logger.info("Initializing repeater manager")
        try:
            self.repeater_manager = RepeaterManager(self)
            self.logger.info("Repeater manager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize repeater manager: {e}")
            raise
        
        # Initialize solar conditions configuration
        from .solar_conditions import set_config
        set_config(self.config)
        
        # Advert tracking
        self.last_advert_time = None
        
        self.logger.info(f"MeshCore Bot initialized: {self.config.get('Bot', 'bot_name')}")
    
    def load_config(self):
        """Load configuration from file"""
        if not Path(self.config_file).exists():
            self.create_default_config()
        
        self.config.read(self.config_file)
    
    def create_default_config(self):
        """Create default configuration file"""
        default_config = """[Connection]
connection_type = ble
ble_device_name = MeshCore
serial_port = /dev/ttyUSB0
timeout = 30

[Bot]
bot_name = MeshCoreBot
node_id = 
enabled = true
passive_mode = false
rate_limit_seconds = 10
# Send startup announcement when bot finishes initializing
# Send startup advert when bot finishes initializing
# Options: false (disabled), zero-hop, flood
startup_advert = false
# Path to repeater contacts database
repeater_db_path = repeater_contacts.db

[Keywords]
test = "Test message received! Hops: {hops}, Path: {path}, From: {sender}"
ping = "Pong! Response time: {timestamp}"
help = "Available commands: test, ping, help"

[Custom_Syntax]
# Custom syntax patterns for special message formats
# Format: pattern = "response_format"
# Available fields: {sender}, {phrase}, {connection_info}, {snr}, {timestamp}, {path}
t_phrase = "ack {sender} {phrase} | {connection_info}"
@_phrase = "ack {sender} {phrase} | {connection_info}"

[Channels]
monitor_channels = Testing
respond_to_dms = true
channel_public_key = 1321f3257ae4f7125204096e15b34c99

[Banned_Users]
banned_users = 

[Scheduled_Messages]
0800 = Testing:Good morning! Testing channel is active.
1200 = Testing:Midday test - channel is working properly.
1800 = Testing:Evening test - channel status: Good

[Logging]
log_level = INFO
log_file = meshcore_bot.log
colored_output = true

[External_Data]
weather_api_key = 
weather_update_interval = 3600
tide_api_key = 
tide_update_interval = 1800
"""
        with open(self.config_file, 'w') as f:
            f.write(default_config)
        # Note: Using print here since logger may not be initialized yet
        print(f"Created default config file: {self.config_file}")
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.config.get('Logging', 'log_level', fallback='INFO'))
        
        # Create formatter
        if self.config.getboolean('Logging', 'colored_output', fallback=True):
            formatter = colorlog.ColoredFormatter(
                '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        # Setup logger
        self.logger = logging.getLogger('MeshCoreBot')
        self.logger.setLevel(log_level)
        
        # Clear any existing handlers to prevent duplicates
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        log_file = self.config.get('Logging', 'log_file', fallback='meshcore_bot.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Prevent propagation to root logger to avoid duplicate output
        self.logger.propagate = False
        
        # Configure meshcore library logging (separate from bot logging)
        meshcore_log_level = getattr(logging, self.config.get('Logging', 'meshcore_log_level', fallback='INFO'))
        
        # Configure all possible meshcore-related loggers
        meshcore_loggers = [
            'meshcore',
            'meshcore_cli', 
            'meshcore.meshcore',
            'meshcore_cli.meshcore_cli',
            'meshcore_cli.commands',
            'meshcore_cli.connection'
        ]
        
        for logger_name in meshcore_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(meshcore_log_level)
            # Remove any existing handlers to prevent duplicate output
            logger.handlers.clear()
            # Add our formatter
            if not logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(formatter)
                logger.addHandler(handler)
        
        # Configure root logger to prevent other libraries from using DEBUG
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Log the configuration for debugging
        self.logger.info(f"Logging configured - Bot: {logging.getLevelName(log_level)}, MeshCore: {logging.getLevelName(meshcore_log_level)}")
    
    async def connect(self) -> bool:
        """Connect to MeshCore node using official package"""
        try:
            self.logger.info("Connecting to MeshCore node...")
            
            # Get connection type from config
            connection_type = self.config.get('Connection', 'connection_type', fallback='ble').lower()
            self.logger.info(f"Using connection type: {connection_type}")
            
            if connection_type == 'serial':
                # Create serial connection
                serial_port = self.config.get('Connection', 'serial_port', fallback='/dev/ttyUSB0')
                self.logger.info(f"Connecting via serial port: {serial_port}")
                self.meshcore = await meshcore.MeshCore.create_serial(serial_port, debug=False)
            else:
                # Create BLE connection (default)
                ble_device_name = self.config.get('Connection', 'ble_device_name', fallback=None)
                self.logger.info(f"Connecting via BLE" + (f" to device: {ble_device_name}" if ble_device_name else ""))
                self.meshcore = await meshcore.MeshCore.create_ble(device_name=ble_device_name, debug=False)
            
            if self.meshcore.is_connected:
                self.connected = True
                self.logger.info(f"Connected to: {self.meshcore.self_info}")
                
                # Wait for contacts to load
                await self.wait_for_contacts()
                
                # Fetch channels
                await self.channel_manager.fetch_channels()
                
                # Setup message event handlers
                await self.setup_message_handlers()
                
                return True
            else:
                self.logger.error("Failed to connect to MeshCore node")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False
    
    async def wait_for_contacts(self):
        """Wait for contacts to be loaded"""
        self.logger.info("Waiting for contacts to load...")
        
        # Try to manually load contacts first
        try:
            from meshcore_cli.meshcore_cli import next_cmd
            self.logger.info("Manually requesting contacts from device...")
            result = await next_cmd(self.meshcore, ["contacts"])
            self.logger.info(f"Contacts command result: {len(result) if result else 0} contacts")
        except Exception as e:
            self.logger.warning(f"Error manually loading contacts: {e}")
        
        # Check if contacts are loaded (even if empty list)
        if hasattr(self.meshcore, 'contacts'):
            self.logger.info(f"Contacts loaded: {len(self.meshcore.contacts)} contacts")
            return
        
        # Wait up to 30 seconds for contacts to load
        max_wait = 30
        wait_time = 0
        while wait_time < max_wait:
            if hasattr(self.meshcore, 'contacts'):
                self.logger.info(f"Contacts loaded: {len(self.meshcore.contacts)} contacts")
                return
            
            await asyncio.sleep(5)
            wait_time += 5
            self.logger.info(f"Still waiting for contacts... ({wait_time}s)")
        
        self.logger.warning(f"Contacts not loaded after {max_wait} seconds, proceeding anyway")
    
    async def setup_message_handlers(self):
        """Setup event handlers for messages"""
        # Handle contact messages (DMs)
        async def on_contact_message(event, metadata=None):
            await self.message_handler.handle_contact_message(event, metadata)
        
        # Handle channel messages
        async def on_channel_message(event, metadata=None):
            await self.message_handler.handle_channel_message(event, metadata)
        
        # Handle RF log data for SNR information
        async def on_rf_data(event, metadata=None):
            await self.message_handler.handle_rf_log_data(event, metadata)
        
        # Handle raw data events (full packet data)
        async def on_raw_data(event, metadata=None):
            await self.message_handler.handle_raw_data(event, metadata)
        
        # Handle new contact events
        async def on_new_contact(event, metadata=None):
            await self.message_handler.handle_new_contact(event, metadata)
        
        # Subscribe to events
        self.meshcore.subscribe(EventType.CONTACT_MSG_RECV, on_contact_message)
        self.meshcore.subscribe(EventType.CHANNEL_MSG_RECV, on_channel_message)
        self.meshcore.subscribe(EventType.RX_LOG_DATA, on_rf_data)
        
        # Subscribe to RAW_DATA events for full packet data
        self.meshcore.subscribe(EventType.RAW_DATA, on_raw_data)
        
        # Subscribe to NEW_CONTACT events for automatic contact management
        self.meshcore.subscribe(EventType.NEW_CONTACT, on_new_contact)
        
        # Note: Debug mode commands are not available in current meshcore-cli version
        # The meshcore library handles debug output automatically when needed
        
        # Start auto message fetching
        await self.meshcore.start_auto_message_fetching()
        
        self.logger.info("Message handlers setup complete")
    
    async def start(self):
        """Start the bot"""
        self.logger.info("Starting MeshCore Bot...")
        
        # Connect to MeshCore node
        if not await self.connect():
            self.logger.error("Failed to connect to MeshCore node")
            return
        
        # Setup scheduled messages
        self.scheduler.setup_scheduled_messages()
        
        # Start scheduler thread
        self.scheduler.start()
        
        # Send startup advert if enabled
        await self.send_startup_advert()
        
        # Keep running
        self.logger.info("Bot is running. Press Ctrl+C to stop.")
        try:
            while self.connected:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the bot"""
        self.logger.info("Stopping MeshCore Bot...")
        self.connected = False
        
        if self.meshcore:
            await self.meshcore.disconnect()
        
        self.logger.info("Bot stopped")
    
    async def send_startup_advert(self):
        """Send a startup advert if enabled in config"""
        try:
            # Check if startup advert is enabled
            startup_advert = self.config.get('Bot', 'startup_advert', fallback='false').lower()
            if startup_advert == 'false':
                self.logger.debug("Startup advert disabled")
                return
            
            self.logger.info(f"Sending startup advert: {startup_advert}")
            
            # Add a small delay to ensure connection is fully established
            await asyncio.sleep(2)
            
            # Send the appropriate type of advert using meshcore.commands
            if startup_advert == 'zero-hop':
                self.logger.debug("Sending zero-hop advert")
                await self.meshcore.commands.send_advert(flood=False)
            elif startup_advert == 'flood':
                self.logger.debug("Sending flood advert")
                await self.meshcore.commands.send_advert(flood=True)
            else:
                self.logger.warning(f"Unknown startup_advert option: {startup_advert}")
                return
            
            # Update last advert time
            import time
            self.last_advert_time = time.time()
            
            self.logger.info(f"Startup {startup_advert} advert sent successfully")
                
        except Exception as e:
            self.logger.error(f"Error sending startup advert: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
