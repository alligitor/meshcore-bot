#!/usr/bin/env python3
"""
Repeater Contact Management System
Manages a database of repeater contacts and provides purging functionality
"""

import sqlite3
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class RepeaterManager:
    """Manages repeater contacts database and purging operations"""
    
    def __init__(self, bot, db_path: str = "repeater_contacts.db"):
        self.bot = bot
        self.logger = bot.logger
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create repeater_contacts table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS repeater_contacts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        public_key TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        device_type TEXT NOT NULL,  -- 'Repeater' or 'RoomServer'
                        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        contact_data TEXT,  -- JSON string of full contact data
                        is_active BOOLEAN DEFAULT 1,
                        purge_count INTEGER DEFAULT 0
                    )
                ''')
                
                # Create purging_log table for audit trail
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS purging_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        action TEXT NOT NULL,  -- 'purged', 'restored', 'added'
                        public_key TEXT NOT NULL,
                        name TEXT NOT NULL,
                        reason TEXT
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_public_key ON repeater_contacts(public_key)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_device_type ON repeater_contacts(device_type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_seen ON repeater_contacts(last_seen)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_is_active ON repeater_contacts(is_active)')
                
                conn.commit()
                self.logger.info("Repeater contacts database initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize repeater database: {e}")
            raise
    
    def _is_repeater_device(self, contact_data: Dict) -> bool:
        """Check if a contact is a repeater or room server using available contact data"""
        try:
            # Primary detection: Check device type field
            # Based on the actual contact data structure:
            # type: 2 = repeater, type: 3 = room server
            device_type = contact_data.get('type')
            if device_type in [2, 3]:
                return True
            
            # Secondary detection: Check for role fields in contact data
            role_fields = ['role', 'device_role', 'mode', 'device_type']
            for field in role_fields:
                value = contact_data.get(field, '')
                if value and isinstance(value, str):
                    value_lower = value.lower()
                    if any(role in value_lower for role in ['repeater', 'roomserver', 'room_server']):
                        return True
            
            # Tertiary detection: Check advertisement flags
            # Some repeaters have specific flags that indicate their function
            flags = contact_data.get('flags', contact_data.get('advert_flags', ''))
            if flags:
                if isinstance(flags, (int, str)):
                    flags_str = str(flags).lower()
                    if any(role in flags_str for role in ['repeater', 'roomserver', 'room_server']):
                        return True
            
            # Quaternary detection: Check name patterns with validation
            name = contact_data.get('adv_name', contact_data.get('name', '')).lower()
            if name:
                # Strong repeater indicators
                strong_indicators = ['repeater', 'roompeater', 'room server', 'roomserver', 'relay', 'gateway']
                if any(indicator in name for indicator in strong_indicators):
                    return True
                
                # Room server indicators
                room_indicators = ['room', 'rs ', 'rs-', 'rs_']
                if any(indicator in name for indicator in room_indicators):
                    # Additional validation to avoid false positives
                    user_indicators = ['user', 'person', 'mobile', 'phone', 'device', 'pager']
                    if not any(user_indicator in name for user_indicator in user_indicators):
                        return True
            
            # Quinary detection: Check path characteristics
            # Some repeaters have specific path patterns
            out_path_len = contact_data.get('out_path_len', -1)
            if out_path_len == 0:  # Direct connection might indicate repeater
                # Additional validation with name check
                if name and any(indicator in name for indicator in ['repeater', 'room', 'relay']):
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking if device is repeater: {e}")
            return False
    
    async def scan_and_catalog_repeaters(self) -> int:
        """Scan current contacts and catalog any repeaters found"""
        # Wait for contacts to be loaded if they're not ready yet
        if not hasattr(self.bot.meshcore, 'contacts') or not self.bot.meshcore.contacts:
            self.logger.info("Contacts not loaded yet, waiting...")
            # Wait up to 10 seconds for contacts to load
            for i in range(20):  # 20 * 0.5 = 10 seconds
                await asyncio.sleep(0.5)
                if hasattr(self.bot.meshcore, 'contacts') and self.bot.meshcore.contacts:
                    break
            else:
                self.logger.warning("No contacts available to scan for repeaters after waiting")
                return 0
        
        contacts = self.bot.meshcore.contacts
        self.logger.info(f"Scanning {len(contacts)} contacts for repeaters...")
        
        cataloged_count = 0
        processed_count = 0
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for contact_key, contact_data in self.bot.meshcore.contacts.items():
                    processed_count += 1
                    
                    # Log progress every 20 contacts
                    if processed_count % 20 == 0:
                        self.logger.info(f"Scan progress: {processed_count}/{len(contacts)} contacts processed, {cataloged_count} repeaters found")
                    
                    if self._is_repeater_device(contact_data):
                        public_key = contact_data.get('public_key', contact_key)
                        name = contact_data.get('adv_name', contact_data.get('name', 'Unknown'))
                        
                        # Determine device type based on contact data
                        contact_type = contact_data.get('type')
                        if contact_type == 3:
                            device_type = 'RoomServer'
                        elif contact_type == 2:
                            device_type = 'Repeater'
                        else:
                            # Fallback to name-based detection
                            device_type = 'Repeater'
                            if 'room' in name.lower() or 'server' in name.lower():
                                device_type = 'RoomServer'
                        
                        # Check if already exists
                        cursor.execute(
                            'SELECT id, last_seen FROM repeater_contacts WHERE public_key = ?',
                            (public_key,)
                        )
                        existing = cursor.fetchone()
                        
                        if existing:
                            # Update last_seen timestamp
                            cursor.execute(
                                'UPDATE repeater_contacts SET last_seen = CURRENT_TIMESTAMP, is_active = 1 WHERE public_key = ?',
                                (public_key,)
                            )
                        else:
                            # Insert new repeater
                            cursor.execute('''
                                INSERT INTO repeater_contacts 
                                (public_key, name, device_type, contact_data)
                                VALUES (?, ?, ?, ?)
                            ''', (
                                public_key,
                                name,
                                device_type,
                                json.dumps(contact_data)
                            ))
                            
                            # Log the addition
                            cursor.execute('''
                                INSERT INTO purging_log (action, public_key, name, reason)
                                VALUES ('added', ?, ?, 'Auto-detected during contact scan')
                            ''', (public_key, name))
                            
                            cataloged_count += 1
                            self.logger.info(f"Cataloged new repeater: {name} ({device_type})")
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error scanning contacts for repeaters: {e}")
        
        if cataloged_count > 0:
            self.logger.info(f"Cataloged {cataloged_count} new repeaters")
        
        self.logger.info(f"Scan completed: {cataloged_count} repeaters cataloged from {len(contacts)} contacts")
        self.logger.info(f"Scan summary: {processed_count} contacts processed, {cataloged_count} repeaters found")
        return cataloged_count
    
    async def get_repeater_contacts(self, active_only: bool = True) -> List[Dict]:
        """Get list of repeater contacts from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = 'SELECT * FROM repeater_contacts'
                if active_only:
                    query += ' WHERE is_active = 1'
                query += ' ORDER BY last_seen DESC'
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            self.logger.error(f"Error retrieving repeater contacts: {e}")
            return []
    
    async def purge_repeater_from_contacts(self, public_key: str, reason: str = "Manual purge") -> bool:
        """Remove a specific repeater from the device's contact list"""
        self.logger.info(f"Starting purge process for public_key: {public_key}")
        self.logger.debug(f"Purge reason: {reason}")
        
        try:
            # Find the contact in meshcore
            contact_to_remove = None
            contact_name = None
            
            self.logger.debug(f"Searching through {len(self.bot.meshcore.contacts)} contacts...")
            for contact_key, contact_data in self.bot.meshcore.contacts.items():
                if contact_data.get('public_key', contact_key) == public_key:
                    contact_to_remove = contact_data
                    contact_name = contact_data.get('adv_name', contact_data.get('name', 'Unknown'))
                    self.logger.debug(f"Found contact: {contact_name} (key: {contact_key})")
                    break
            
            if not contact_to_remove:
                self.logger.warning(f"Repeater with public key {public_key} not found in current contacts")
                return False
            
            # Actually remove the contact from the device using meshcore-cli
            # Add timeout and error handling for LoRa communication
            try:
                from meshcore_cli.meshcore_cli import next_cmd
                import asyncio
                
                self.logger.info(f"Starting removal of contact '{contact_name}' from device...")
                self.logger.debug(f"Contact details: public_key={public_key}, name='{contact_name}'")
                
                # Use asyncio.wait_for to add timeout for LoRa communication
                try:
                    self.logger.info(f"Sending remove_contact command for '{contact_name}' (timeout: 30s)...")
                    start_time = asyncio.get_event_loop().time()
                    
                    result = await asyncio.wait_for(
                        next_cmd(self.bot.meshcore, ["remove_contact", contact_name]),
                        timeout=30.0  # 30 second timeout for LoRa communication
                    )
                    
                    end_time = asyncio.get_event_loop().time()
                    duration = end_time - start_time
                    self.logger.info(f"Remove command completed in {duration:.2f} seconds")
                    
                    # Check if removal was successful
                    if result is not None:
                        self.logger.info(f"Successfully removed contact '{contact_name}' from device")
                        self.logger.debug(f"Command result: {result}")
                    else:
                        self.logger.warning(f"Contact removal command returned no result for '{contact_name}'")
                        
                except asyncio.TimeoutError:
                    end_time = asyncio.get_event_loop().time()
                    duration = end_time - start_time
                    self.logger.warning(f"Timeout removing contact '{contact_name}' after {duration:.2f} seconds (LoRa communication)")
                    # Continue with database operations even if device removal timed out
                except Exception as cmd_error:
                    end_time = asyncio.get_event_loop().time()
                    duration = end_time - start_time
                    self.logger.error(f"Command error removing contact '{contact_name}' after {duration:.2f} seconds: {cmd_error}")
                    self.logger.debug(f"Error type: {type(cmd_error).__name__}")
                    # Continue with database operations even if device removal failed
                
            except Exception as e:
                self.logger.error(f"Failed to remove contact '{contact_name}' from device: {e}")
                self.logger.debug(f"Error type: {type(e).__name__}")
                # Continue with database operations even if device removal failed
            
            # Mark as inactive in database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE repeater_contacts SET is_active = 0, purge_count = purge_count + 1 WHERE public_key = ?',
                    (public_key,)
                )
                
                # Log the purge action
                cursor.execute('''
                    INSERT INTO purging_log (action, public_key, name, reason)
                    VALUES ('purged', ?, ?, ?)
                ''', (public_key, contact_name, reason))
                
                conn.commit()
            
            self.logger.info(f"Successfully purged repeater {contact_name}: {reason}")
            self.logger.debug(f"Purge process completed successfully for {contact_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error purging repeater {public_key}: {e}")
            self.logger.debug(f"Error type: {type(e).__name__}")
            return False
    
    async def purge_old_repeaters(self, days_old: int = 30, reason: str = "Automatic purge - old contacts") -> int:
        """Purge repeaters that haven't been seen in specified days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Find old repeaters
                cursor.execute('''
                    SELECT public_key, name FROM repeater_contacts 
                    WHERE is_active = 1 AND last_seen < ?
                ''', (cutoff_date.isoformat(),))
                
                old_repeaters = cursor.fetchall()
                purged_count = 0
                
                # Process repeaters with delays to avoid overwhelming LoRa network
                self.logger.info(f"Starting batch purge of {len(old_repeaters)} old repeaters...")
                start_time = asyncio.get_event_loop().time()
                
                for i, (public_key, name) in enumerate(old_repeaters):
                    self.logger.info(f"Purging repeater {i+1}/{len(old_repeaters)}: {name}")
                    self.logger.debug(f"Processing public_key: {public_key}")
                    
                    try:
                        if await self.purge_repeater_from_contacts(public_key, f"{reason} (last seen: {cutoff_date.date()})"):
                            purged_count += 1
                            self.logger.info(f"Successfully purged {i+1}/{len(old_repeaters)}: {name}")
                        else:
                            self.logger.warning(f"Failed to purge {i+1}/{len(old_repeaters)}: {name}")
                    except Exception as e:
                        self.logger.error(f"Exception purging {i+1}/{len(old_repeaters)}: {name} - {e}")
                    
                    # Add delay between removals to avoid overwhelming LoRa network
                    if i < len(old_repeaters) - 1:  # Don't delay after the last one
                        self.logger.debug(f"Waiting 2 seconds before next removal...")
                        await asyncio.sleep(2)  # 2 second delay between removals
                
                end_time = asyncio.get_event_loop().time()
                total_duration = end_time - start_time
                self.logger.info(f"Batch purge completed in {total_duration:.2f} seconds")
                
                self.logger.info(f"Purged {purged_count} old repeaters (older than {days_old} days)")
                return purged_count
                
        except Exception as e:
            self.logger.error(f"Error purging old repeaters: {e}")
            return 0
    
    async def restore_repeater(self, public_key: str, reason: str = "Manual restore") -> bool:
        """Restore a previously purged repeater"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get repeater info before updating
                cursor.execute('''
                    SELECT name, contact_data FROM repeater_contacts WHERE public_key = ?
                ''', (public_key,))
                result = cursor.fetchone()
                
                if not result:
                    self.logger.warning(f"No repeater found with public key {public_key}")
                    return False
                
                name, contact_data_json = result
                
                # Mark as active again
                cursor.execute(
                    'UPDATE repeater_contacts SET is_active = 1 WHERE public_key = ?',
                    (public_key,)
                )
                
                # Log the restore action
                cursor.execute('''
                    INSERT INTO purging_log (action, public_key, name, reason)
                    VALUES ('restored', ?, ?, ?)
                ''', (public_key, name, reason))
                
                conn.commit()
                
                # Note: Restoring a contact to the device would require re-adding it
                # This is complex as it requires the contact's URI or public key
                # For now, we just mark it as active in our database
                # The contact would need to be re-discovered through normal mesh operations
                
                self.logger.info(f"Restored repeater {name} ({public_key}) - contact will need to be re-discovered")
                return True
                    
        except Exception as e:
            self.logger.error(f"Error restoring repeater {public_key}: {e}")
            return False
    
    async def get_purging_stats(self) -> Dict:
        """Get statistics about repeater purging operations"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get total counts
                cursor.execute('SELECT COUNT(*) FROM repeater_contacts')
                total_repeaters = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM repeater_contacts WHERE is_active = 1')
                active_repeaters = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM repeater_contacts WHERE is_active = 0')
                purged_repeaters = cursor.fetchone()[0]
                
                # Get recent purging activity
                cursor.execute('''
                    SELECT action, COUNT(*) FROM purging_log 
                    WHERE timestamp > datetime('now', '-7 days')
                    GROUP BY action
                ''')
                recent_activity = dict(cursor.fetchall())
                
                return {
                    'total_repeaters': total_repeaters,
                    'active_repeaters': active_repeaters,
                    'purged_repeaters': purged_repeaters,
                    'recent_activity_7_days': recent_activity
                }
                
        except Exception as e:
            self.logger.error(f"Error getting purging stats: {e}")
            return {}
    
    async def cleanup_database(self, days_to_keep_logs: int = 90):
        """Clean up old purging log entries"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep_logs)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'DELETE FROM purging_log WHERE timestamp < ?',
                    (cutoff_date.isoformat(),)
                )
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    self.logger.info(f"Cleaned up {deleted_count} old purging log entries")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up database: {e}")
