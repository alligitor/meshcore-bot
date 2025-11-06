#!/usr/bin/env python3
"""
Satellite Pass Command - Provides satellite pass information
"""

from .base_command import BaseCommand
from ..solar_conditions import get_next_satellite_pass
from ..models import MeshMessage


class SatpassCommand(BaseCommand):
    """Command to get satellite pass information"""
    
    # Plugin metadata
    name = "satpass"
    keywords = ['satpass']
    description = "Get satellite pass info: satpass <NORAD_number_or_shortcut> [visual]"
    category = "solar"
    
    # Common satellite shortcuts
    SATELLITE_SHORTCUTS = {
    'iss': '25544',
    'hst': '20580',  # Hubble Space Telescope
    'hubble': '20580',
    'starlink': '44294',  # Example Starlink satellite
    'tiangong': '48274',  # Tiangong space station
    'goes18': '51850',  # GOES-18 weather satellite
    }
    
    def __init__(self, bot):
        super().__init__(bot)
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the satpass command"""
        try:
            # Check if user provided a satellite number
            content = message.content.strip()
            if content == 'satpass':
                # No satellite specified, show help
                help_text = self._get_help_text()
                await self.send_response(message, help_text)
                return True
            
            # Extract satellite identifier from command
            parts = content.split()
            if len(parts) < 2:
                error_msg = "Please provide a satellite NORAD number or shortcut. Example: satpass iss"
                await self.send_response(message, error_msg)
                return True
            
            satellite_input = parts[1].lower()
            
            # Check for "visual" or "vis" option
            use_visual = False
            if len(parts) >= 3:
                option = parts[2].lower()
                if option in ['visual', 'vis']:
                    use_visual = True
            
            # Check if it's a shortcut first
            if satellite_input in self.SATELLITE_SHORTCUTS:
                satellite = self.SATELLITE_SHORTCUTS[satellite_input]
            else:
                # Assume it's a NORAD number
                satellite = satellite_input
            
            # Get satellite pass information
            pass_info = get_next_satellite_pass(satellite, use_visual=use_visual)
            
            # Send response
            response = f"🛰️ Satellite Pass:\n{pass_info}"
            await self.send_response(message, response)
            return True
            
        except Exception as e:
            error_msg = f"Error getting satellite pass info: {e}"
            await self.send_response(message, error_msg)
            return False
    
    def _get_help_text(self):
        """Get detailed help text with shortcuts"""
        shortcuts_text = "🛰️ Satellite Pass Info\n\nUsage: satpass <NORAD_number_or_shortcut>\n\nShortcuts:\n"
        
        # Group shortcuts by category for better organization
        weather_sats = ['noaa15', 'noaa18', 'noaa19', 'metop-a', 'metop-b', 'metop-c', 'goes16', 'goes17', 'goes18']
        space_stations = ['iss', 'tiangong', 'tiangong1', 'tiangong2']
        telescopes = ['hst', 'hubble']
        other = ['starlink']
        
        # Add weather satellites
        shortcuts_text += "🌤️ Weather: "
        weather_list = [f"{name} ({self.SATELLITE_SHORTCUTS[name]})" for name in weather_sats if name in self.SATELLITE_SHORTCUTS]
        shortcuts_text += ", ".join(weather_list) + "\n"
        
        # Add space stations
        shortcuts_text += "🚀 Stations: "
        station_list = [f"{name} ({self.SATELLITE_SHORTCUTS[name]})" for name in space_stations if name in self.SATELLITE_SHORTCUTS]
        shortcuts_text += ", ".join(station_list) + "\n"
        
        # Add telescopes
        shortcuts_text += "🔭 Telescopes: "
        telescope_list = [f"{name} ({self.SATELLITE_SHORTCUTS[name]})" for name in telescopes if name in self.SATELLITE_SHORTCUTS]
        shortcuts_text += ", ".join(telescope_list) + "\n"
        
        # Add other satellites
        shortcuts_text += "🛰️ Other: "
        other_list = [f"{name} ({self.SATELLITE_SHORTCUTS[name]})" for name in other if name in self.SATELLITE_SHORTCUTS]
        shortcuts_text += ", ".join(other_list) + "\n"
        
        shortcuts_text += "\nExamples:\n• satpass iss\n• satpass noaa15\n• satpass 25544\n• satpass 27607 visual (visual passes only)"
        
        return shortcuts_text
    
    def get_help_text(self):
        """Get help text for this command"""
        return self.description
