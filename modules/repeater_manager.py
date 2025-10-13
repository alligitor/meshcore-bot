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
        
        # Check for and handle database schema migration
        self._migrate_database_schema()
    
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
                latitude REAL,
                longitude REAL,
                city TEXT,
                state TEXT,
                country TEXT,
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
    
    def _migrate_database_schema(self):
        """Handle database schema migration for existing installations"""
        try:
            # Check if the new location columns exist
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(repeater_contacts)")
                columns = [row[1] for row in cursor.fetchall()]
                
                # Add missing location columns if they don't exist
                new_columns = [
                    ('latitude', 'REAL'),
                    ('longitude', 'REAL'),
                    ('city', 'TEXT'),
                    ('state', 'TEXT'),
                    ('country', 'TEXT')
                ]
                
                for column_name, column_type in new_columns:
                    if column_name not in columns:
                        self.logger.info(f"Adding missing column: {column_name}")
                        cursor.execute(f"ALTER TABLE repeater_contacts ADD COLUMN {column_name} {column_type}")
                        conn.commit()
                
                self.logger.info("Database schema migration completed")
                
        except Exception as e:
            self.logger.error(f"Error during database schema migration: {e}")
    
    def _extract_location_data(self, contact_data: Dict) -> Dict[str, Optional[str]]:
        """Extract location data from contact_data JSON"""
        location_info = {
            'latitude': None,
            'longitude': None,
            'city': None,
            'state': None,
            'country': None
        }
        
        try:
            # Check for various possible location field names in contact data
            location_fields = [
                'location', 'gps', 'coordinates', 'lat_lon', 'lat_lng',
                'position', 'geo', 'geolocation', 'loc'
            ]
            
            for field in location_fields:
                if field in contact_data:
                    loc_data = contact_data[field]
                    if isinstance(loc_data, dict):
                        # Handle structured location data
                        if 'lat' in loc_data and 'lon' in loc_data:
                            try:
                                location_info['latitude'] = float(loc_data['lat'])
                                location_info['longitude'] = float(loc_data['lon'])
                            except (ValueError, TypeError):
                                pass
                        elif 'latitude' in loc_data and 'longitude' in loc_data:
                            try:
                                location_info['latitude'] = float(loc_data['latitude'])
                                location_info['longitude'] = float(loc_data['longitude'])
                            except (ValueError, TypeError):
                                pass
                        
                        # Extract city/state/country if available
                        for addr_field in ['city', 'state', 'country', 'region', 'province']:
                            if addr_field in loc_data and loc_data[addr_field]:
                                if addr_field == 'region' or addr_field == 'province':
                                    location_info['state'] = str(loc_data[addr_field])
                                else:
                                    location_info[addr_field] = str(loc_data[addr_field])
                    
                    elif isinstance(loc_data, str):
                        # Handle string location data (e.g., "lat,lon" or "city, state")
                        if ',' in loc_data:
                            parts = [p.strip() for p in loc_data.split(',')]
                            if len(parts) >= 2:
                                try:
                                    # Try to parse as coordinates
                                    lat = float(parts[0])
                                    lon = float(parts[1])
                                    location_info['latitude'] = lat
                                    location_info['longitude'] = lon
                                except ValueError:
                                    # Treat as city, state format
                                    location_info['city'] = parts[0]
                                    if len(parts) > 1:
                                        location_info['state'] = parts[1]
                                    if len(parts) > 2:
                                        location_info['country'] = parts[2]
            
            # Check for individual lat/lon fields (including MeshCore-specific fields)
            for lat_field in ['adv_lat', 'lat', 'latitude', 'gps_lat']:
                if lat_field in contact_data:
                    try:
                        location_info['latitude'] = float(contact_data[lat_field])
                        break
                    except (ValueError, TypeError):
                        pass
            
            for lon_field in ['adv_lon', 'lon', 'lng', 'longitude', 'gps_lon', 'gps_lng']:
                if lon_field in contact_data:
                    try:
                        location_info['longitude'] = float(contact_data[lon_field])
                        break
                    except (ValueError, TypeError):
                        pass
            
            # Check for address fields
            for city_field in ['city', 'town', 'municipality']:
                if city_field in contact_data and contact_data[city_field]:
                    location_info['city'] = str(contact_data[city_field])
                    break
            
            for state_field in ['state', 'province', 'region']:
                if state_field in contact_data and contact_data[state_field]:
                    location_info['state'] = str(contact_data[state_field])
                    break
            
            for country_field in ['country', 'nation']:
                if country_field in contact_data and contact_data[country_field]:
                    location_info['country'] = str(contact_data[country_field])
                    break
            
            # Validate coordinates if we have them
            if location_info['latitude'] is not None and location_info['longitude'] is not None:
                lat, lon = location_info['latitude'], location_info['longitude']
                
                # Treat 0,0 coordinates as "hidden" location (common in MeshCore)
                if lat == 0.0 and lon == 0.0:
                    location_info['latitude'] = None
                    location_info['longitude'] = None
                # Check for valid coordinate ranges
                elif not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    # Invalid coordinates
                    location_info['latitude'] = None
                    location_info['longitude'] = None
            
        except Exception as e:
            self.logger.debug(f"Error extracting location data: {e}")
        
        return location_info

    def _get_city_from_coordinates(self, latitude: float, longitude: float) -> Optional[str]:
        """Get city name from coordinates using reverse geocoding, with neighborhood for large cities"""
        try:
            from geopy.geocoders import Nominatim
            
            # Initialize geocoder
            geolocator = Nominatim(user_agent="meshcore-bot")
            
            # Perform reverse geocoding
            location = geolocator.reverse(f"{latitude}, {longitude}")
            if location:
                address = location.raw.get('address', {})
                
                # Get city name from various fields
                city = (address.get('city') or 
                       address.get('town') or 
                       address.get('village') or 
                       address.get('hamlet') or 
                       address.get('municipality') or 
                       address.get('suburb'))
                
                if city:
                    # For large cities, try to get neighborhood information
                    neighborhood = self._get_neighborhood_for_large_city(address, city)
                    if neighborhood:
                        return f"{neighborhood}, {city}"
                    else:
                        return city
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error getting city from coordinates {latitude}, {longitude}: {e}")
            return None
    
    def _get_full_location_from_coordinates(self, latitude: float, longitude: float) -> Dict[str, Optional[str]]:
        """Get complete location information (city, state, country) from coordinates using reverse geocoding"""
        location_info = {
            'city': None,
            'state': None,
            'country': None
        }
        
        try:
            # Validate coordinates first
            if latitude == 0.0 and longitude == 0.0:
                self.logger.debug(f"Skipping geocoding for hidden location: {latitude}, {longitude}")
                return location_info
            
            # Check for valid coordinate ranges
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                self.logger.debug(f"Skipping geocoding for invalid coordinates: {latitude}, {longitude}")
                return location_info
            
            # Check cache first to avoid duplicate API calls
            cache_key = f"location_{latitude:.6f}_{longitude:.6f}"
            cached_result = self.db_manager.get_cached_json(cache_key, "geolocation")
            
            if cached_result:
                self.logger.debug(f"Using cached location data for {latitude}, {longitude}")
                return cached_result
            
            from geopy.geocoders import Nominatim
            
            # Initialize geocoder with proper user agent and timeout
            geolocator = Nominatim(
                user_agent="meshcore-bot-geolocation-update",
                timeout=10  # 10 second timeout
            )
            
            # Perform reverse geocoding
            location = geolocator.reverse(f"{latitude}, {longitude}")
            if location:
                address = location.raw.get('address', {})
                
                # Get city name from various fields
                city = (address.get('city') or 
                       address.get('town') or 
                       address.get('village') or 
                       address.get('hamlet') or 
                       address.get('municipality') or 
                       address.get('suburb'))
                
                if city:
                    # For large cities, try to get neighborhood information
                    neighborhood = self._get_neighborhood_for_large_city(address, city)
                    if neighborhood:
                        location_info['city'] = f"{neighborhood}, {city}"
                    else:
                        location_info['city'] = city
                
                # Get state/province information
                state = (address.get('state') or 
                        address.get('province') or 
                        address.get('region') or 
                        address.get('county'))
                if state:
                    location_info['state'] = state
                
                # Get country information
                country = (address.get('country') or 
                          address.get('country_code'))
                if country:
                    location_info['country'] = country
            
            # Cache the result for 24 hours to avoid duplicate API calls
            self.db_manager.cache_json(cache_key, location_info, "geolocation", cache_hours=24)
            
            return location_info
            
        except Exception as e:
            error_msg = str(e)
            if "No route to host" in error_msg or "Connection" in error_msg:
                self.logger.warning(f"Network error geocoding {latitude}, {longitude}: {error_msg}")
            else:
                self.logger.debug(f"Error getting full location from coordinates {latitude}, {longitude}: {e}")
            return location_info
    
    def _get_neighborhood_for_large_city(self, address: dict, city: str) -> Optional[str]:
        """Get neighborhood information for large cities"""
        try:
            # List of large cities where neighborhood info is useful
            large_cities = [
                'seattle', 'portland', 'san francisco', 'los angeles', 'san diego',
                'chicago', 'new york', 'boston', 'philadelphia', 'washington',
                'atlanta', 'miami', 'houston', 'dallas', 'austin', 'denver',
                'phoenix', 'las vegas', 'minneapolis', 'detroit', 'cleveland',
                'pittsburgh', 'baltimore', 'richmond', 'norfolk', 'tampa',
                'orlando', 'jacksonville', 'nashville', 'memphis', 'kansas city',
                'st louis', 'milwaukee', 'cincinnati', 'columbus', 'indianapolis',
                'louisville', 'lexington', 'charlotte', 'raleigh', 'greensboro',
                'winston-salem', 'durham', 'charleston', 'columbia', 'greenville',
                'savannah', 'augusta', 'macon', 'columbus', 'atlanta'
            ]
            
            # Check if this is a large city
            if city.lower() not in large_cities:
                return None
            
            # Try to get neighborhood information from various address fields
            neighborhood_fields = [
                'neighbourhood', 'neighborhood', 'suburb', 'quarter', 'district',
                'area', 'locality', 'hamlet', 'village', 'town'
            ]
            
            for field in neighborhood_fields:
                if field in address and address[field]:
                    neighborhood = address[field]
                    # Skip if it's the same as the city name
                    if neighborhood.lower() != city.lower():
                        return neighborhood
            
            # For Seattle specifically, try to get more specific area info
            if city.lower() == 'seattle':
                # Check for specific Seattle neighborhoods/areas
                seattle_areas = [
                    'capitol hill', 'ballard', 'fremont', 'queen anne', 'belltown',
                    'pioneer square', 'international district', 'chinatown',
                    'first hill', 'central district', 'central', 'beacon hill',
                    'columbia city', 'rainier valley', 'west seattle', 'alki',
                    'magnolia', 'greenwood', 'phinney ridge', 'wallingford',
                    'university district', 'udistrict', 'ravenna', 'laurelhurst',
                    'sand point', 'wedgwood', 'view ridge', 'matthews beach',
                    'lake city', 'bitter lake', 'broadview', 'crown hill',
                    'loyal heights', 'sunset hill', 'interbay', 'downtown',
                    'south lake union', 'denny triangle', 'denny regrade',
                    'eastlake', 'montlake', 'madison park', 'madrona',
                    'leschi', 'mount baker', 'columbia city', 'rainier beach',
                    'south park', 'georgetown', 'soho', 'industrial district'
                ]
                
                # Check if any of the address fields contain Seattle neighborhood names
                for field, value in address.items():
                    if isinstance(value, str):
                        value_lower = value.lower()
                        for area in seattle_areas:
                            if area in value_lower:
                                return area.title()
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error getting neighborhood for {city}: {e}")
            return None

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
        updated_count = 0
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
                    
                    # Extract location data from contact_data
                    location_info = self._extract_location_data(contact_data)
                    
                    # Check if already exists and get existing location data
                    existing = self.db_manager.execute_query(
                        'SELECT id, last_seen, latitude, longitude, city FROM repeater_contacts WHERE public_key = ?',
                        (public_key,)
                    )
                    
                    # If we have coordinates but no city, try to get city from coordinates
                    # Skip 0,0 coordinates as they indicate "hidden" location
                    # Skip reverse geocoding if coordinates haven't changed and we already have a city
                    should_geocode = (
                        location_info['latitude'] is not None and 
                        location_info['longitude'] is not None and 
                        not (location_info['latitude'] == 0.0 and location_info['longitude'] == 0.0) and
                        not location_info['city']
                    )
                    
                    # If repeater exists, check if coordinates changed or if we need to geocode
                    if existing and should_geocode:
                        existing_lat = existing[0][2] if existing[0][2] is not None else 0.0
                        existing_lon = existing[0][3] if existing[0][3] is not None else 0.0
                        existing_city = existing[0][4]
                        
                        # Only geocode if coordinates changed or we don't have a city
                        coordinates_changed = (
                            abs(location_info['latitude'] - existing_lat) > 0.0001 or 
                            abs(location_info['longitude'] - existing_lon) > 0.0001
                        )
                        
                        if not coordinates_changed and existing_city:
                            # Use existing city data, no need to geocode
                            location_info['city'] = existing_city
                            should_geocode = False
                    
                    if should_geocode:
                        city_from_coords = self._get_city_from_coordinates(
                            location_info['latitude'], 
                            location_info['longitude']
                        )
                        if city_from_coords:
                            location_info['city'] = city_from_coords
                    
                    if existing:
                        # Update last_seen timestamp and location data if available
                        update_query = 'UPDATE repeater_contacts SET last_seen = CURRENT_TIMESTAMP, is_active = 1'
                        update_params = []
                        
                        # Add location fields if we have new data
                        if location_info['latitude'] is not None:
                            update_query += ', latitude = ?'
                            update_params.append(location_info['latitude'])
                        if location_info['longitude'] is not None:
                            update_query += ', longitude = ?'
                            update_params.append(location_info['longitude'])
                        if location_info['city']:
                            update_query += ', city = ?'
                            update_params.append(location_info['city'])
                        if location_info['state']:
                            update_query += ', state = ?'
                            update_params.append(location_info['state'])
                        if location_info['country']:
                            update_query += ', country = ?'
                            update_params.append(location_info['country'])
                        
                        update_query += ' WHERE public_key = ?'
                        update_params.append(public_key)
                        
                        self.db_manager.execute_update(update_query, tuple(update_params))
                        updated_count += 1
                    else:
                        # Insert new repeater with location data
                        self.db_manager.execute_update('''
                            INSERT INTO repeater_contacts 
                            (public_key, name, device_type, contact_data, latitude, longitude, city, state, country)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            public_key,
                            name,
                            device_type,
                            json.dumps(contact_data),
                            location_info['latitude'],
                            location_info['longitude'],
                            location_info['city'],
                            location_info['state'],
                            location_info['country']
                        ))
                        
                        # Log the addition
                        self.db_manager.execute_update('''
                            INSERT INTO purging_log (action, public_key, name, reason)
                            VALUES ('added', ?, ?, 'Auto-detected during contact scan')
                        ''', (public_key, name))
                        
                        cataloged_count += 1
                        location_str = ""
                        if location_info['city'] or location_info['latitude']:
                            if location_info['city']:
                                location_str = f" in {location_info['city']}"
                                if location_info['state']:
                                    location_str += f", {location_info['state']}"
                            elif location_info['latitude'] and location_info['longitude']:
                                location_str = f" at {location_info['latitude']:.4f}, {location_info['longitude']:.4f}"
                        self.logger.info(f"Cataloged new repeater: {name} ({device_type}){location_str}")
                
        except Exception as e:
            self.logger.error(f"Error scanning contacts for repeaters: {e}")
        
        if cataloged_count > 0:
            self.logger.info(f"Cataloged {cataloged_count} new repeaters")
        
        if updated_count > 0:
            self.logger.info(f"Updated {updated_count} existing repeaters with location data")
        
        self.logger.info(f"Scan completed: {cataloged_count} new repeaters cataloged, {updated_count} existing repeaters updated from {len(contacts)} contacts")
        self.logger.info(f"Scan summary: {processed_count} contacts processed, {cataloged_count + updated_count} repeaters processed")
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
            
            # Check if repeater exists in database, if not add it first
            existing_repeater = self.db_manager.execute_query(
                'SELECT id FROM repeater_contacts WHERE public_key = ?',
                (public_key,)
            )
            
            if not existing_repeater:
                # Add repeater to database first
                contact_name = contact_to_remove.get('adv_name', contact_to_remove.get('name', 'Unknown'))
                device_type = 'Repeater'
                if contact_to_remove.get('type') == 3:
                    device_type = 'RoomServer'
                elif 'room' in contact_name.lower() or 'server' in contact_name.lower():
                    device_type = 'RoomServer'
                
                self.db_manager.execute_update('''
                    INSERT INTO repeater_contacts 
                    (public_key, name, device_type, contact_data)
                    VALUES (?, ?, ?, ?)
                ''', (
                    public_key,
                    contact_name,
                    device_type,
                    json.dumps(contact_to_remove)
                ))
                
                self.logger.info(f"Added repeater {contact_name} to database before purging")
            
            # Track whether device removal was successful
            device_removal_successful = False
            
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
                    import sys
                    import io
                    
                    # Capture stdout/stderr to catch "Unknown contact" messages
                    old_stdout = sys.stdout
                    old_stderr = sys.stderr
                    captured_output = io.StringIO()
                    captured_errors = io.StringIO()
                    
                    try:
                        sys.stdout = captured_output
                        sys.stderr = captured_errors
                        
                        # Use contact name instead of public key for removal
                        contact_name = contact_data.get('adv_name', contact_data.get('name', 'Unknown'))
                        result = await asyncio.wait_for(
                            next_cmd(self.bot.meshcore, ["remove_contact", contact_name]),
                            timeout=30.0  # 30 second timeout for LoRa communication
                        )
                    finally:
                        sys.stdout = old_stdout
                        sys.stderr = old_stderr
                    
                    # Get captured output
                    stdout_content = captured_output.getvalue()
                    stderr_content = captured_errors.getvalue()
                    all_output = stdout_content + stderr_content
                    
                    end_time = asyncio.get_event_loop().time()
                    duration = end_time - start_time
                    self.logger.info(f"Remove command completed in {duration:.2f} seconds")
                    
                    # Check if removal was successful
                    # Note: meshcore-cli prints "Unknown contact" to stdout/stderr if contact doesn't exist
                    self.logger.debug(f"Command result: {result}")
                    self.logger.debug(f"Captured output: {all_output}")
                    
                    # Check if the captured output indicates the contact was unknown (doesn't exist)
                    if "unknown contact" in all_output.lower():
                        self.logger.warning(f"Contact '{contact_name}' was not found on device - this suggests the contact list is out of sync")
                        # Don't mark as successful - we need to actually remove contacts that exist
                        device_removal_successful = False
                    elif result is not None:
                        self.logger.info(f"Successfully removed contact '{contact_name}' from device")
                        
                        # Verify the contact was actually removed by checking if it still exists
                        await asyncio.sleep(1)  # Give device time to process
                        contact_still_exists = False
                        for check_key, check_data in self.bot.meshcore.contacts.items():
                            if check_data.get('public_key', check_key) == public_key:
                                contact_still_exists = True
                                break
                        
                        if contact_still_exists:
                            self.logger.warning(f"Contact '{contact_name}' still exists after removal command - removal may have failed")
                            device_removal_successful = False
                        else:
                            self.logger.info(f"Verified: Contact '{contact_name}' successfully removed from device")
                            device_removal_successful = True
                    else:
                        self.logger.warning(f"Contact removal command returned no result for '{contact_name}'")
                        device_removal_successful = False
                        
                except asyncio.TimeoutError:
                    end_time = asyncio.get_event_loop().time()
                    duration = end_time - start_time
                    self.logger.warning(f"Timeout removing contact '{contact_name}' after {duration:.2f} seconds (LoRa communication)")
                    device_removal_successful = False
                except Exception as cmd_error:
                    end_time = asyncio.get_event_loop().time()
                    duration = end_time - start_time
                    self.logger.error(f"Command error removing contact '{contact_name}' after {duration:.2f} seconds: {cmd_error}")
                    self.logger.debug(f"Error type: {type(cmd_error).__name__}")
                    device_removal_successful = False
                
            except Exception as e:
                self.logger.error(f"Failed to remove contact '{contact_name}' from device: {e}")
                self.logger.debug(f"Error type: {type(e).__name__}")
                device_removal_successful = False
            
            # Only mark as inactive in database if device removal was successful
            if device_removal_successful:
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
            else:
                self.logger.error(f"Failed to remove repeater {contact_name} from device - not marking as purged in database")
                # Log the failed attempt
                self.db_manager.execute_update('''
                    INSERT INTO purging_log (action, public_key, name, reason)
                    VALUES ('purge_failed', ?, ?, ?)
                ''', (public_key, contact_name, f"{reason} - Device removal failed"))
                return False
            
        except Exception as e:
            self.logger.error(f"Error purging repeater {public_key}: {e}")
            self.logger.debug(f"Error type: {type(e).__name__}")
            return False
    
    async def purge_repeater_by_contact_key(self, contact_key: str, reason: str = "Manual purge") -> bool:
        """Remove a repeater using the contact key from the device's contact list"""
        self.logger.info(f"Starting purge process for contact_key: {contact_key}")
        self.logger.debug(f"Purge reason: {reason}")
        
        try:
            # Find the contact in meshcore using the contact key
            if contact_key not in self.bot.meshcore.contacts:
                self.logger.warning(f"Contact with key {contact_key} not found in current contacts")
                return False
            
            contact_data = self.bot.meshcore.contacts[contact_key]
            contact_name = contact_data.get('adv_name', contact_data.get('name', 'Unknown'))
            public_key = contact_data.get('public_key', contact_key)
            
            self.logger.info(f"Found contact: {contact_name} (key: {contact_key}, public_key: {public_key[:16]}...)")
            
            # Check if repeater exists in database, if not add it first
            existing_repeater = self.db_manager.execute_query(
                'SELECT id FROM repeater_contacts WHERE public_key = ?',
                (public_key,)
            )
            
            if not existing_repeater:
                # Add repeater to database first
                device_type = 'Repeater'
                if contact_data.get('type') == 3:
                    device_type = 'RoomServer'
                elif 'room' in contact_name.lower() or 'server' in contact_name.lower():
                    device_type = 'RoomServer'
                
                self.db_manager.execute_update('''
                    INSERT INTO repeater_contacts 
                    (public_key, name, device_type, contact_data)
                    VALUES (?, ?, ?, ?)
                ''', (
                    public_key,
                    contact_name,
                    device_type,
                    json.dumps(contact_data)
                ))
                
                self.logger.info(f"Added repeater {contact_name} to database before purging")
            
            # Track whether device removal was successful
            device_removal_successful = False
            
            # Try multiple approaches to remove the contact
            try:
                self.logger.info(f"Starting removal of contact '{contact_name}' from device...")
                
                # Method 1: Try direct removal from contacts dictionary
                try:
                    self.logger.info(f"Method 1: Attempting direct removal from contacts dictionary...")
                    if contact_key in self.bot.meshcore.contacts:
                        del self.bot.meshcore.contacts[contact_key]
                        self.logger.info(f"Successfully removed contact '{contact_name}' from contacts dictionary")
                        device_removal_successful = True
                    else:
                        self.logger.warning(f"Contact '{contact_name}' not found in contacts dictionary")
                except Exception as e:
                    self.logger.warning(f"Direct removal failed: {e}")
                
                # Method 2: Try using meshcore commands if available
                if not device_removal_successful and hasattr(self.bot.meshcore, 'commands'):
                    try:
                        self.logger.info(f"Method 2: Attempting removal via meshcore commands...")
                        # Check if there's a remove_contact method
                        if hasattr(self.bot.meshcore.commands, 'remove_contact'):
                            # Try different parameter combinations
                            try:
                                # Try with contact_data
                                result = await self.bot.meshcore.commands.remove_contact(contact_data)
                                if result:
                                    self.logger.info(f"Successfully removed contact '{contact_name}' via meshcore commands (contact_data)")
                                    device_removal_successful = True
                            except Exception as e1:
                                self.logger.debug(f"remove_contact(contact_data) failed: {e1}")
                                try:
                                    # Try with public_key
                                    result = await self.bot.meshcore.commands.remove_contact(public_key)
                                    if result:
                                        self.logger.info(f"Successfully removed contact '{contact_name}' via meshcore commands (public_key)")
                                        device_removal_successful = True
                                except Exception as e2:
                                    self.logger.debug(f"remove_contact(public_key) failed: {e2}")
                                    try:
                                        # Try with contact_key
                                        result = await self.bot.meshcore.commands.remove_contact(contact_key)
                                        if result:
                                            self.logger.info(f"Successfully removed contact '{contact_name}' via meshcore commands (contact_key)")
                                            device_removal_successful = True
                                    except Exception as e3:
                                        self.logger.debug(f"remove_contact(contact_key) failed: {e3}")
                                        self.logger.warning(f"All meshcore commands remove_contact attempts failed")
                        else:
                            self.logger.info("No remove_contact method found in meshcore commands")
                    except Exception as e:
                        self.logger.warning(f"Meshcore commands removal failed: {e}")
                
                # Method 3: Try CLI as fallback
                if not device_removal_successful:
                    try:
                        self.logger.info(f"Method 3: Attempting removal via CLI...")
                        import asyncio
                        import sys
                        import io
                        
                        # Use asyncio.wait_for to add timeout for LoRa communication
                        start_time = asyncio.get_event_loop().time()
                        
                        # Use the meshcore-cli API for device commands
                        from meshcore_cli.meshcore_cli import next_cmd
                        
                        # Capture stdout/stderr to catch "Unknown contact" messages
                        old_stdout = sys.stdout
                        old_stderr = sys.stderr
                        captured_output = io.StringIO()
                        captured_errors = io.StringIO()
                        
                        try:
                            sys.stdout = captured_output
                            sys.stderr = captured_errors
                            
                            # Try using the contact key instead of public key
                            result = await asyncio.wait_for(
                                next_cmd(self.bot.meshcore, ["remove_contact", contact_key]),
                                timeout=30.0  # 30 second timeout for LoRa communication
                            )
                        finally:
                            sys.stdout = old_stdout
                            sys.stderr = old_stderr
                        
                        # Get captured output
                        stdout_content = captured_output.getvalue()
                        stderr_content = captured_errors.getvalue()
                        all_output = stdout_content + stderr_content
                        
                        end_time = asyncio.get_event_loop().time()
                        duration = end_time - start_time
                        self.logger.info(f"CLI remove command completed in {duration:.2f} seconds")
                        
                        # Check if removal was successful
                        self.logger.debug(f"CLI command result: {result}")
                        self.logger.debug(f"CLI captured output: {all_output}")
                        
                        # Check if the captured output indicates the contact was unknown (doesn't exist)
                        if "unknown contact" in all_output.lower():
                            self.logger.warning(f"CLI: Contact '{contact_name}' was not found on device")
                        elif result is not None:
                            self.logger.info(f"CLI: Successfully removed contact '{contact_name}' from device")
                            device_removal_successful = True
                        else:
                            self.logger.warning(f"CLI: Contact removal command returned no result for '{contact_name}'")
                            
                    except Exception as e:
                        self.logger.warning(f"CLI removal failed: {e}")
                
                # Verify removal and ensure persistence
                if device_removal_successful:
                    import asyncio
                    await asyncio.sleep(3)  # Give device more time to process and save
                    
                    # Try to force device to save changes
                    try:
                        self.logger.info(f"Attempting to force device to save contact changes...")
                        from meshcore_cli.meshcore_cli import next_cmd
                        
                        # Try to refresh contacts from device
                        try:
                            self.logger.info("Refreshing contacts from device...")
                            await asyncio.wait_for(
                                next_cmd(self.bot.meshcore, ["contacts"]),
                                timeout=15.0
                            )
                            self.logger.info("Contacts refreshed from device")
                        except Exception as e:
                            self.logger.warning(f"Failed to refresh contacts: {e}")
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to force device persistence: {e}")
                    
                    # Wait a bit more after refresh
                    await asyncio.sleep(1)
                    
                    # Check if contact still exists in the bot's memory after refresh
                    contact_still_exists = contact_key in self.bot.meshcore.contacts
                    
                    if contact_still_exists:
                        self.logger.warning(f"Contact '{contact_name}' still exists after removal and refresh - removal may have failed")
                        device_removal_successful = False
                    else:
                        self.logger.info(f"Verified: Contact '{contact_name}' successfully removed from device")
                
            except Exception as e:
                self.logger.error(f"Failed to remove contact '{contact_name}' from device: {e}")
                self.logger.debug(f"Error type: {type(e).__name__}")
                device_removal_successful = False
            
            # Only mark as inactive in database if device removal was successful
            if device_removal_successful:
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
            else:
                self.logger.error(f"Failed to remove repeater {contact_name} from device - not marking as purged in database")
                # Log the failed attempt
                self.db_manager.execute_update('''
                    INSERT INTO purging_log (action, public_key, name, reason)
                    VALUES ('purge_failed', ?, ?, ?)
                ''', (public_key, contact_name, f"{reason} - Device removal failed"))
                return False
            
        except Exception as e:
            self.logger.error(f"Error purging repeater {contact_key}: {e}")
            self.logger.debug(f"Error type: {type(e).__name__}")
            return False
    
    async def force_purge_repeater_from_contacts(self, public_key: str, reason: str = "Force purge") -> bool:
        """Force remove a repeater from device contacts using multiple methods"""
        self.logger.info(f"Starting FORCE purge process for public_key: {public_key}")
        self.logger.debug(f"Force purge reason: {reason}")
        
        try:
            # Find the contact in meshcore
            contact_to_remove = None
            contact_name = None
            
            for contact_key, contact_data in self.bot.meshcore.contacts.items():
                if contact_data.get('public_key', contact_key) == public_key:
                    contact_to_remove = contact_data
                    contact_name = contact_data.get('adv_name', contact_data.get('name', 'Unknown'))
                    break
            
            if not contact_to_remove:
                self.logger.warning(f"Repeater with public key {public_key} not found in current contacts")
                return False
            
            # Method 1: Try standard removal
            self.logger.info(f"Method 1: Attempting standard removal for '{contact_name}'")
            success = await self.purge_repeater_from_contacts(public_key, reason)
            if success:
                self.logger.info(f"Standard removal successful for '{contact_name}'")
                return True
            
            # Method 2: Try alternative removal commands
            self.logger.info(f"Method 2: Attempting alternative removal for '{contact_name}'")
            try:
                from meshcore_cli.meshcore_cli import next_cmd
                
                # Try different removal commands
                alternative_commands = [
                    ["delete_contact", public_key],
                    ["remove", public_key],
                    ["del", public_key],
                    ["clear_contact", public_key]
                ]
                
                for cmd in alternative_commands:
                    try:
                        self.logger.info(f"Trying command: {' '.join(cmd)}")
                        
                        # Capture stdout/stderr to catch "Unknown contact" messages
                        import sys
                        import io
                        old_stdout = sys.stdout
                        old_stderr = sys.stderr
                        captured_output = io.StringIO()
                        captured_errors = io.StringIO()
                        
                        try:
                            sys.stdout = captured_output
                            sys.stderr = captured_errors
                            
                            result = await asyncio.wait_for(
                                next_cmd(self.bot.meshcore, cmd),
                                timeout=15.0
                            )
                        finally:
                            sys.stdout = old_stdout
                            sys.stderr = old_stderr
                        
                        # Get captured output
                        stdout_content = captured_output.getvalue()
                        stderr_content = captured_errors.getvalue()
                        all_output = stdout_content + stderr_content
                        
                        if result is not None:
                            self.logger.debug(f"Alternative command {' '.join(cmd)} result: {result}")
                            self.logger.debug(f"Captured output: {all_output}")
                            
                            # Check if the captured output indicates the contact was unknown (doesn't exist)
                            if "unknown contact" in all_output.lower():
                                self.logger.warning(f"Contact '{contact_name}' was not found on device - this suggests the contact list is out of sync")
                                # Don't mark as successful - we need to actually remove contacts that exist
                                continue  # Try next command
                            else:
                                self.logger.info(f"Alternative command {' '.join(cmd)} succeeded")
                                # Verify removal
                                await asyncio.sleep(1)
                                contact_still_exists = False
                                for check_key, check_data in self.bot.meshcore.contacts.items():
                                    if check_data.get('public_key', check_key) == public_key:
                                        contact_still_exists = True
                                        break
                                
                                if not contact_still_exists:
                                    # Mark as purged in database
                                    self.db_manager.execute_update(
                                        'UPDATE repeater_contacts SET is_active = 0, purge_count = purge_count + 1 WHERE public_key = ?',
                                        (public_key,)
                                    )
                                    
                                    self.db_manager.execute_update('''
                                        INSERT INTO purging_log (action, public_key, name, reason)
                                        VALUES ('force_purged', ?, ?, ?)
                                    ''', (public_key, contact_name, f"{reason} - Alternative command: {' '.join(cmd)}"))
                                    
                                    self.logger.info(f"Force purge successful for '{contact_name}' using {' '.join(cmd)}")
                                    return True
                    except Exception as e:
                        self.logger.debug(f"Alternative command {' '.join(cmd)} failed: {e}")
                        continue
                        
            except Exception as e:
                self.logger.error(f"Error with alternative removal methods: {e}")
            
            # Method 3: Mark as purged anyway and log the issue
            self.logger.warning(f"All removal methods failed for '{contact_name}' - marking as purged anyway")
            self.db_manager.execute_update(
                'UPDATE repeater_contacts SET is_active = 0, purge_count = purge_count + 1 WHERE public_key = ?',
                (public_key,)
            )
            
            self.db_manager.execute_update('''
                INSERT INTO purging_log (action, public_key, name, reason)
                VALUES ('force_purged_failed', ?, ?, ?)
            ''', (public_key, contact_name, f"{reason} - All removal methods failed, marked as purged anyway"))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in force purge for repeater {public_key}: {e}")
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
        """Add a discovered contact to the contact list using multiple methods"""
        try:
            self.logger.info(f"Adding discovered contact: {contact_name}")
            
            # Track whether contact addition was successful
            contact_addition_successful = False
            
            # Method 1: Try using meshcore commands if available
            if hasattr(self.bot.meshcore, 'commands'):
                try:
                    self.logger.info(f"Method 1: Attempting addition via meshcore commands...")
                    # Check if there's an add_contact method
                    if hasattr(self.bot.meshcore.commands, 'add_contact'):
                        # Try different parameter combinations
                        try:
                            # Try with contact_name and public_key
                            result = await self.bot.meshcore.commands.add_contact(contact_name, public_key)
                            if result:
                                self.logger.info(f"Successfully added contact '{contact_name}' via meshcore commands (name+key)")
                                contact_addition_successful = True
                        except Exception as e1:
                            self.logger.debug(f"add_contact(name, key) failed: {e1}")
                            try:
                                # Try with just contact_name
                                result = await self.bot.meshcore.commands.add_contact(contact_name)
                                if result:
                                    self.logger.info(f"Successfully added contact '{contact_name}' via meshcore commands (name only)")
                                    contact_addition_successful = True
                            except Exception as e2:
                                self.logger.debug(f"add_contact(name) failed: {e2}")
                                self.logger.warning(f"All meshcore commands add_contact attempts failed")
                    else:
                        self.logger.info("No add_contact method found in meshcore commands")
                except Exception as e:
                    self.logger.warning(f"Meshcore commands addition failed: {e}")
            
            # Method 2: Try CLI as fallback
            if not contact_addition_successful:
                try:
                    self.logger.info(f"Method 2: Attempting addition via CLI...")
                    from meshcore_cli.meshcore_cli import next_cmd
                    import sys
                    import io
                    
                    # Capture stdout/stderr to catch any error messages
                    old_stdout = sys.stdout
                    old_stderr = sys.stderr
                    captured_output = io.StringIO()
                    captured_errors = io.StringIO()
                    
                    try:
                        sys.stdout = captured_output
                        sys.stderr = captured_errors
                        
                        result = await asyncio.wait_for(
                            next_cmd(self.bot.meshcore, ["add_contact", contact_name, public_key] if public_key else ["add_contact", contact_name]),
                            timeout=15.0
                        )
                    finally:
                        sys.stdout = old_stdout
                        sys.stderr = old_stderr
                    
                    # Get captured output
                    stdout_content = captured_output.getvalue()
                    stderr_content = captured_errors.getvalue()
                    all_output = stdout_content + stderr_content
                    
                    self.logger.debug(f"CLI command result: {result}")
                    self.logger.debug(f"CLI captured output: {all_output}")
                    
                    if result is not None:
                        self.logger.info(f"CLI: Successfully added contact '{contact_name}' from device")
                        contact_addition_successful = True
                    else:
                        self.logger.warning(f"CLI: Contact addition command returned no result for '{contact_name}'")
                        
                except Exception as e:
                    self.logger.warning(f"CLI addition failed: {e}")
            
            # Method 3: Try discovery approach as last resort
            if not contact_addition_successful:
                try:
                    self.logger.info(f"Method 3: Attempting addition via discovery...")
                    from meshcore_cli.meshcore_cli import next_cmd
                    
                    result = await asyncio.wait_for(
                        next_cmd(self.bot.meshcore, ["discover_companion_contacts"]),
                        timeout=30.0
                    )
                    
                    if result is not None:
                        self.logger.info("Contact discovery initiated")
                        contact_addition_successful = True
                    else:
                        self.logger.warning("Contact discovery failed")
                        
                except Exception as e:
                    self.logger.warning(f"Discovery addition failed: {e}")
            
            # Log the addition if successful
            if contact_addition_successful:
                self.db_manager.execute_update(
                    'INSERT INTO purging_log (action, details) VALUES (?, ?)',
                    ('contact_addition', f'Added discovered contact: {contact_name} - {reason}')
                )
                self.logger.info(f"Successfully added contact '{contact_name}': {reason}")
                return True
            else:
                self.logger.error(f"Failed to add contact '{contact_name}' - all methods failed")
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
    
    async def populate_missing_geolocation_data(self, dry_run: bool = False, batch_size: int = 10) -> Dict[str, int]:
        """Populate missing geolocation data (state, country) for repeaters that have coordinates but missing location info"""
        try:
            # Check network connectivity first
            if not dry_run:
                try:
                    import socket
                    socket.create_connection(("nominatim.openstreetmap.org", 443), timeout=5)
                except OSError:
                    return {
                        'total_found': 0,
                        'updated': 0,
                        'errors': 1,
                        'skipped': 0,
                        'error': 'No network connectivity to geocoding service'
                    }
            # Find repeaters with valid coordinates but missing state or country
            repeaters_to_update = self.db_manager.execute_query('''
                SELECT id, name, latitude, longitude, city, state, country 
                FROM repeater_contacts 
                WHERE latitude IS NOT NULL 
                AND longitude IS NOT NULL 
                AND NOT (latitude = 0.0 AND longitude = 0.0)
                AND latitude BETWEEN -90 AND 90
                AND longitude BETWEEN -180 AND 180
                AND (state IS NULL OR country IS NULL)
                ORDER BY name
                LIMIT ?
            ''', (batch_size,))
            
            if not repeaters_to_update:
                return {
                    'total_found': 0,
                    'updated': 0,
                    'errors': 0,
                    'skipped': 0
                }
            
            self.logger.info(f"Found {len(repeaters_to_update)} repeaters with missing geolocation data")
            
            updated_count = 0
            error_count = 0
            skipped_count = 0
            
            for repeater in repeaters_to_update:
                repeater_id = repeater['id']
                name = repeater['name']
                latitude = repeater['latitude']
                longitude = repeater['longitude']
                current_city = repeater['city']
                current_state = repeater['state']
                current_country = repeater['country']
                
                try:
                    # Get full location information from coordinates
                    location_info = self._get_full_location_from_coordinates(latitude, longitude)
                    
                    # Check if we got any useful data
                    if not any(location_info.values()):
                        self.logger.debug(f"No location data found for {name} at {latitude}, {longitude}")
                        skipped_count += 1
                        # Still add delay to be respectful to the API
                        await asyncio.sleep(2.0)
                        continue
                    
                    # Determine what needs to be updated
                    updates = []
                    params = []
                    
                    # Update city if we don't have one or if the new one is more detailed
                    if not current_city and location_info['city']:
                        updates.append('city = ?')
                        params.append(location_info['city'])
                    elif current_city and location_info['city'] and len(location_info['city']) > len(current_city):
                        # Update if new city info is more detailed (e.g., includes neighborhood)
                        updates.append('city = ?')
                        params.append(location_info['city'])
                    
                    # Update state if missing
                    if not current_state and location_info['state']:
                        updates.append('state = ?')
                        params.append(location_info['state'])
                    
                    # Update country if missing
                    if not current_country and location_info['country']:
                        updates.append('country = ?')
                        params.append(location_info['country'])
                    
                    if updates:
                        if not dry_run:
                            # Update the database
                            update_query = f"UPDATE repeater_contacts SET {', '.join(updates)} WHERE id = ?"
                            params.append(repeater_id)
                            
                            self.db_manager.execute_update(update_query, tuple(params))
                            
                            self.logger.info(f"Updated geolocation for {name}: {', '.join(updates)}")
                        else:
                            self.logger.info(f"[DRY RUN] Would update {name}: {', '.join(updates)}")
                        
                        updated_count += 1
                    else:
                        self.logger.debug(f"No updates needed for {name}")
                        skipped_count += 1
                    
                    # Add longer delay to avoid overwhelming the geocoding service
                    # Nominatim has a rate limit of 1 request per second, we'll be more conservative
                    await asyncio.sleep(2.0)
                    
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg or "Bandwidth limit exceeded" in error_msg:
                        self.logger.warning(f"Rate limited by geocoding service for {name}. Waiting longer...")
                        # Wait longer if we're rate limited
                        await asyncio.sleep(10.0)
                        error_count += 1
                    elif "No route to host" in error_msg or "Connection" in error_msg:
                        self.logger.warning(f"Network connectivity issue for {name}. Skipping...")
                        # Skip this repeater due to network issues
                        skipped_count += 1
                    else:
                        self.logger.error(f"Error updating geolocation for {name}: {e}")
                        error_count += 1
                    continue
            
            result = {
                'total_found': len(repeaters_to_update),
                'updated': updated_count,
                'errors': error_count,
                'skipped': skipped_count
            }
            
            if not dry_run:
                self.logger.info(f"Geolocation update completed: {updated_count} updated, {error_count} errors, {skipped_count} skipped")
            else:
                self.logger.info(f"Geolocation update dry run completed: {updated_count} would be updated, {error_count} errors, {skipped_count} skipped")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error populating missing geolocation data: {e}")
            return {
                'total_found': 0,
                'updated': 0,
                'errors': 1,
                'skipped': 0,
                'error': str(e)
            }