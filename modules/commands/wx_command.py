#!/usr/bin/env python3
"""
Weather command for the MeshCore Bot
Provides weather information using zip codes and NOAA APIs
"""

import re
import json
import requests
import xml.dom.minidom
from datetime import datetime
from geopy.geocoders import Nominatim
import maidenhead as mh
from .base_command import BaseCommand
from ..models import MeshMessage


class WxCommand(BaseCommand):
    """Handles weather commands with zipcode support"""
    
    # Plugin metadata
    name = "wx"
    keywords = ['wx', 'weather', 'wxa', 'wxalert']
    description = "Get weather information for a zip code (usage: wx 12345)"
    category = "weather"
    cooldown_seconds = 5  # 5 second cooldown per user to prevent API abuse
    
    # Error constants
    NO_DATA_NOGPS = "No GPS data available"
    ERROR_FETCHING_DATA = "Error fetching weather data"
    NO_ALERTS = "No weather alerts"
    
    def __init__(self, bot):
        super().__init__(bot)
        self.url_timeout = 10  # seconds
        self.forecast_duration = 3  # days
        self.num_wx_alerts = 2  # number of alerts to show
        self.use_metric = False  # Use imperial units by default
        self.zulu_time = False  # Use local time by default
        
        # Per-user cooldown tracking
        self.user_cooldowns = {}  # user_id -> last_execution_time
        
        # Get default state from config for city disambiguation
        self.default_state = self.bot.config.get('Weather', 'default_state', fallback='WA')
        
        # Initialize geocoder
        self.geolocator = Nominatim(user_agent="meshcore-bot")
    
    def get_help_text(self) -> str:
        return f"Usage: wx <zipcode|city> - Get weather for US zipcode or city in {self.default_state}"
    
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
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the weather command"""
        content = message.content.strip()
        
        # Parse the command to extract location
        # Support formats: "wx 12345", "wx seattle", "weather everett", "wxa bellingham"
        parts = content.split()
        if len(parts) < 2:
            await self.send_response(message, f"Usage: wx <zipcode|city> - Example: wx 12345 or wx seattle")
            return True
        
        location = parts[1].strip()
        
        # Check if it's a zipcode (5 digits) or city name
        if re.match(r'^\d{5}$', location):
            # It's a zipcode
            location_type = "zipcode"
        else:
            # It's a city name
            location_type = "city"
        
        try:
            # Record execution for this user
            self._record_execution(message.sender_id)
            
            # Get weather data for the location
            weather_data = await self.get_weather_for_location(location, location_type)
            
            # Check if we need to send multiple messages
            if isinstance(weather_data, tuple) and weather_data[0] == "multi_message":
                # Send weather data first
                await self.send_response(message, weather_data[1])
                
                # Wait for bot TX rate limiter to allow next message
                import asyncio
                rate_limit = self.bot.config.getfloat('Bot', 'bot_tx_rate_limit_seconds', fallback=1.0)
                await asyncio.sleep(rate_limit + 0.2)  # Wait longer than the configured rate limit to avoid rate limiting
                
                # Send the special weather statement
                alert_text = weather_data[2]
                alert_count = weather_data[3]
                await self.send_response(message, f"{alert_count} alerts: {alert_text}")
            else:
                # Send single message as usual
                await self.send_response(message, weather_data)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in weather command: {e}")
            await self.send_response(message, f"Error getting weather data: {e}")
            return True
    
    async def get_weather_for_location(self, location: str, location_type: str) -> str:
        """Get weather data for a location (zipcode or city)"""
        try:
            # Convert location to lat/lon
            if location_type == "zipcode":
                lat, lon = self.zipcode_to_lat_lon(location)
                if lat is None or lon is None:
                    return f"Could not find location for zipcode {location}"
            else:  # city
                lat, lon = self.city_to_lat_lon(location)
                if lat is None or lon is None:
                    return f"Could not find city '{location}' in {self.default_state}"
            
            # Get weather forecast
            weather = self.get_noaa_weather(lat, lon)
            if weather == self.ERROR_FETCHING_DATA:
                return "Error fetching weather data from NOAA"
            
            # Try to get additional current conditions data
            current_conditions = self.get_current_conditions(lat, lon)
            if current_conditions and len(weather) < 120:
                weather = f"{weather} {current_conditions}"
            
            # Get weather alerts
            alerts_result = self.get_weather_alerts_noaa(lat, lon)
            if alerts_result == self.ERROR_FETCHING_DATA:
                alerts_info = None
            elif alerts_result == self.NO_ALERTS:
                alerts_info = None
            else:
                full_alert_text, abbreviated_alert_text, alert_count = alerts_result
                if alert_count > 0:
                    # Check if this is a special weather statement that needs two messages
                    self.logger.debug(f"Checking if alert is special: '{full_alert_text}'")
                    if self.is_special_weather_statement(full_alert_text):
                        self.logger.info(f"Special weather statement detected: '{full_alert_text}' - using multi-message mode")
                        # Return a tuple indicating we need to send two messages
                        # Don't truncate the alert text for special statements
                        return ("multi_message", weather, full_alert_text, alert_count)
                    else:
                        self.logger.debug(f"Regular alert detected: '{full_alert_text}' - using single message mode")
                    
                    # For regular alerts, use the already abbreviated text and apply truncation for single message
                    alert_text_for_single_message = self.truncate_alert_for_lora(abbreviated_alert_text, max_length=80)
                    
                    # Combine weather and alerts more compactly
                    combined = f"{weather} | {alert_count} alerts: {alert_text_for_single_message}"
                    if len(combined) > 120:
                        # If still too long, prioritize alerts only
                        weather = f"{alert_count} alerts: {alert_text_for_single_message}"
                    else:
                        weather = combined
            
            return weather
            
        except Exception as e:
            self.logger.error(f"Error getting weather for {location_type} {location}: {e}")
            return f"Error getting weather data: {e}"
    
    async def get_weather_for_zipcode(self, zipcode: str) -> str:
        """Get weather data for a specific zipcode (legacy method)"""
        return await self.get_weather_for_location(zipcode, "zipcode")
    
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
            # Use Nominatim to geocode the city with default state
            location = self.geolocator.geocode(f"{city}, {self.default_state}, USA")
            if location:
                return location.latitude, location.longitude
            else:
                # Try without state as fallback
                location = self.geolocator.geocode(f"{city}, USA")
                if location:
                    return location.latitude, location.longitude
                else:
                    return None, None
        except Exception as e:
            self.logger.error(f"Error geocoding city {city}: {e}")
            return None, None
    
    def get_noaa_weather(self, lat: float, lon: float) -> str:
        """Get weather forecast from NOAA"""
        try:
            # Get weather data from NOAA
            weather_api = f"https://api.weather.gov/points/{lat},{lon}"
            
            # Get the forecast URL
            weather_data = requests.get(weather_api, timeout=self.url_timeout)
            if not weather_data.ok:
                self.logger.warning("Error fetching weather data from NOAA")
                return self.ERROR_FETCHING_DATA
            
            weather_json = weather_data.json()
            forecast_url = weather_json['properties']['forecast']
            
            # Get the forecast
            forecast_data = requests.get(forecast_url, timeout=self.url_timeout)
            if not forecast_data.ok:
                self.logger.warning("Error fetching weather forecast from NOAA")
                return self.ERROR_FETCHING_DATA
            
            forecast_json = forecast_data.json()
            forecast = forecast_json['properties']['periods']
            
            # Format the forecast - focus on current conditions and key info
            if not forecast:
                return "No forecast data available"
            
            current = forecast[0]
            day_name = self.abbreviate_noaa(current['name'])
            temp = current.get('temperature', 'N/A')
            temp_unit = current.get('temperatureUnit', 'F')
            short_forecast = current.get('shortForecast', 'Unknown')
            wind_speed = current.get('windSpeed', '')
            wind_direction = current.get('windDirection', '')
            detailed_forecast = current.get('detailedForecast', '')
            
            # Extract additional useful info from detailed forecast
            humidity = self.extract_humidity(detailed_forecast)
            precip_chance = self.extract_precip_chance(detailed_forecast)
            
            # Create compact but complete weather string with emoji
            weather_emoji = self.get_weather_emoji(short_forecast)
            weather = f"{day_name}: {weather_emoji}{short_forecast} {temp}°{temp_unit}"
            
            # Add wind info if available
            if wind_speed and wind_direction:
                import re
                wind_match = re.search(r'(\d+)', wind_speed)
                if wind_match:
                    wind_num = wind_match.group(1)
                    wind_dir = self.abbreviate_wind_direction(wind_direction)
                    if wind_dir:
                        weather += f" {wind_dir}{wind_num}"
            
            # Add humidity if available and space allows
            if humidity and len(weather) < 90:
                weather += f" {humidity}%RH"
            
            # Add precipitation chance if available and space allows
            if precip_chance and len(weather) < 100:
                weather += f" 🌦️{precip_chance}%"
            
            # Add UV index if available and space allows
            uv_index = self.extract_uv_index(detailed_forecast)
            if uv_index and len(weather) < 110:
                weather += f" UV{uv_index}"
            
            # Add dew point if available and space allows
            dew_point = self.extract_dew_point(detailed_forecast)
            if dew_point and len(weather) < 120:
                weather += f" 💧{dew_point}°"
            
            # Add visibility if available and space allows
            visibility = self.extract_visibility(detailed_forecast)
            if visibility and len(weather) < 130:
                weather += f" 👁️{visibility}mi"
            
            # Add precipitation probability if available and space allows
            precip_prob = self.extract_precip_probability(detailed_forecast)
            if precip_prob and len(weather) < 140:
                weather += f" 🌦️{precip_prob}%"
            
            # Add wind gusts if available and space allows
            wind_gusts = self.extract_wind_gusts(detailed_forecast)
            if wind_gusts and len(weather) < 140:
                weather += f" 💨{wind_gusts}"
            
            # Add tomorrow with high/low if available
            if len(forecast) > 1:
                tomorrow = forecast[1]
                tomorrow_temp = tomorrow.get('temperature', '')
                tomorrow_short = tomorrow.get('shortForecast', '')
                tomorrow_detailed = tomorrow.get('detailedForecast', '')
                tomorrow_wind_speed = tomorrow.get('windSpeed', '')
                tomorrow_wind_direction = tomorrow.get('windDirection', '')
                
                if tomorrow_temp and tomorrow_short:
                    # Try to get high/low for tomorrow
                    tomorrow_high_low = self.extract_high_low(tomorrow_detailed)
                    
                    tomorrow_emoji = self.get_weather_emoji(tomorrow_short)
                    if tomorrow_high_low:
                        tomorrow_str = f" | Tmrw: {tomorrow_emoji}{tomorrow_short} {tomorrow_high_low}"
                    else:
                        tomorrow_str = f" | Tmrw: {tomorrow_emoji}{tomorrow_short} {tomorrow_temp}°"
                    
                    # Add tomorrow wind info if space allows
                    if tomorrow_wind_speed and tomorrow_wind_direction and len(weather + tomorrow_str) < 120:
                        import re
                        wind_match = re.search(r'(\d+)', tomorrow_wind_speed)
                        if wind_match:
                            wind_num = wind_match.group(1)
                            wind_dir = self.abbreviate_wind_direction(tomorrow_wind_direction)
                            if wind_dir:
                                wind_info = f" {wind_dir}{wind_num}"
                                if len(weather + tomorrow_str + wind_info) <= 130:
                                    tomorrow_str += wind_info
                    
                    # Only add if we have space
                    if len(weather + tomorrow_str) <= 130:  # Leave room for alerts
                        weather += tomorrow_str
            
            return weather
            
        except Exception as e:
            self.logger.error(f"Error fetching NOAA weather: {e}")
            return self.ERROR_FETCHING_DATA
    
    def get_weather_alerts_noaa(self, lat: float, lon: float) -> tuple:
        """Get weather alerts from NOAA"""
        try:
            alert_url = f"https://api.weather.gov/alerts/active.atom?point={lat},{lon}"
            
            alert_data = requests.get(alert_url, timeout=self.url_timeout)
            if not alert_data.ok:
                self.logger.warning("Error fetching weather alerts from NOAA")
                return self.ERROR_FETCHING_DATA
            
            full_alert_titles = []  # Store original full titles
            abbreviated_alert_titles = []  # Store abbreviated titles for single message mode
            alertxml = xml.dom.minidom.parseString(alert_data.text)
            
            for i in alertxml.getElementsByTagName("entry"):
                title = i.getElementsByTagName("title")[0].childNodes[0].nodeValue
                full_alert_titles.append(title)
                
                # Abbreviate alert title for brevity (for single message mode)
                short_title = self.abbreviate_alert_title(title)
                abbreviated_alert_titles.append(short_title)
            
            if not full_alert_titles:
                return self.NO_ALERTS
            
            alert_num = len(full_alert_titles)
            
            # For multi-message, we need the full first alert title
            full_first_alert_text = full_alert_titles[0]
            
            # For single message, we need the abbreviated first alert title, further abbreviated by abbreviate_noaa
            abbreviated_first_alert_text = self.abbreviate_noaa(abbreviated_alert_titles[0])
            
            # Return both full and abbreviated versions, along with count
            return full_first_alert_text, abbreviated_first_alert_text, alert_num
            
        except Exception as e:
            self.logger.error(f"Error fetching NOAA weather alerts: {e}")
            return self.ERROR_FETCHING_DATA
    
    def truncate_alert_for_lora(self, alert_text: str, max_length: int = 60) -> str:
        """Truncate alert text intelligently for LoRa message limits"""
        if len(alert_text) <= max_length:
            return alert_text
        
        # Try to truncate at word boundaries
        truncated = alert_text[:max_length-3]
        last_space = truncated.rfind(' ')
        
        if last_space > max_length * 0.7:  # If we can find a good word boundary
            return truncated[:last_space] + "..."
        else:
            return truncated + "..."
    
    def is_special_weather_statement(self, alert_text: str) -> bool:
        """Check if this is a special weather statement that should be sent in a separate message"""
        # Special weather statements are typically longer and more detailed
        # They often contain important information that shouldn't be truncated
        
        # Check for special weather statement keywords (both full and abbreviated forms)
        special_keywords = [
            "special weather statement",
            "special weather stmt",
            "hazardous weather outlook",
            "hydrologic outlook",
            "fire weather watch",
            "red flag warning",
            "excessive heat warning",
            "extreme heat warning",
            # Abbreviated forms
            "extheat warning",
            "extheat warn",
            "exheat warning", 
            "exheat warn",
            "redflag warning",
            "redflag warn",
            "firewx watch",
            "firewx warning"
        ]
        
        alert_lower = alert_text.lower()
        
        # Check if it contains any special keywords
        for keyword in special_keywords:
            if keyword in alert_lower:
                self.logger.debug(f"Special keyword '{keyword}' found in alert: '{alert_text}'")
                return True
        
        # Also check if the alert is particularly long (likely to be truncated)
        # Special statements are often 100+ characters
        if len(alert_text) > 100:
            return True
        
        return False
    
    def abbreviate_alert_title(self, title: str) -> str:
        """Abbreviate alert title for brevity"""
        # Common alert type abbreviations
        replacements = {
            "warning": "Warn",
            "watch": "Watch", 
            "advisory": "Adv",
            "statement": "Stmt",
            "severe thunderstorm": "SvrT-Storm",
            "tornado": "Tornado",
            "flash flood": "FlashFlood",
            "flood": "Flood",
            "winter storm": "WinterStorm",
            "blizzard": "Blizzard",
            "ice storm": "IceStorm",
            "freeze": "Freeze",
            "frost": "Frost",
            "heat": "Heat",
            "excessive heat": "ExHeat",
            "extreme heat": "ExtHeat",
            "wind": "Wind",
            "high wind": "HighWind",
            "wind advisory": "WindAdv",
            "fire weather": "FireWx",
            "red flag": "RedFlag",
            "dense fog": "DenseFog",
            "issued": "iss",
            "until": "til",
            "effective": "eff",
            "expires": "exp",
            "dense smoke": "DenseSmoke",
            "air quality": "AirQuality",
            "coastal flood": "CoastalFlood",
            "lakeshore flood": "LakeshoreFlood",
            "rip current": "RipCurrent",
            "high surf": "HighSurf",
            "hurricane": "Hurricane",
            "tropical storm": "TropStorm",
            "tropical depression": "TropDep",
            "storm surge": "StormSurge",
            "tsunami": "Tsunami",
            "earthquake": "Earthquake",
            "volcano": "Volcano",
            "avalanche": "Avalanche",
            "landslide": "Landslide",
            "debris flow": "DebrisFlow",
            "dust storm": "DustStorm",
            "sandstorm": "Sandstorm",
            "blowing dust": "BlwDust",
            "blowing sand": "BlwSand"
        }
        
        result = title
        for key, value in replacements.items():
            # Case insensitive replace
            result = result.replace(key, value).replace(key.capitalize(), value).replace(key.upper(), value)
        
        # Limit to reasonable length
        if len(result) > 30:
            result = result[:27] + "..."
        
        return result

    def abbreviate_wind_direction(self, direction: str) -> str:
        """Abbreviate wind direction to emoji + 2-3 characters"""
        if not direction:
            return ""
        
        direction = direction.upper()
        replacements = {
            "NORTHWEST": "↖️NW",
            "NORTHEAST": "↗️NE",
            "SOUTHWEST": "↙️SW", 
            "SOUTHEAST": "↘️SE",
            "NORTH": "⬆️N",
            "EAST": "➡️E",
            "SOUTH": "⬇️S",
            "WEST": "⬅️W"
        }
        
        for full, abbrev in replacements.items():
            if full in direction:
                return abbrev
        
        # If no match, return first 2 characters with generic wind emoji
        return f"💨{direction[:2]}" if len(direction) >= 2 else f"💨{direction}"

    def extract_humidity(self, text: str) -> str:
        """Extract humidity percentage from forecast text"""
        if not text:
            return ""
        
        import re
        # Look for patterns like "humidity 45%" or "45% humidity"
        humidity_patterns = [
            r'humidity\s+(\d+)%',
            r'(\d+)%\s+humidity',
            r'relative humidity\s+(\d+)%',
            r'(\d+)%\s+relative humidity'
        ]
        
        for pattern in humidity_patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(1)
        
        return ""

    def extract_precip_chance(self, text: str) -> str:
        """Extract precipitation chance from forecast text"""
        if not text:
            return ""
        
        import re
        # Look for patterns like "20% chance" or "chance of rain 30%"
        precip_patterns = [
            r'(\d+)%\s+chance',
            r'chance\s+of\s+\w+\s+(\d+)%',
            r'(\d+)%\s+probability',
            r'probability\s+of\s+\w+\s+(\d+)%'
        ]
        
        for pattern in precip_patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(1)
        
        return ""

    def extract_high_low(self, text: str) -> str:
        """Extract high/low temperatures from forecast text"""
        if not text:
            return ""
        
        import re
        # Look for more specific patterns to avoid false matches
        high_low_patterns = [
            r'high\s+near\s+(\d+).*?low\s+around\s+(\d+)',
            r'high\s+(\d+).*?low\s+(\d+)',
            r'(\d+)\s+to\s+(\d+)\s+degrees',  # More specific
            r'temperature\s+(\d+)\s+to\s+(\d+)',
            r'high\s+near\s+(\d+).*?temperatures\s+falling\s+to\s+around\s+(\d+)',  # "High near 82, with temperatures falling to around 80"
            r'low\s+around\s+(\d+)',  # Just low temp
            r'high\s+near\s+(\d+)'   # Just high temp
        ]
        
        for pattern in high_low_patterns:
            match = re.search(pattern, text.lower())
            if match:
                if len(match.groups()) == 2:
                    high, low = match.groups()
                    # Validate that these are reasonable temperatures (20-120°F)
                    try:
                        high_val = int(high)
                        low_val = int(low)
                        if 20 <= high_val <= 120 and 20 <= low_val <= 120 and high_val > low_val:
                            return f"{high}°/{low}°"
                    except ValueError:
                        continue
                elif len(match.groups()) == 1:
                    # Single temperature - could be high or low
                    temp = match.group(1)
                    try:
                        temp_val = int(temp)
                        if 20 <= temp_val <= 120:
                            return f"{temp}°"
                    except ValueError:
                        continue
        
        return ""

    def extract_uv_index(self, text: str) -> str:
        """Extract UV index from forecast text"""
        if not text:
            return ""
        
        import re
        # Look for UV index patterns
        uv_patterns = [
            r'uv\s+index\s+(\d+)',
            r'uv\s+(\d+)',
            r'ultraviolet\s+index\s+(\d+)'
        ]
        
        for pattern in uv_patterns:
            match = re.search(pattern, text.lower())
            if match:
                uv_val = match.group(1)
                # Validate UV index (0-11+ is reasonable)
                try:
                    if 0 <= int(uv_val) <= 15:
                        return uv_val
                except ValueError:
                    continue
        
        return ""

    def extract_dew_point(self, text: str) -> str:
        """Extract dew point temperature from forecast text"""
        if not text:
            return ""
        
        import re
        # Look for dew point patterns
        dew_point_patterns = [
            r'dew point\s+(\d+)',
            r'dewpoint\s+(\d+)',
            r'dew\s+point\s+(\d+)°'
        ]
        
        for pattern in dew_point_patterns:
            match = re.search(pattern, text.lower())
            if match:
                dp_val = match.group(1)
                # Validate dew point (reasonable range -20 to 80°F)
                try:
                    if -20 <= int(dp_val) <= 80:
                        return dp_val
                except ValueError:
                    continue
        
        return ""

    def extract_visibility(self, text: str) -> str:
        """Extract visibility from forecast text"""
        if not text:
            return ""
        
        import re
        # Look for visibility patterns
        visibility_patterns = [
            r'visibility\s+(\d+)\s+miles',
            r'visibility\s+(\d+)\s+mi',
            r'(\d+)\s+mile\s+visibility',
            r'(\d+)\s+mi\s+visibility'
        ]
        
        for pattern in visibility_patterns:
            match = re.search(pattern, text.lower())
            if match:
                vis_val = match.group(1)
                # Validate visibility (reasonable range 0-20 miles)
                try:
                    if 0 <= int(vis_val) <= 20:
                        return vis_val
                except ValueError:
                    continue
        
        return ""

    def extract_precip_probability(self, text: str) -> str:
        """Extract precipitation probability from forecast text"""
        if not text:
            return ""
        
        import re
        # Look for precipitation probability patterns
        precip_prob_patterns = [
            r'(\d+)%\s+chance\s+of\s+(?:rain|precipitation|showers)',
            r'chance\s+of\s+(?:rain|precipitation|showers)\s+(\d+)%',
            r'(\d+)%\s+probability\s+of\s+(?:rain|precipitation|showers)',
            r'probability\s+of\s+(?:rain|precipitation|showers)\s+(\d+)%',
            r'(\d+)%\s+chance',
            r'chance\s+(\d+)%'
        ]
        
        for pattern in precip_prob_patterns:
            match = re.search(pattern, text.lower())
            if match:
                prob_val = match.group(1)
                # Validate probability (0-100%)
                try:
                    if 0 <= int(prob_val) <= 100:
                        return prob_val
                except ValueError:
                    continue
        
        return ""

    def extract_wind_gusts(self, text: str) -> str:
        """Extract wind gusts from forecast text"""
        if not text:
            return ""
        
        import re
        # Look for wind gust patterns
        gust_patterns = [
            r'gusts\s+to\s+(\d+)\s+mph',
            r'gusts\s+up\s+to\s+(\d+)\s+mph',
            r'wind\s+gusts\s+to\s+(\d+)\s+mph',
            r'wind\s+gusts\s+up\s+to\s+(\d+)\s+mph',
            r'gusts\s+(\d+)\s+mph',
            r'wind\s+gusts\s+(\d+)\s+mph'
        ]
        
        for pattern in gust_patterns:
            match = re.search(pattern, text.lower())
            if match:
                gust_val = match.group(1)
                # Validate wind gust (reasonable range 10-100 mph)
                try:
                    if 10 <= int(gust_val) <= 100:
                        return gust_val
                except ValueError:
                    continue
        
        return ""

    def get_current_conditions(self, lat: float, lon: float) -> str:
        """Get additional current conditions data from NOAA"""
        try:
            # Get the weather station info
            weather_api = f"https://api.weather.gov/points/{lat},{lon}"
            weather_data = requests.get(weather_api, timeout=self.url_timeout)
            if not weather_data.ok:
                return ""
            
            weather_json = weather_data.json()
            station_url = weather_json['properties'].get('observationStations')
            if not station_url:
                return ""
            
            # Get the nearest station
            stations_data = requests.get(station_url, timeout=self.url_timeout)
            if not stations_data.ok:
                return ""
            
            stations_json = stations_data.json()
            if not stations_json.get('features'):
                return ""
            
            # Get current observations from the nearest station
            station_id = stations_json['features'][0]['properties']['stationIdentifier']
            obs_url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
            
            obs_data = requests.get(obs_url, timeout=self.url_timeout)
            if not obs_data.ok:
                return ""
            
            obs_json = obs_data.json()
            if not obs_json.get('properties'):
                return ""
            
            props = obs_json['properties']
            conditions = []
            
            # Extract useful current conditions with emojis
            if props.get('relativeHumidity', {}).get('value'):
                humidity = int(props['relativeHumidity']['value'])
                conditions.append(f"{humidity}%RH")
            
            if props.get('dewpoint', {}).get('value'):
                dewpoint = int(props['dewpoint']['value'] * 9/5 + 32)  # Convert C to F
                conditions.append(f"💧{dewpoint}°")
            
            if props.get('visibility', {}).get('value'):
                visibility = int(props['visibility']['value'] * 0.000621371)  # Convert m to miles
                if visibility > 0:
                    conditions.append(f"👁️{visibility}mi")
            
            if props.get('windGust', {}).get('value'):
                wind_gust = int(props['windGust']['value'] * 2.237)  # Convert m/s to mph
                if wind_gust > 10:
                    conditions.append(f"💨{wind_gust}")
            
            if props.get('barometricPressure', {}).get('value'):
                pressure = int(props['barometricPressure']['value'] / 100)  # Convert Pa to hPa
                conditions.append(f"📊{pressure}hPa")
            
            return " ".join(conditions[:3])  # Limit to 3 conditions to avoid overflow
            
        except Exception as e:
            self.logger.debug(f"Error getting current conditions: {e}")
            return ""

    def get_weather_emoji(self, condition: str) -> str:
        """Get emoji for weather condition"""
        if not condition:
            return ""
        
        condition_lower = condition.lower()
        
        # Weather condition emojis
        if any(word in condition_lower for word in ['sunny', 'clear']):
            return "☀️"
        elif any(word in condition_lower for word in ['cloudy', 'overcast']):
            return "☁️"
        elif any(word in condition_lower for word in ['partly cloudy', 'mostly cloudy']):
            return "⛅"
        elif any(word in condition_lower for word in ['rain', 'showers']):
            return "🌦️"
        elif any(word in condition_lower for word in ['thunderstorm', 'thunderstorms']):
            return "⛈️"
        elif any(word in condition_lower for word in ['snow', 'snow showers']):
            return "❄️"
        elif any(word in condition_lower for word in ['fog', 'mist', 'haze']):
            return "🌫️"
        elif any(word in condition_lower for word in ['smoke']):
            return "💨"
        elif any(word in condition_lower for word in ['windy', 'breezy']):
            return "💨"
        else:
            return "🌤️"  # Default weather emoji

    def abbreviate_noaa(self, text: str) -> str:
        """Replace long strings with shorter ones for display"""
        replacements = {
            "monday": "Mon",
            "tuesday": "Tue", 
            "wednesday": "Wed",
            "thursday": "Thu",
            "friday": "Fri",
            "saturday": "Sat",
            "sunday": "Sun",
            "northwest": "NW",
            "northeast": "NE", 
            "southwest": "SW",
            "southeast": "SE",
            "north": "N",
            "south": "S",
            "east": "E",
            "west": "W",
            "precipitation": "precip",
            "showers": "shwrs",
            "thunderstorms": "t-storms",
            "thunderstorm": "t-storm",
            "quarters": "qtrs",
            "quarter": "qtr",
            "january": "Jan",
            "february": "Feb",
            "march": "Mar",
            "april": "Apr",
            "may": "May",
            "june": "Jun",
            "july": "Jul",
            "august": "Aug",
            "september": "Sep",
            "october": "Oct",
            "november": "Nov",
            "december": "Dec",
            "degrees": "°",
            "percent": "%",
            "department": "Dept.",
            "amounts less than a tenth of an inch possible.": "< 0.1in",
            "temperatures": "temps.",
            "temperature": "temp.",
        }
        
        line = text
        for key, value in replacements.items():
            # Case insensitive replace
            line = line.replace(key, value).replace(key.capitalize(), value).replace(key.upper(), value)
        
        return line
