#!/usr/bin/env python3
"""
Moon Command - Provides moon phase and position information
"""

from .base_command import BaseCommand
from ..solar_conditions import get_moon
from ..models import MeshMessage


class MoonCommand(BaseCommand):
    """Command to get moon information"""
    
    # Plugin metadata
    name = "moon"
    keywords = ['moon']
    description = "Get moon phase, rise/set times and position"
    category = "solar"
    
    def __init__(self, bot):
        super().__init__(bot)
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute the moon command"""
        try:
            # Get moon information using default location
            moon_info = get_moon()
            
            # Format the response to be more compact and readable
            response = self._format_moon_response(moon_info)
            
            # Use the unified send_response method
            await self.send_response(message, response)
            return True
            
        except Exception as e:
            error_msg = f"Error getting moon info: {e}"
            await self.send_response(message, error_msg)
            return False
    
    def _format_moon_response(self, moon_info: str) -> str:
        """Format moon information to be more compact and readable"""
        try:
            # Parse the moon info string to extract key information
            lines = moon_info.split('\n')
            moon_data = {}
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    moon_data[key.strip()] = value.strip()
            
            # Create a more compact format while keeping essential details
            if 'MoonRise' in moon_data and 'Set' in moon_data and 'Phase' in moon_data:
                # Keep day info but make it more compact
                rise_info = moon_data['MoonRise']  # e.g., "Thu 04 06:47PM"
                set_info = moon_data['Set']        # e.g., "Fri 05 03:43AM"
                
                # Extract phase and illumination
                phase_info = moon_data.get('Phase', 'Unknown')
                if '@:' in phase_info:
                    phase, illum = phase_info.split('@:')
                    phase = phase.strip()
                    illum = illum.strip()
                else:
                    phase = phase_info
                    illum = 'N/A'
                
                # Create compact response with essential details
                response = f"🌙 {phase} {illum}\nRise:{rise_info} Set:{set_info}"
                
                # Add next full and new moon dates (compact format)
                if 'FullMoon' in moon_data and 'NewMoon' in moon_data:
                    full_moon = moon_data['FullMoon']  # e.g., "Sun Sep 07 11:08AM"
                    new_moon = moon_data['NewMoon']    # e.g., "Sun Sep 21 12:54PM"
                    
                    # Extract just the essential date/time parts
                    full_parts = full_moon.split()
                    new_parts = new_moon.split()
                    
                    if len(full_parts) >= 3 and len(new_parts) >= 3:
                        # Format: "Sep 07 11:08AM" and "Sep 21 12:54PM"
                        full_compact = f"{full_parts[1]} {full_parts[2]} {full_parts[3]}"
                        new_compact = f"{new_parts[1]} {new_parts[2]} {new_parts[3]}"
                        response += f"\nFull:{full_compact} New:{new_compact}"
                
                return response
            else:
                # Fallback to original format if parsing fails
                return f"🌙 {moon_info}"
                
        except Exception as e:
            # Fallback to original format if formatting fails
            return f"🌙 {moon_info}"
    
    def get_help_text(self):
        """Get help text for this command"""
        return self.description
