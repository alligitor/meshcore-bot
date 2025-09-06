#!/usr/bin/env python3
"""
AQI command for the MeshCore Bot
Provides Air Quality Index information using zip codes and AirNow API
"""

import re
import requests
from datetime import datetime
from geopy.geocoders import Nominatim
from .base_command import BaseCommand
from ..models import MeshMessage


class AqiCommand(BaseCommand):
    """Handles AQI commands with zipcode and city support"""
    
    # Plugin metadata
    name = "aqi"
    keywords = ['aqi', 'air', 'airquality', 'air_quality']
    description = "Get Air Quality Index for a zip code, city, or coordinates (usage: aqi 12345, aqi seattle, or aqi 47.6,-122.3)"
    category = "weather"
    cooldown_seconds = 5  # 5 second cooldown per user to prevent API abuse
    
    # Error constants
    ERROR_FETCHING_DATA = "Error fetching AQI data"
    NO_DATA_AVAILABLE = "No AQI data available"
    
    def __init__(self, bot):
        super().__init__(bot)
        self.url_timeout = 10  # seconds
        
        # Per-user cooldown tracking
        self.user_cooldowns = {}  # user_id -> last_execution_time
        
        # Get default state from config for city disambiguation
        self.default_state = self.bot.config.get('Weather', 'default_state', fallback='WA')
        
        # Get AirNow API key from config
        self.api_key = self.bot.config.get('Solar_Config', 'airnow_api_key', fallback='')
        if not self.api_key:
            self.logger.warning("AirNow API key not configured in config.ini")
        
        # Initialize geocoder
        self.geolocator = Nominatim(user_agent="meshcore-bot")
        
        # US boundary coordinates (approximate bounding box)
        self.us_bounds = {
            'min_lat': 24.396308,  # Southern tip of Florida
            'max_lat': 71.538800,  # Northern Alaska
            'min_lon': -179.148909, # Western Alaska (Aleutian Islands)
            'max_lon': -66.885444   # Eastern Maine
        }
        
        # Snarky responses for astronomical objects
        self.astronomical_responses = {
            'sun': "The Sun's AQI is off the charts! Solar wind and coronal mass ejections make Earth's air look pristine. ☀️",
            'moon': "You like breathing regolith? The Moon has no atmosphere, so AQI is technically perfect (if you can breathe vacuum). 🌙",
            'the moon': "You like breathing regolith? The Moon has no atmosphere, so AQI is technically perfect (if you can breathe vacuum). 🌙",
            'mercury': "Mercury's atmosphere is so thin it's practically vacuum. AQI: Perfect, if you can survive 800°F temperature swings. ☿️",
            'venus': "Venus has an atmosphere of 96% CO2 with sulfuric acid clouds. AQI: Hazardous doesn't even begin to describe it. ♀️",
            'earth': "Earth's AQI varies by location. Try a specific city or coordinates! 🌍",
            'mars': "Mars has a thin CO2 atmosphere with dust storms. AQI: Generally good, but those dust storms are brutal. ♂️",
            'jupiter': "Jupiter is a gas giant with no solid surface. AQI: N/A (you'd be crushed by atmospheric pressure first). ♃",
            'saturn': "Saturn's atmosphere is mostly hydrogen and helium. AQI: Perfect, if you can survive the pressure and cold. ♄",
            'uranus': "Uranus has methane in its atmosphere. AQI: Smells like farts, but at least it's not toxic. ♅",
            'neptune': "Neptune's atmosphere has methane and hydrogen sulfide. AQI: Smells like rotten eggs, but you'd freeze first. ♆",
            'pluto': "Pluto's atmosphere is mostly nitrogen with some methane. AQI: Good, but it's so cold your lungs would freeze. ♇",
            'europa': "Europa has a thin oxygen atmosphere. AQI: Excellent, but you'd freeze solid in the vacuum of space. 🌑",
            'titan': "Titan has a thick nitrogen atmosphere with methane. AQI: Breathable, but it's -290°F and rains liquid methane. 🪐",
            'io': "Io has a thin sulfur dioxide atmosphere from volcanic activity. AQI: Toxic, but the radiation would kill you first. 🌋",
            'ganymede': "Ganymede has a thin oxygen atmosphere. AQI: Good, but you'd freeze in the vacuum of space. 🛸",
            'callisto': "Callisto has a thin carbon dioxide atmosphere. AQI: Decent, but it's -220°F and you're in space. ❄️",
            'enceladus': "Enceladus has water vapor from geysers. AQI: Perfect, but you'd freeze instantly in space. 💧",
            'triton': "Triton has a thin nitrogen atmosphere. AQI: Good, but it's -390°F and you're in deep space. 🥶",
            # Bonus fun responses
            'space': "Space has no atmosphere, so AQI is perfect! Just don't forget your spacesuit. 🚀",
            'void': "The void of space has excellent air quality - zero pollutants! Just remember to bring your own air. 🌌",
            'black hole': "Black holes have no atmosphere, but the tidal forces would be a bigger problem than air quality. 🕳️",
            'asteroid': "Asteroids have no atmosphere, so AQI is perfect! Just watch out for the vacuum of space. ☄️",
            'comet': "Comets have thin atmospheres of water vapor and dust. AQI: Variable, but you'd freeze in space anyway. ☄️"
        }
    
    def get_help_text(self) -> str:
        return f"Usage: aqi <zipcode|city|lat,lon> - Get AQI for US zipcode, city in {self.default_state}, or coordinates"
    
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
    
    def is_coordinate_in_us(self, lat: float, lon: float) -> bool:
        """Check if coordinates are within US boundaries"""
        
        # Check Hawaii first (separate from continental US)
        hawaii_bounds = {
            'min_lat': 18.9, 'max_lat': 22.2,
            'min_lon': -162.0, 'max_lon': -154.8
        }
        if (hawaii_bounds['min_lat'] <= lat <= hawaii_bounds['max_lat'] and
            hawaii_bounds['min_lon'] <= lon <= hawaii_bounds['max_lon']):
            return True
        
        # Check Puerto Rico (separate from continental US)
        puerto_rico_bounds = {
            'min_lat': 17.8, 'max_lat': 18.5,
            'min_lon': -67.3, 'max_lon': -65.2
        }
        if (puerto_rico_bounds['min_lat'] <= lat <= puerto_rico_bounds['max_lat'] and
            puerto_rico_bounds['min_lon'] <= lon <= puerto_rico_bounds['max_lon']):
            return True
        
        # Check Alaska (separate from continental US)
        alaska_bounds = {
            'min_lat': 51.0, 'max_lat': 71.5,
            'min_lon': -179.0, 'max_lon': -129.0
        }
        if (alaska_bounds['min_lat'] <= lat <= alaska_bounds['max_lat'] and
            alaska_bounds['min_lon'] <= lon <= alaska_bounds['max_lon']):
            return True
        
        # Continental US bounds (excluding Alaska, Hawaii, Puerto Rico)
        continental_us_bounds = {
            'min_lat': 24.4,   # Southern tip of Florida
            'max_lat': 49.0,   # US-Canada border (49th parallel)
            'min_lon': -125.0, # West coast
            'max_lon': -66.0   # East coast
        }
        
        # Check if coordinates are within continental US bounds
        if not (continental_us_bounds['min_lat'] <= lat <= continental_us_bounds['max_lat']):
            return False
        if not (continental_us_bounds['min_lon'] <= lon <= continental_us_bounds['max_lon']):
            return False
        
        # Additional exclusions for areas that might be in Canada or Mexico
        # Northern border with Canada (above 49th parallel)
        if lat > 49.0:
            return False
        
        # Southern border with Mexico (below 25th parallel, west of -97)
        if lat < 25.0 and lon < -97.0:
            return False
        
        # Great Lakes region - exclude Canadian side
        # Lake Superior area (north of 48.5, between -92 and -84)
        if lat > 48.5 and -92.0 <= lon <= -84.0:
            return False
        
        # Lake Huron area (north of 45.5, between -84 and -79)
        if lat > 45.5 and -84.0 <= lon <= -79.0:
            return False
        
        # Lake Ontario area (north of 44.0, between -79 and -76)
        if lat > 44.0 and -79.0 <= lon <= -76.0:
            return False
        
        # Additional Canadian exclusions
        # Toronto area (around 43.7, -79.4)
        if 43.5 <= lat <= 43.9 and -79.8 <= lon <= -79.0:
            return False
        
        # Montreal area (around 45.5, -73.6)
        if 45.3 <= lat <= 45.7 and -74.0 <= lon <= -73.2:
            return False
        
        # Vancouver area (around 49.3, -123.1)
        if 49.0 <= lat <= 49.5 and -123.5 <= lon <= -122.5:
            return False
        
        return True
    
    def validate_coordinates_with_geocoding(self, lat: float, lon: float) -> tuple:
        """Validate coordinates are in US using both boundary check and geocoding"""
        # First check if coordinates are within US boundaries
        if not self.is_coordinate_in_us(lat, lon):
            return False, f"Coordinates {lat:.3f},{lon:.3f} are outside the United States. AirNow API only supports US locations."
        
        # Additional validation using reverse geocoding
        try:
            # Use reverse geocoding to get location info
            location = self.geolocator.reverse(f"{lat}, {lon}")
            if location:
                address = location.raw.get('address', {})
                country = address.get('country', '').lower()
                country_code = address.get('country_code', '').lower()
                
                # Check if the location is in the US
                if country in ['united states', 'usa', 'us'] or country_code in ['us', 'usa']:
                    return True, None
                else:
                    return False, f"Coordinates {lat:.3f},{lon:.3f} are in {country.title()}. AirNow API only supports US locations."
            else:
                # If geocoding fails but coordinates are within US bounds, allow it
                return True, None
                
        except Exception as e:
            self.logger.warning(f"Error in reverse geocoding for {lat},{lon}: {e}")
            # If geocoding fails but coordinates are within US bounds, allow it
            return True, None
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the AQI command"""
        content = message.content.strip()
        
        # Parse the command to extract location
        # Support formats: "aqi 12345", "aqi seattle", "aqi paris, tx", "aqi 47.6,-122.3", "air everett"
        parts = content.split()
        if len(parts) < 2:
            await self.send_response(message, f"Usage: aqi <zipcode|city|lat,lon> - Example: aqi 12345 or aqi seattle or aqi 47.6,-122.3")
            return True
        
        # Join all parts after the command to handle "city, state" format
        location = ' '.join(parts[1:]).strip()
        
        # Check for astronomical objects first
        location_lower = location.lower()
        if location_lower in self.astronomical_responses:
            await self.send_response(message, self.astronomical_responses[location_lower])
            return True
        
        # Check if it's a zipcode (5 digits)
        if re.match(r'^\d{5}$', location):
            location_type = "zipcode"
        # Check if it's lat,lon coordinates (decimal numbers separated by comma)
        elif re.match(r'^-?\d+\.?\d*,-?\d+\.?\d*$', location):
            location_type = "coordinates"
        else:
            # It's a city name (possibly with state)
            location_type = "city"
        
        try:
            # Record execution for this user
            self._record_execution(message.sender_id)
            
            # Get AQI data for the location
            aqi_data = await self.get_aqi_for_location(location, location_type)
            
            # Send the response
            await self.send_response(message, aqi_data)
            return True
            
        except Exception as e:
            self.logger.error(f"Error in AQI command: {e}")
            await self.send_response(message, f"Error getting AQI data: {e}")
            return True
    
    async def get_aqi_for_location(self, location: str, location_type: str) -> str:
        """Get AQI data for a location (zipcode, city, or coordinates)"""
        try:
            if not self.api_key:
                return "AirNow API key not configured. Please add airnow_api_key to config.ini"
            
            # Convert location to lat/lon
            if location_type == "zipcode":
                lat, lon = self.zipcode_to_lat_lon(location)
                if lat is None or lon is None:
                    return f"Could not find location for zipcode {location}"
                address_info = None
            elif location_type == "coordinates":
                # Parse lat,lon coordinates
                try:
                    lat_str, lon_str = location.split(',')
                    lat = float(lat_str.strip())
                    lon = float(lon_str.strip())
                    
                    # Validate coordinate ranges
                    if not (-90 <= lat <= 90):
                        return f"Invalid latitude: {lat}. Must be between -90 and 90."
                    if not (-180 <= lon <= 180):
                        return f"Invalid longitude: {lon}. Must be between -180 and 180."
                    
                    # Validate coordinates are in US
                    is_valid, error_msg = self.validate_coordinates_with_geocoding(lat, lon)
                    if not is_valid:
                        return error_msg
                    
                    address_info = None
                except ValueError:
                    return f"Invalid coordinates format: {location}. Use format: lat,lon (e.g., 47.6,-122.3)"
            else:  # city
                result = self.city_to_lat_lon(location)
                if len(result) == 3:
                    lat, lon, address_info = result
                else:
                    lat, lon = result
                    address_info = None
                
                if lat is None or lon is None:
                    return f"Could not find city '{location}' in {self.default_state}"
                
                # Check if the found city is in a different state than default
                actual_city = location
                actual_state = self.default_state
                if address_info:
                    # Try to get the best city name from various address fields
                    actual_city = (address_info.get('city') or 
                                 address_info.get('town') or 
                                 address_info.get('village') or 
                                 address_info.get('hamlet') or 
                                 address_info.get('municipality') or 
                                 location)
                    actual_state = address_info.get('state', self.default_state)
                    # Convert full state name to abbreviation if needed
                    if len(actual_state) > 2:
                        state_abbrev_map = {
                            'Washington': 'WA', 'California': 'CA', 'New York': 'NY', 'Texas': 'TX',
                            'Florida': 'FL', 'Illinois': 'IL', 'Pennsylvania': 'PA', 'Ohio': 'OH',
                            'Georgia': 'GA', 'North Carolina': 'NC', 'Michigan': 'MI', 'New Jersey': 'NJ',
                            'Virginia': 'VA', 'Tennessee': 'TN', 'Indiana': 'IN', 'Arizona': 'AZ',
                            'Massachusetts': 'MA', 'Missouri': 'MO', 'Maryland': 'MD', 'Wisconsin': 'WI',
                            'Colorado': 'CO', 'Minnesota': 'MN', 'South Carolina': 'SC', 'Alabama': 'AL',
                            'Louisiana': 'LA', 'Kentucky': 'KY', 'Oregon': 'OR', 'Oklahoma': 'OK',
                            'Connecticut': 'CT', 'Utah': 'UT', 'Iowa': 'IA', 'Nevada': 'NV',
                            'Arkansas': 'AR', 'Mississippi': 'MS', 'Kansas': 'KS', 'New Mexico': 'NM',
                            'Nebraska': 'NE', 'West Virginia': 'WV', 'Idaho': 'ID', 'Hawaii': 'HI',
                            'New Hampshire': 'NH', 'Maine': 'ME', 'Montana': 'MT', 'Rhode Island': 'RI',
                            'Delaware': 'DE', 'South Dakota': 'SD', 'North Dakota': 'ND', 'Alaska': 'AK',
                            'Vermont': 'VT', 'Wyoming': 'WY'
                        }
                        actual_state = state_abbrev_map.get(actual_state, actual_state)
                    
                    # Also check if the default state needs to be converted for comparison
                    default_state_full = self.default_state
                    if len(self.default_state) == 2:
                        # Convert abbreviation to full name for comparison
                        abbrev_to_full_map = {v: k for k, v in state_abbrev_map.items()}
                        default_state_full = abbrev_to_full_map.get(self.default_state, self.default_state)
            
            # Get AQI forecast - use zipcode API if available, otherwise lat/lon
            if location_type == "zipcode":
                aqi_data = self.get_airnow_aqi_by_zipcode(location)
            else:
                # Use lat/lon API for both city and coordinates
                aqi_data = self.get_airnow_aqi(lat, lon)
            
            if aqi_data == self.ERROR_FETCHING_DATA:
                return "Error fetching AQI data from AirNow"
            
            # Add location info if city is in a different state than default, or for coordinates
            location_prefix = ""
            if location_type == "city" and address_info:
                # Compare states (handle both full names and abbreviations)
                states_different = (actual_state != self.default_state and 
                                  actual_state != default_state_full)
                if states_different:
                    location_prefix = f"{actual_city}, {actual_state}: "
            elif location_type == "coordinates":
                # Add coordinate info for clarity
                location_prefix = f"{lat:.3f},{lon:.3f}: "
            
            return f"{location_prefix}{aqi_data}"
            
        except Exception as e:
            self.logger.error(f"Error getting AQI for {location_type} {location}: {e}")
            return f"Error getting AQI data: {e}"
    
    def zipcode_to_lat_lon(self, zipcode: str) -> tuple:
        """Convert zipcode to latitude and longitude"""
        try:
            # Use Nominatim to geocode the zipcode
            location = self.geolocator.geocode(f"{zipcode}, USA")
            if location:
                return location.latitude, location.longitude
            else:
                return None, None
        except Exception as e:
            self.logger.error(f"Error geocoding zipcode {zipcode}: {e}")
            return None, None
    
    def city_to_lat_lon(self, city: str) -> tuple:
        """Convert city name to latitude and longitude using default state"""
        try:
            # Check if the input contains a comma (city, state format)
            if ',' in city:
                # Parse city, state format
                city_parts = [part.strip() for part in city.split(',')]
                if len(city_parts) >= 2:
                    city_name = city_parts[0]
                    state = city_parts[1]
                    
                    # Try the specific city, state combination first
                    location = self.geolocator.geocode(f"{city_name}, {state}, USA")
                    if location:
                        # Use reverse geocoding to get detailed address info
                        try:
                            reverse_location = self.geolocator.reverse(f"{location.latitude}, {location.longitude}")
                            if reverse_location:
                                return location.latitude, location.longitude, reverse_location.raw.get('address', {})
                        except:
                            pass
                        return location.latitude, location.longitude, location.raw.get('address', {})
            
            # For common city names, try major cities first to avoid small towns
            major_city_mappings = {
                'albany': ['Albany, NY, USA', 'Albany, OR, USA', 'Albany, CA, USA'],
                'portland': ['Portland, OR, USA', 'Portland, ME, USA'],
                'boston': ['Boston, MA, USA'],
                'paris': ['Paris, TX, USA', 'Paris, IL, USA', 'Paris, TN, USA'],
                'springfield': ['Springfield, IL, USA', 'Springfield, MO, USA', 'Springfield, MA, USA'],
                'franklin': ['Franklin, TN, USA', 'Franklin, MA, USA'],
                'georgetown': ['Georgetown, TX, USA', 'Georgetown, SC, USA'],
                'madison': ['Madison, WI, USA', 'Madison, AL, USA'],
                'auburn': ['Auburn, AL, USA', 'Auburn, WA, USA'],
                'troy': ['Troy, NY, USA', 'Troy, MI, USA'],
                'clinton': ['Clinton, IA, USA', 'Clinton, MS, USA'],
                # Major US cities that should be unambiguous
                'los angeles': ['Los Angeles, CA, USA'],
                'new york': ['New York, NY, USA'],
                'chicago': ['Chicago, IL, USA'],
                'houston': ['Houston, TX, USA'],
                'phoenix': ['Phoenix, AZ, USA'],
                'philadelphia': ['Philadelphia, PA, USA'],
                'san antonio': ['San Antonio, TX, USA'],
                'san diego': ['San Diego, CA, USA'],
                'dallas': ['Dallas, TX, USA'],
                'san jose': ['San Jose, CA, USA'],
                'austin': ['Austin, TX, USA'],
                'jacksonville': ['Jacksonville, FL, USA'],
                'fort worth': ['Fort Worth, TX, USA'],
                'columbus': ['Columbus, OH, USA'],
                'charlotte': ['Charlotte, NC, USA'],
                'san francisco': ['San Francisco, CA, USA'],
                'indianapolis': ['Indianapolis, IN, USA'],
                'seattle': ['Seattle, WA, USA'],
                'denver': ['Denver, CO, USA'],
                'washington': ['Washington, DC, USA'],
                'boston': ['Boston, MA, USA'],
                'el paso': ['El Paso, TX, USA'],
                'nashville': ['Nashville, TN, USA'],
                'detroit': ['Detroit, MI, USA'],
                'oklahoma city': ['Oklahoma City, OK, USA'],
                'portland': ['Portland, OR, USA', 'Portland, ME, USA'],
                'las vegas': ['Las Vegas, NV, USA'],
                'memphis': ['Memphis, TN, USA'],
                'louisville': ['Louisville, KY, USA'],
                'baltimore': ['Baltimore, MD, USA'],
                'milwaukee': ['Milwaukee, WI, USA'],
                'albuquerque': ['Albuquerque, NM, USA'],
                'tucson': ['Tucson, AZ, USA'],
                'fresno': ['Fresno, CA, USA'],
                'sacramento': ['Sacramento, CA, USA'],
                'mesa': ['Mesa, AZ, USA'],
                'kansas city': ['Kansas City, MO, USA'],
                'atlanta': ['Atlanta, GA, USA'],
                'long beach': ['Long Beach, CA, USA'],
                'colorado springs': ['Colorado Springs, CO, USA'],
                'raleigh': ['Raleigh, NC, USA'],
                'miami': ['Miami, FL, USA'],
                'virginia beach': ['Virginia Beach, VA, USA'],
                'omaha': ['Omaha, NE, USA'],
                'oakland': ['Oakland, CA, USA'],
                'minneapolis': ['Minneapolis, MN, USA'],
                'tulsa': ['Tulsa, OK, USA'],
                'arlington': ['Arlington, TX, USA'],
                'tampa': ['Tampa, FL, USA'],
                'new orleans': ['New Orleans, LA, USA']
            }
            
            # If it's a major city with multiple locations, try the major ones first
            if city.lower() in major_city_mappings:
                for major_city_query in major_city_mappings[city.lower()]:
                    location = self.geolocator.geocode(major_city_query)
                    if location:
                        # Use reverse geocoding to get detailed address info
                        try:
                            reverse_location = self.geolocator.reverse(f"{location.latitude}, {location.longitude}")
                            if reverse_location:
                                return location.latitude, location.longitude, reverse_location.raw.get('address', {})
                        except:
                            pass
                        return location.latitude, location.longitude, location.raw.get('address', {})
            
            # First try with default state
            location = self.geolocator.geocode(f"{city}, {self.default_state}, USA")
            if location:
                # Use reverse geocoding to get detailed address info
                try:
                    reverse_location = self.geolocator.reverse(f"{location.latitude}, {location.longitude}")
                    if reverse_location:
                        return location.latitude, location.longitude, reverse_location.raw.get('address', {})
                except:
                    pass
                return location.latitude, location.longitude, location.raw.get('address', {})
            else:
                # Try without state as fallback
                location = self.geolocator.geocode(f"{city}, USA")
                if location:
                    # Use reverse geocoding to get detailed address info
                    try:
                        reverse_location = self.geolocator.reverse(f"{location.latitude}, {location.longitude}")
                        if reverse_location:
                            return location.latitude, location.longitude, reverse_location.raw.get('address', {})
                    except:
                        pass
                    return location.latitude, location.longitude, location.raw.get('address', {})
                else:
                    return None, None, None
        except Exception as e:
            self.logger.error(f"Error geocoding city {city}: {e}")
            return None, None, None
    
    def get_airnow_aqi(self, lat: float, lon: float) -> str:
        """Get AQI forecast from AirNow API"""
        try:
            # Get current date for the forecast
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Try with increasing distance radii if no data found
            distances = [25, 50, 100]
            
            for distance in distances:
                # Build the API URL for lat/long
                api_url = f"https://www.airnowapi.org/aq/forecast/latLong/"
                params = {
                    'format': 'text/csv',  # Use CSV format for more reliable parsing
                    'latitude': lat,
                    'longitude': lon,
                    'date': today,
                    'distance': distance,
                    'API_KEY': self.api_key
                }
                
                # Make the API request
                response = requests.get(api_url, params=params, timeout=self.url_timeout)
                if not response.ok:
                    self.logger.warning(f"Error fetching AQI data from AirNow: {response.status_code}")
                    return self.ERROR_FETCHING_DATA
                
                # Parse CSV response
                csv_data = response.text.strip()
                if not csv_data:
                    continue
                
                # Parse the CSV data
                aqi_info = self.parse_csv_aqi_data(csv_data)
                
                # If we found data, return it
                if aqi_info != self.NO_DATA_AVAILABLE and "No AQI monitoring stations" not in aqi_info:
                    return aqi_info
                
                # If this was the last distance to try, return the result
                if distance == distances[-1]:
                    return aqi_info
            
            return self.NO_DATA_AVAILABLE
            
        except Exception as e:
            self.logger.error(f"Error fetching AirNow AQI: {e}")
            return self.ERROR_FETCHING_DATA
    
    def get_airnow_aqi_by_zipcode(self, zipcode: str) -> str:
        """Get AQI forecast from AirNow API using zipcode"""
        try:
            # Get current date for the forecast
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Build the API URL for zipcode
            api_url = f"https://www.airnowapi.org/aq/forecast/zipCode/"
            params = {
                'format': 'text/csv',  # Use CSV format for more reliable parsing
                'zipCode': zipcode,
                'date': today,
                'distance': 25,  # 25 mile radius
                'API_KEY': self.api_key
            }
            
            # Make the API request
            response = requests.get(api_url, params=params, timeout=self.url_timeout)
            if not response.ok:
                self.logger.warning(f"Error fetching AQI data from AirNow: {response.status_code}")
                return self.ERROR_FETCHING_DATA
            
            # Parse CSV response
            csv_data = response.text.strip()
            if not csv_data:
                return self.NO_DATA_AVAILABLE
            
            # Parse the CSV data
            aqi_info = self.parse_csv_aqi_data(csv_data)
            return aqi_info
            
        except Exception as e:
            self.logger.error(f"Error fetching AirNow AQI: {e}")
            return self.ERROR_FETCHING_DATA
    
    def parse_csv_aqi_data(self, csv_data: str) -> str:
        """Parse AirNow CSV response and format for display"""
        try:
            import csv
            from io import StringIO
            
            if not csv_data:
                return self.NO_DATA_AVAILABLE
            
            # Parse CSV data
            csv_reader = csv.DictReader(StringIO(csv_data))
            rows = list(csv_reader)
            
            if not rows:
                # Check if we have headers but no data (remote location)
                if csv_data.strip() and 'DateIssue' in csv_data and 'ReportingArea' in csv_data:
                    return "No AQI monitoring stations within 100 miles of this location"
                return self.NO_DATA_AVAILABLE
            
            # Group by reporting area
            areas = {}
            for row in rows:
                area = row.get('ReportingArea', 'Unknown')
                if area not in areas:
                    areas[area] = []
                areas[area].append(row)
            
            # Format the response
            aqi_parts = []
            
            for area, items in areas.items():
                # Get the primary pollutant (usually PM2.5 or Ozone)
                primary_item = None
                for item in items:
                    param = item.get('ParameterName', '')
                    if param in ['PM2.5', 'Ozone', 'PM10']:
                        primary_item = item
                        break
                
                # If no primary pollutant found, use the first item
                if not primary_item:
                    primary_item = items[0]
                
                # Extract key information
                aqi = primary_item.get('AQI', '')
                category = primary_item.get('CategoryName', 'Unknown')
                parameter = primary_item.get('ParameterName', 'Unknown')
                state = primary_item.get('StateCode', '')
                
                # Get emoji for AQI category
                aqi_emoji = self.get_aqi_emoji(category)
                
                # Format the area name
                area_display = area
                if state and state != 'Unknown':
                    area_display = f"{area}, {state}"
                
                # Format AQI value
                if not aqi or aqi == '-1':
                    aqi_display = "N/A"
                else:
                    aqi_display = str(aqi)
                
                # Create compact AQI string
                aqi_str = f"{area_display}: {aqi_emoji} {aqi_display} ({category})"
                if parameter != 'Unknown':
                    aqi_str += f" {parameter}"
                
                aqi_parts.append(aqi_str)
            
            # Join all areas
            if len(aqi_parts) == 1:
                return aqi_parts[0]
            else:
                return " | ".join(aqi_parts)
            
        except Exception as e:
            self.logger.error(f"Error parsing CSV AQI data: {e}")
            return "Error parsing AQI data"
    
    def parse_aqi_data(self, data: list) -> str:
        """Parse AirNow API response and format for display"""
        try:
            if not data:
                return self.NO_DATA_AVAILABLE
            
            # Group by reporting area
            areas = {}
            for item in data:
                area = item.get('ReportingArea', 'Unknown')
                if area not in areas:
                    areas[area] = []
                areas[area].append(item)
            
            # Format the response
            aqi_parts = []
            
            for area, items in areas.items():
                # Get the primary pollutant (usually PM2.5 or Ozone)
                primary_item = None
                for item in items:
                    param = item.get('ParameterName', '')
                    if param in ['PM2.5', 'Ozone', 'PM10']:
                        primary_item = item
                        break
                
                # If no primary pollutant found, use the first item
                if not primary_item:
                    primary_item = items[0]
                
                # Extract key information
                aqi = primary_item.get('AQI', -1)
                category_info = primary_item.get('Category', {})
                category = category_info.get('Name', 'Unknown') if isinstance(category_info, dict) else 'Unknown'
                parameter = primary_item.get('ParameterName', 'Unknown')
                state = primary_item.get('StateCode', '')
                
                # Get emoji for AQI category
                aqi_emoji = self.get_aqi_emoji(category)
                
                # Format the area name
                area_display = area
                if state and state != 'Unknown':
                    area_display = f"{area}, {state}"
                
                # Format AQI value
                if aqi == -1:
                    aqi_display = "N/A"
                else:
                    aqi_display = str(aqi)
                
                # Create compact AQI string
                aqi_str = f"{area_display}: {aqi_emoji}{aqi_display} ({category})"
                if parameter != 'Unknown':
                    aqi_str += f" {parameter}"
                
                aqi_parts.append(aqi_str)
            
            # Join all areas
            if len(aqi_parts) == 1:
                return aqi_parts[0]
            else:
                return " | ".join(aqi_parts)
            
        except Exception as e:
            self.logger.error(f"Error parsing AQI data: {e}")
            return "Error parsing AQI data"
    
    def get_aqi_emoji(self, category: str) -> str:
        """Get emoji for AQI category"""
        if not category:
            return "🌫️"
        
        category_lower = category.lower()
        
        # AQI category emojis
        if 'good' in category_lower:
            return "🟢"
        elif 'moderate' in category_lower:
            return "🟡"
        elif 'unhealthy for sensitive groups' in category_lower:
            return "🟠"
        elif 'unhealthy' in category_lower:
            return "🔴"
        elif 'very unhealthy' in category_lower:
            return "🟣"
        elif 'hazardous' in category_lower:
            return "🟤"
        else:
            return "🌫️"  # Default air quality emoji
