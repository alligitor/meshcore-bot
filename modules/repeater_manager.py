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
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.db_path = bot.db_manager.db_path
        
        # Use the shared database manager
        self.db_manager = bot.db_manager
        
        # Initialize repeater-specific tables
        self._init_repeater_tables()
    
    def _init_repeater_tables(self):
        """Initialize repeater-specific database tables"""
        try:
            # Create repeater_contacts table
            self.db_manager.create_table('repeater_contacts', '''
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                device_type TEXT NOT NULL,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                contact_data TEXT,
                is_active BOOLEAN DEFAULT 1,
                purge_count INTEGER DEFAULT 0
            ''')
            
            # Create purging_log table for audit trail
            self.db_manager.create_table('purging_log', '''
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action TEXT NOT NULL,
                public_key TEXT NOT NULL,
                name TEXT NOT NULL,
                reason TEXT
            ''')
            
            # Create indexes for better performance
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
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
            for contact_key, contact_data in self.bot.meshcore.contacts.items():
                processed_count += 1
                
                # Log progress every 20 contacts
                if processed_count % 20 == 0:
                    self.logger.info(f"Scan progress: {processed_count}/{len(contacts)} contacts processed, {cataloged_count} repeaters found")
                
                # Debug logging for first few contacts to understand structure
                if processed_count <= 5:
                    self.logger.debug(f"Contact {processed_count}: {contact_data.get('name', 'Unknown')} (type: {contact_data.get('type')}, keys: {list(contact_data.keys())})")
                
                if self._is_repeater_device(contact_data):
                    public_key = contact_data.get('public_key', contact_key)
                    name = contact_data.get('adv_name', contact_data.get('name', 'Unknown'))
                    self.logger.info(f"Found repeater: {name} (type: {contact_data.get('type')}, key: {public_key[:16]}...)")
                    
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
                    existing = self.db_manager.execute_query(
                        'SELECT id, last_seen FROM repeater_contacts WHERE public_key = ?',
                        (public_key,)
                    )
                    
                    if existing:
                        # Update last_seen timestamp
                        self.db_manager.execute_update(
                            'UPDATE repeater_contacts SET last_seen = CURRENT_TIMESTAMP, is_active = 1 WHERE public_key = ?',
                            (public_key,)
                        )
                    else:
                        # Insert new repeater
                        self.db_manager.execute_update('''
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
                        self.db_manager.execute_update('''
                            INSERT INTO purging_log (action, public_key, name, reason)
                            VALUES ('added', ?, ?, 'Auto-detected during contact scan')
                        ''', (public_key, name))
                        
                        cataloged_count += 1
                        self.logger.info(f"Cataloged new repeater: {name} ({device_type})")
                
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
            query = 'SELECT * FROM repeater_contacts'
            if active_only:
                query += ' WHERE is_active = 1'
            query += ' ORDER BY last_seen DESC'
            
            return self.db_manager.execute_query(query)
                
        except Exception as e:
            self.logger.error(f"Error retrieving repeater contacts: {e}")
            return []
    
    async def test_meshcore_cli_commands(self) -> Dict[str, bool]:
        """Test if meshcore-cli commands are working properly"""
        results = {}
        
        try:
            from meshcore_cli.meshcore_cli import next_cmd
            
            # Test a simple command that should always work
            try:
                result = await asyncio.wait_for(
                    next_cmd(self.bot.meshcore, ["help"]),
                    timeout=10.0
                )
                results['help'] = result is not None
                self.logger.info(f"meshcore-cli help command test: {'PASS' if results['help'] else 'FAIL'}")
            except Exception as e:
                results['help'] = False
                self.logger.warning(f"meshcore-cli help command test FAILED: {e}")
            
            # Test remove_contact command (we'll use a dummy key)
            try:
                result = await asyncio.wait_for(
                    next_cmd(self.bot.meshcore, ["remove_contact", "dummy_key"]),
                    timeout=10.0
                )
                # Even if it fails, if we get here without "Unknown command" error, the command exists
                results['remove_contact'] = True
                self.logger.info(f"meshcore-cli remove_contact command test: PASS")
            except Exception as e:
                if "Unknown command" in str(e):
                    results['remove_contact'] = False
                    self.logger.error(f"meshcore-cli remove_contact command test FAILED: {e}")
                else:
                    # Command exists but failed for other reasons (expected with dummy key)
                    results['remove_contact'] = True
                    self.logger.info(f"meshcore-cli remove_contact command test: PASS (command exists)")
            
        except Exception as e:
            self.logger.error(f"Error testing meshcore-cli commands: {e}")
            results['error'] = str(e)
        
        return results

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
            
            # Actually remove the contact from the device using meshcore-cli API
            # Add timeout and error handling for LoRa communication
            try:
                import asyncio
                
                self.logger.info(f"Starting removal of contact '{contact_name}' from device...")
                self.logger.debug(f"Contact details: public_key={public_key}, name='{contact_name}'")
                
                # Check if we have a valid public key
                if not public_key or public_key.strip() == '':
                    self.logger.error(f"Cannot remove contact '{contact_name}': no public key available")
                    return False
                
                # Use asyncio.wait_for to add timeout for LoRa communication
                try:
                    self.logger.info(f"Sending remove_contact command for '{contact_name}' (key: {public_key[:16]}...) (timeout: 30s)...")
                    start_time = asyncio.get_event_loop().time()
                    
                    # Use the meshcore-cli API for device commands
                    from meshcore_cli.meshcore_cli import next_cmd
                    result = await asyncio.wait_for(
                        next_cmd(self.bot.meshcore, ["remove_contact", public_key]),
                        timeout=30.0  # 30 second timeout for LoRa communication
                    )
                    
                    end_time = asyncio.get_event_loop().time()
                    duration = end_time - start_time
                    self.logger.info(f"Remove command completed in {duration:.2f} seconds")
                    
                    # Check if removal was successful
                    if result is not None:
                        self.logger.info(f"Successfully removed contact '{contact_name}' from device")
                        self.logger.debug(f"Command result: {result}")
                        
                        # Verify the contact was actually removed by checking if it still exists
                        await asyncio.sleep(1)  # Give device time to process
                        contact_still_exists = False
                        for check_key, check_data in self.bot.meshcore.contacts.items():
                            if check_data.get('public_key', check_key) == public_key:
                                contact_still_exists = True
                                break
                        
                        if contact_still_exists:
                            self.logger.warning(f"Contact '{contact_name}' still exists after removal command - removal may have failed")
                        else:
                            self.logger.info(f"Verified: Contact '{contact_name}' successfully removed from device")
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
            self.db_manager.execute_update(
                'UPDATE repeater_contacts SET is_active = 0, purge_count = purge_count + 1 WHERE public_key = ?',
                (public_key,)
            )
            
            # Log the purge action
            self.db_manager.execute_update('''
                INSERT INTO purging_log (action, public_key, name, reason)
                VALUES ('purged', ?, ?, ?)
            ''', (public_key, contact_name, reason))
            
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
            
            # Find old repeaters by checking their actual last_advert time from contact data
            # We need to cross-reference the database with the current contact data
            old_repeaters = []
            
            # Get all active repeaters from database
            all_repeaters = self.db_manager.execute_query('''
                SELECT public_key, name FROM repeater_contacts 
                WHERE is_active = 1
            ''')
            
            # Check each repeater's actual last_advert time
            for repeater in all_repeaters:
                public_key = repeater['public_key']
                name = repeater['name']
                
                # Find the contact in meshcore.contacts
                for contact_key, contact_data in self.bot.meshcore.contacts.items():
                    if contact_data.get('public_key', contact_key) == public_key:
                        # Check the actual last_advert time
                        last_advert = contact_data.get('last_advert')
                        if last_advert:
                            try:
                                # Parse the last_advert timestamp
                                if isinstance(last_advert, str):
                                    last_advert_dt = datetime.fromisoformat(last_advert.replace('Z', '+00:00'))
                                elif isinstance(last_advert, (int, float)):
                                    # Unix timestamp (seconds since epoch)
                                    last_advert_dt = datetime.fromtimestamp(last_advert)
                                else:
                                    # Assume it's already a datetime object
                                    last_advert_dt = last_advert
                                
                                # Check if it's older than cutoff
                                if last_advert_dt < cutoff_date:
                                    old_repeaters.append({
                                        'public_key': public_key,
                                        'name': name,
                                        'last_seen': last_advert
                                    })
                                    self.logger.debug(f"Found old repeater: {name} (last_advert: {last_advert} -> {last_advert_dt})")
                                else:
                                    self.logger.debug(f"Recent repeater: {name} (last_advert: {last_advert} -> {last_advert_dt})")
                            except Exception as e:
                                self.logger.debug(f"Error parsing last_advert for {name}: {e} (type: {type(last_advert)}, value: {last_advert})")
                        break
            
            # Debug logging
            self.logger.info(f"Purge criteria: cutoff_date = {cutoff_date.isoformat()}, days_old = {days_old}")
            self.logger.info(f"Found {len(old_repeaters)} repeaters older than {days_old} days")
            
            # Show some examples of what we found
            if old_repeaters:
                for i, repeater in enumerate(old_repeaters[:3]):  # Show first 3
                    self.logger.info(f"Old repeater {i+1}: {repeater['name']} (last_advert: {repeater['last_seen']})")
            else:
                # Show some recent repeaters to understand the timestamp format
                self.logger.info("No old repeaters found. Showing recent repeater activity:")
                recent_count = 0
                for contact_key, contact_data in self.bot.meshcore.contacts.items():
                    if self._is_repeater_device(contact_data):
                        last_advert = contact_data.get('last_advert', 'No last_advert')
                        name = contact_data.get('adv_name', contact_data.get('name', 'Unknown'))
                        if last_advert != 'No last_advert':
                            try:
                                if isinstance(last_advert, (int, float)):
                                    last_advert_dt = datetime.fromtimestamp(last_advert)
                                    self.logger.info(f"  {name}: {last_advert} (Unix timestamp) -> {last_advert_dt}")
                                else:
                                    self.logger.info(f"  {name}: {last_advert} (type: {type(last_advert)})")
                            except Exception as e:
                                self.logger.info(f"  {name}: {last_advert} (parse error: {e})")
                        else:
                            self.logger.info(f"  {name}: No last_advert")
                        recent_count += 1
                        if recent_count >= 3:
                            break
            
            purged_count = 0
            
            # Process repeaters with delays to avoid overwhelming LoRa network
            self.logger.info(f"Starting batch purge of {len(old_repeaters)} old repeaters...")
            start_time = asyncio.get_event_loop().time()
            
            for i, repeater in enumerate(old_repeaters):
                public_key = repeater['public_key']
                name = repeater['name']
                
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
            
            # After purging, toggle auto-add off and discover new contacts manually
            if purged_count > 0:
                await self._post_purge_contact_management()
            
            self.logger.info(f"Purged {purged_count} old repeaters (older than {days_old} days)")
            return purged_count
                
        except Exception as e:
            self.logger.error(f"Error purging old repeaters: {e}")
            return 0
    
    async def _post_purge_contact_management(self):
        """Post-purge contact management: enable manual contact addition and discover new contacts manually"""
        try:
            self.logger.info("Starting post-purge contact management...")
            
            # Step 1: Enable manual contact addition
            self.logger.info("Enabling manual contact addition on device...")
            try:
                from meshcore_cli.meshcore_cli import next_cmd
                result = await asyncio.wait_for(
                    next_cmd(self.bot.meshcore, ["set_manual_add_contacts", "true"]),
                    timeout=15.0
                )
                self.logger.info("Successfully enabled manual contact addition")
                self.logger.debug(f"Manual add contacts enable result: {result}")
            except asyncio.TimeoutError:
                self.logger.warning("Timeout enabling manual contact addition (LoRa communication)")
            except Exception as e:
                self.logger.error(f"Failed to enable manual contact addition: {e}")
            
            # Step 2: Discover new companion contacts manually
            self.logger.info("Starting manual companion contact discovery...")
            try:
                from meshcore_cli.meshcore_cli import next_cmd
                result = await asyncio.wait_for(
                    next_cmd(self.bot.meshcore, ["discover_companion_contacts"]),
                    timeout=30.0
                )
                self.logger.info("Successfully initiated companion contact discovery")
                self.logger.debug(f"Discovery result: {result}")
            except asyncio.TimeoutError:
                self.logger.warning("Timeout during companion contact discovery (LoRa communication)")
            except Exception as e:
                self.logger.error(f"Failed to discover companion contacts: {e}")
            
            # Step 3: Log the post-purge management action
            self.db_manager.execute_update(
                'INSERT INTO purging_log (action, details) VALUES (?, ?)',
                ('post_purge_management', 'Enabled manual contact addition and initiated companion contact discovery')
            )
            
            self.logger.info("Post-purge contact management completed")
            
        except Exception as e:
            self.logger.error(f"Error in post-purge contact management: {e}")
    
    async def get_contact_list_status(self) -> Dict:
        """Get current contact list status and limits"""
        try:
            # Get current contact count
            current_contacts = len(self.bot.meshcore.contacts) if hasattr(self.bot.meshcore, 'contacts') else 0
            
            # Get device info to determine contact limit
            device_info = self.bot.meshcore.device_info if hasattr(self.bot.meshcore, 'device_info') else {}
            
            # Typical MeshCore contact limits (these may vary by device)
            # Most devices have a limit around 200-500 contacts
            estimated_limit = device_info.get('contact_limit', 200)  # Default assumption
            
            # Calculate usage percentage
            usage_percentage = (current_contacts / estimated_limit) * 100 if estimated_limit > 0 else 0
            
            # Count repeaters from actual device contacts (more accurate than database)
            device_repeater_count = 0
            if hasattr(self.bot.meshcore, 'contacts'):
                for contact_key, contact_data in self.bot.meshcore.contacts.items():
                    if self._is_repeater_device(contact_data):
                        device_repeater_count += 1
            
            # Also get database repeater count for reference
            db_repeater_count = len(await self.get_repeater_contacts(active_only=True))
            
            # Use device count as primary, fall back to database count
            repeater_count = device_repeater_count if device_repeater_count > 0 else db_repeater_count
            
            # Calculate companion count (total contacts minus repeaters)
            companion_count = current_contacts - repeater_count
            
            # Get contacts without recent adverts (potential candidates for removal)
            stale_contacts = await self._get_stale_contacts()
            
            return {
                'current_contacts': current_contacts,
                'estimated_limit': estimated_limit,
                'usage_percentage': usage_percentage,
                'repeater_count': repeater_count,
                'companion_count': companion_count,
                'stale_contacts_count': len(stale_contacts),
                'available_slots': max(0, estimated_limit - current_contacts),
                'is_near_limit': usage_percentage > 80,  # Warning at 80%
                'is_at_limit': usage_percentage >= 95,   # Critical at 95%
                'stale_contacts': stale_contacts[:10]  # Top 10 stale contacts
            }
            
        except Exception as e:
            self.logger.error(f"Error getting contact list status: {e}")
            return {}
    
    async def _get_stale_contacts(self, days_without_advert: int = 7) -> List[Dict]:
        """Get contacts that haven't sent adverts in specified days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_without_advert)
            
            # Get contacts from device
            if not hasattr(self.bot.meshcore, 'contacts'):
                return []
            
            stale_contacts = []
            for contact_key, contact_data in self.bot.meshcore.contacts.items():
                # Skip repeaters (they're managed separately)
                if self._is_repeater_device(contact_data):
                    continue
                
                # Check last_seen or similar timestamp fields
                last_seen = contact_data.get('last_seen', contact_data.get('last_advert', contact_data.get('timestamp')))
                if last_seen:
                    try:
                        # Parse timestamp
                        if isinstance(last_seen, str):
                            last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                        elif isinstance(last_seen, (int, float)):
                            # Unix timestamp (seconds since epoch)
                            last_seen_dt = datetime.fromtimestamp(last_seen)
                        else:
                            # Assume it's already a datetime object
                            last_seen_dt = last_seen
                        
                        if last_seen_dt < cutoff_date:
                            stale_contacts.append({
                                'name': contact_data.get('name', contact_data.get('adv_name', 'Unknown')),
                                'public_key': contact_data.get('public_key', ''),
                                'last_seen': last_seen,
                                'days_stale': (datetime.now() - last_seen_dt).days
                            })
                    except Exception as e:
                        self.logger.debug(f"Error parsing timestamp for contact {contact_data.get('name', 'Unknown')}: {e}")
                        continue
            
            # Sort by days stale (oldest first)
            stale_contacts.sort(key=lambda x: x['days_stale'], reverse=True)
            return stale_contacts
            
        except Exception as e:
            self.logger.error(f"Error getting stale contacts: {e}")
            return []
    
    async def manage_contact_list(self, auto_cleanup: bool = True) -> Dict:
        """Manage contact list to prevent hitting limits"""
        try:
            status = await self.get_contact_list_status()
            
            if not status:
                return {'error': 'Failed to get contact list status'}
            
            actions_taken = []
            
            # If near limit, start cleanup
            if status['is_near_limit']:
                self.logger.warning(f"Contact list at {status['usage_percentage']:.1f}% capacity ({status['current_contacts']}/{status['estimated_limit']})")
                
                if auto_cleanup:
                    # Step 1: Remove stale contacts
                    stale_removed = await self._remove_stale_contacts(status['stale_contacts'])
                    if stale_removed > 0:
                        actions_taken.append(f"Removed {stale_removed} stale contacts")
                    
                    # Step 2: If still near limit, remove old repeaters
                    if status['is_near_limit'] and status['repeater_count'] > 0:
                        old_repeaters_removed = await self.purge_old_repeaters(days_old=14, reason="Contact list management - near limit")
                        if old_repeaters_removed > 0:
                            actions_taken.append(f"Removed {old_repeaters_removed} old repeaters")
                    
                    # Step 3: If still at critical limit, more aggressive cleanup
                    if status['is_at_limit']:
                        self.logger.warning("Contact list at critical capacity, performing aggressive cleanup")
                        aggressive_removed = await self._aggressive_contact_cleanup()
                        if aggressive_removed > 0:
                            actions_taken.append(f"Aggressive cleanup removed {aggressive_removed} contacts")
            
            # Log the management action
            if actions_taken:
                self.db_manager.execute_update(
                    'INSERT INTO purging_log (action, details) VALUES (?, ?)',
                    ('contact_management', f'Contact list management: {"; ".join(actions_taken)}')
                )
            
            return {
                'status': status,
                'actions_taken': actions_taken,
                'success': True
            }
            
        except Exception as e:
            self.logger.error(f"Error managing contact list: {e}")
            return {'error': str(e), 'success': False}
    
    async def _remove_stale_contacts(self, stale_contacts: List[Dict], max_remove: int = 10) -> int:
        """Remove stale contacts to free up space"""
        try:
            removed_count = 0
            
            for contact in stale_contacts[:max_remove]:
                try:
                    contact_name = contact['name']
                    public_key = contact['public_key']
                    
                    self.logger.info(f"Removing stale contact: {contact_name} (last seen {contact['days_stale']} days ago)")
                    
                    # Check if we have a valid public key
                    if not public_key or public_key.strip() == '':
                        self.logger.warning(f"Skipping stale contact '{contact_name}': no public key available")
                        continue
                    
                    # Remove from device
                    from meshcore_cli.meshcore_cli import next_cmd
                    result = await asyncio.wait_for(
                        next_cmd(self.bot.meshcore, ["remove_contact", public_key]),
                        timeout=15.0
                    )
                    
                    if result is not None:
                        removed_count += 1
                        self.logger.info(f"Successfully removed stale contact: {contact_name}")
                        
                        # Log the removal
                        self.db_manager.execute_update(
                            'INSERT INTO purging_log (action, details) VALUES (?, ?)',
                            ('stale_contact_removal', f'Removed stale contact: {contact_name} (last seen {contact["days_stale"]} days ago)')
                        )
                    else:
                        self.logger.warning(f"Failed to remove stale contact: {contact_name}")
                    
                    # Small delay between removals
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    self.logger.error(f"Error removing stale contact {contact.get('name', 'Unknown')}: {e}")
                    continue
            
            return removed_count
            
        except Exception as e:
            self.logger.error(f"Error removing stale contacts: {e}")
            return 0
    
    async def _aggressive_contact_cleanup(self) -> int:
        """Perform aggressive cleanup when at critical limit"""
        try:
            removed_count = 0
            
            # Remove very old repeaters (7+ days)
            old_repeaters = await self.purge_old_repeaters(days_old=7, reason="Aggressive cleanup - critical limit")
            removed_count += old_repeaters
            
            # Remove very stale contacts (14+ days)
            very_stale = await self._get_stale_contacts(days_without_advert=14)
            stale_removed = await self._remove_stale_contacts(very_stale, max_remove=20)
            removed_count += stale_removed
            
            return removed_count
            
        except Exception as e:
            self.logger.error(f"Error in aggressive contact cleanup: {e}")
            return 0
    
    async def add_discovered_contact(self, contact_name: str, public_key: str = None, reason: str = "Manual addition") -> bool:
        """Add a discovered contact to the contact list"""
        try:
            from meshcore_cli.meshcore_cli import next_cmd
            
            self.logger.info(f"Adding discovered contact: {contact_name}")
            
            # Use the add_contact command if available, or try to add via discovery
            try:
                result = await asyncio.wait_for(
                    next_cmd(self.bot.meshcore, ["add_contact", contact_name, public_key]),
                    timeout=15.0
                )
                
                if result is not None:
                    self.logger.info(f"Successfully added contact: {contact_name}")
                    
                    # Log the addition
                    self.db_manager.execute_update(
                        'INSERT INTO purging_log (action, details) VALUES (?, ?)',
                        ('contact_addition', f'Added discovered contact: {contact_name} - {reason}')
                    )
                    
                    return True
                else:
                    self.logger.warning(f"Failed to add contact: {contact_name}")
                    return False
                    
            except AttributeError:
                # add_contact command might not be available, try alternative approach
                self.logger.info("add_contact command not available, trying discovery approach")
                
                # Try to discover the contact
                result = await asyncio.wait_for(
                    next_cmd(self.bot.meshcore, ["discover_companion_contacts"]),
                    timeout=30.0
                )
                
                if result is not None:
                    self.logger.info("Contact discovery initiated")
                    return True
                else:
                    self.logger.warning("Contact discovery failed")
                    return False
            
        except asyncio.TimeoutError:
            self.logger.warning("Timeout adding discovered contact (LoRa communication)")
            return False
        except Exception as e:
            self.logger.error(f"Error adding discovered contact: {e}")
            return False
    
    async def toggle_auto_add(self, enabled: bool, reason: str = "Manual toggle") -> bool:
        """Toggle the manual contact addition setting on the device"""
        try:
            from meshcore_cli.meshcore_cli import next_cmd
            
            self.logger.info(f"{'Enabling' if enabled else 'Disabling'} manual contact addition on device...")
            
            result = await asyncio.wait_for(
                next_cmd(self.bot.meshcore, ["set_manual_add_contacts", "true" if enabled else "false"]),
                timeout=15.0
            )
            
            self.logger.info(f"Successfully {'enabled' if enabled else 'disabled'} manual contact addition")
            self.logger.debug(f"Manual contact addition toggle result: {result}")
            
            # Log the action
            self.db_manager.execute_update(
                'INSERT INTO purging_log (action, details) VALUES (?, ?)',
                ('manual_add_toggle', f'{"Enabled" if enabled else "Disabled"} manual contact addition - {reason}')
            )
            
            return True
            
        except asyncio.TimeoutError:
            self.logger.warning("Timeout toggling manual contact addition (LoRa communication)")
            return False
        except Exception as e:
            self.logger.error(f"Failed to toggle manual contact addition: {e}")
            return False
    
    async def discover_companion_contacts(self, reason: str = "Manual discovery") -> bool:
        """Manually discover companion contacts"""
        try:
            from meshcore_cli.meshcore_cli import next_cmd
            
            self.logger.info("Starting manual companion contact discovery...")
            
            result = await asyncio.wait_for(
                next_cmd(self.bot.meshcore, ["discover_companion_contacts"]),
                timeout=30.0
            )
            
            self.logger.info("Successfully initiated companion contact discovery")
            self.logger.debug(f"Discovery result: {result}")
            
            # Log the action
            self.db_manager.execute_update(
                'INSERT INTO purging_log (action, details) VALUES (?, ?)',
                ('companion_discovery', f'Manual companion contact discovery - {reason}')
            )
            
            return True
            
        except asyncio.TimeoutError:
            self.logger.warning("Timeout during companion contact discovery (LoRa communication)")
            return False
        except Exception as e:
            self.logger.error(f"Failed to discover companion contacts: {e}")
            return False
    
    async def restore_repeater(self, public_key: str, reason: str = "Manual restore") -> bool:
        """Restore a previously purged repeater"""
        try:
            # Get repeater info before updating
            result = self.db_manager.execute_query('''
                SELECT name, contact_data FROM repeater_contacts WHERE public_key = ?
            ''', (public_key,))
            
            if not result:
                self.logger.warning(f"No repeater found with public key {public_key}")
                return False
            
            name = result[0]['name']
            
            # Mark as active again
            self.db_manager.execute_update(
                'UPDATE repeater_contacts SET is_active = 1 WHERE public_key = ?',
                (public_key,)
            )
            
            # Log the restore action
            self.db_manager.execute_update('''
                INSERT INTO purging_log (action, public_key, name, reason)
                VALUES ('restored', ?, ?, ?)
            ''', (public_key, name, reason))
            
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
            # Get total counts
            total_repeaters = self.db_manager.execute_query('SELECT COUNT(*) as count FROM repeater_contacts')[0]['count']
            active_repeaters = self.db_manager.execute_query('SELECT COUNT(*) as count FROM repeater_contacts WHERE is_active = 1')[0]['count']
            purged_repeaters = self.db_manager.execute_query('SELECT COUNT(*) as count FROM repeater_contacts WHERE is_active = 0')[0]['count']
            
            # Get recent purging activity
            recent_activity = self.db_manager.execute_query('''
                SELECT action, COUNT(*) as count FROM purging_log 
                WHERE timestamp > datetime('now', '-7 days')
                GROUP BY action
            ''')
            
            return {
                'total_repeaters': total_repeaters,
                'active_repeaters': active_repeaters,
                'purged_repeaters': purged_repeaters,
                'recent_activity_7_days': {row['action']: row['count'] for row in recent_activity}
            }
                
        except Exception as e:
            self.logger.error(f"Error getting purging stats: {e}")
            return {}
    
    async def cleanup_database(self, days_to_keep_logs: int = 90):
        """Clean up old purging log entries"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep_logs)
            
            deleted_count = self.db_manager.execute_update(
                'DELETE FROM purging_log WHERE timestamp < ?',
                (cutoff_date.isoformat(),)
            )
            
            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old purging log entries")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up database: {e}")
    
    # Delegate geocoding cache methods to db_manager
    def get_cached_geocoding(self, query: str) -> Tuple[Optional[float], Optional[float]]:
        """Get cached geocoding result for a query"""
        return self.db_manager.get_cached_geocoding(query)
    
    def cache_geocoding(self, query: str, latitude: float, longitude: float, cache_hours: int = 24):
        """Cache geocoding result for future use"""
        self.db_manager.cache_geocoding(query, latitude, longitude, cache_hours)
    
    def cleanup_geocoding_cache(self):
        """Remove expired geocoding cache entries"""
        self.db_manager.cleanup_geocoding_cache()