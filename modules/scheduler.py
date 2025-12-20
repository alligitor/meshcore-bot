#!/usr/bin/env python3
"""
Message scheduler functionality for the MeshCore Bot
Handles scheduled messages and timing
"""

import time
import threading
import schedule
import datetime
import pytz
from typing import Dict, Tuple


class MessageScheduler:
    """Manages scheduled messages and timing"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.scheduled_messages = {}
        self.scheduler_thread = None
    
    def get_current_time(self):
        """Get current time in configured timezone"""
        timezone_str = self.bot.config.get('Bot', 'timezone', fallback='')
        
        if timezone_str:
            try:
                tz = pytz.timezone(timezone_str)
                return datetime.datetime.now(tz)
            except pytz.exceptions.UnknownTimeZoneError:
                self.logger.warning(f"Invalid timezone '{timezone_str}', using system timezone")
                return datetime.datetime.now()
        else:
            return datetime.datetime.now()
    
    def setup_scheduled_messages(self):
        """Setup scheduled messages from config"""
        if self.bot.config.has_section('Scheduled_Messages'):
            self.logger.info("Found Scheduled_Messages section")
            for time_str, message_info in self.bot.config.items('Scheduled_Messages'):
                self.logger.info(f"Processing scheduled message: '{time_str}' -> '{message_info}'")
                try:
                    # Validate time format first
                    if not self._is_valid_time_format(time_str):
                        self.logger.warning(f"Invalid time format '{time_str}' for scheduled message: {message_info}")
                        continue
                    
                    channel, message = message_info.split(':', 1)
                    # Convert HHMM to HH:MM for scheduler
                    hour = int(time_str[:2])
                    minute = int(time_str[2:])
                    schedule_time = f"{hour:02d}:{minute:02d}"
                    
                    schedule.every().day.at(schedule_time).do(
                        self.send_scheduled_message, channel.strip(), message.strip()
                    )
                    self.scheduled_messages[time_str] = (channel.strip(), message.strip())
                    self.logger.info(f"Scheduled message: {schedule_time} -> {channel}: {message}")
                except ValueError:
                    self.logger.warning(f"Invalid scheduled message format: {message_info}")
                except Exception as e:
                    self.logger.warning(f"Error setting up scheduled message '{time_str}': {e}")
    
    def _is_valid_time_format(self, time_str: str) -> bool:
        """Validate time format (HHMM)"""
        try:
            if len(time_str) != 4:
                return False
            hour = int(time_str[:2])
            minute = int(time_str[2:])
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except ValueError:
            return False
    
    def send_scheduled_message(self, channel: str, message: str):
        """Send a scheduled message (synchronous wrapper for schedule library)"""
        current_time = self.get_current_time()
        self.logger.info(f"📅 Sending scheduled message at {current_time.strftime('%H:%M:%S')} to {channel}: {message}")
        
        import asyncio
        
        # Create a new event loop for this thread if one doesn't exist
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run the async function in the event loop
        loop.run_until_complete(self._send_scheduled_message_async(channel, message))
    
    async def _send_scheduled_message_async(self, channel: str, message: str):
        """Send a scheduled message (async implementation)"""
        await self.bot.command_manager.send_channel_message(channel, message)
    
    def start(self):
        """Start the scheduler in a separate thread"""
        self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.scheduler_thread.start()
    
    def run_scheduler(self):
        """Run the scheduler in a separate thread"""
        self.logger.info("Scheduler thread started")
        last_log_time = 0
        
        while self.bot.connected:
            current_time = self.get_current_time()
            
            # Log current time every 5 minutes for debugging
            if time.time() - last_log_time > 300:  # 5 minutes
                #don't log this message as it clutters the output
                #self.logger.info(f"Scheduler running - Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                last_log_time = time.time()
            
            # Check for pending scheduled messages
            pending_jobs = schedule.get_jobs()
            if pending_jobs:
                self.logger.debug(f"Found {len(pending_jobs)} scheduled jobs")
            
            schedule.run_pending()
            time.sleep(1)
        
        self.logger.info("Scheduler thread stopped")
