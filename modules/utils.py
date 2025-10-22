#!/usr/bin/env python3
"""
Utility functions for the MeshCore Bot
Shared helper functions used across multiple modules
"""

import re
from typing import Optional


def abbreviate_location(location: str, max_length: int = 20) -> str:
    """
    Abbreviate a location string to fit within character limits.
    
    Args:
        location: The location string to abbreviate
        max_length: Maximum length for the abbreviated string
        
    Returns:
        Abbreviated location string
    """
    if not location:
        return location
    
    # Apply common abbreviations first
    abbreviated = location
    
    abbreviations = [
        ('Central Business District', 'CBD'),
        ('Business District', 'BD'),
        ('British Columbia', 'BC'),
        ('United States', 'USA'),
        ('United Kingdom', 'UK'),
        ('Washington', 'WA'),
        ('California', 'CA'),
        ('New York', 'NY'),
        ('Texas', 'TX'),
        ('Florida', 'FL'),
        ('Illinois', 'IL'),
        ('Pennsylvania', 'PA'),
        ('Ohio', 'OH'),
        ('Georgia', 'GA'),
        ('North Carolina', 'NC'),
        ('Michigan', 'MI'),
        ('New Jersey', 'NJ'),
        ('Virginia', 'VA'),
        ('Tennessee', 'TN'),
        ('Indiana', 'IN'),
        ('Arizona', 'AZ'),
        ('Massachusetts', 'MA'),
        ('Missouri', 'MO'),
        ('Maryland', 'MD'),
        ('Wisconsin', 'WI'),
        ('Colorado', 'CO'),
        ('Minnesota', 'MN'),
        ('South Carolina', 'SC'),
        ('Alabama', 'AL'),
        ('Louisiana', 'LA'),
        ('Kentucky', 'KY'),
        ('Oregon', 'OR'),
        ('Oklahoma', 'OK'),
        ('Connecticut', 'CT'),
        ('Utah', 'UT'),
        ('Iowa', 'IA'),
        ('Nevada', 'NV'),
        ('Arkansas', 'AR'),
        ('Mississippi', 'MS'),
        ('Kansas', 'KS'),
        ('New Mexico', 'NM'),
        ('Nebraska', 'NE'),
        ('West Virginia', 'WV'),
        ('Idaho', 'ID'),
        ('Hawaii', 'HI'),
        ('New Hampshire', 'NH'),
        ('Maine', 'ME'),
        ('Montana', 'MT'),
        ('Rhode Island', 'RI'),
        ('Delaware', 'DE'),
        ('South Dakota', 'SD'),
        ('North Dakota', 'ND'),
        ('Alaska', 'AK'),
        ('Vermont', 'VT'),
        ('Wyoming', 'WY')
    ]
    
    # Apply abbreviations in order
    for full_term, abbrev in abbreviations:
        if full_term in abbreviated:
            abbreviated = abbreviated.replace(full_term, abbrev)
    
    # If still too long after abbreviations, try to truncate intelligently
    if len(abbreviated) > max_length:
        # Try to keep the most important part (usually the city name)
        parts = abbreviated.split(', ')
        if len(parts) > 1:
            # Keep the first part (usually city) and truncate if needed
            first_part = parts[0]
            if len(first_part) <= max_length:
                abbreviated = first_part
            else:
                abbreviated = first_part[:max_length-3] + '...'
        else:
            # Just truncate with ellipsis
            abbreviated = abbreviated[:max_length-3] + '...'
    
    return abbreviated


def truncate_string(text: str, max_length: int, ellipsis: str = '...') -> str:
    """
    Truncate a string to a maximum length with ellipsis.
    
    Args:
        text: The string to truncate
        max_length: Maximum length including ellipsis
        ellipsis: String to append when truncating
        
    Returns:
        Truncated string
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(ellipsis)] + ellipsis


def format_location_for_display(city: Optional[str], state: Optional[str] = None, 
                               country: Optional[str] = None, max_length: int = 20) -> Optional[str]:
    """
    Format location data for display with intelligent abbreviation.
    
    Args:
        city: City name (may include neighborhood/district)
        state: State/province name
        country: Country name
        max_length: Maximum length for the formatted location
        
    Returns:
        Formatted location string or None if no location data
    """
    if not city:
        return None
    
    # Start with city (which may include neighborhood)
    location_parts = [city]
    
    # Add state if available and different from city
    if state and state not in location_parts:
        location_parts.append(state)
    
    # Join parts and abbreviate if needed
    full_location = ', '.join(location_parts)
    return abbreviate_location(full_location, max_length)
