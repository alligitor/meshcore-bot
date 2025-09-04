#!/usr/bin/env python3
"""
Test config parsing to debug the scheduled messages issue
"""

import configparser

def test_config_parsing():
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    print("=== Config Parsing Test ===")
    
    if config.has_section('Scheduled_Messages'):
        print("Scheduled_Messages section found:")
        for key, value in config.items('Scheduled_Messages'):
            print(f"  Key: '{key}' -> Value: '{value}'")
            
            # Test our time format validation
            if len(key) == 4:
                try:
                    hour = int(key[:2])
                    minute = int(key[2:])
                    print(f"    Parsed as: {hour:02d}:{minute:02d}")
                except ValueError:
                    print(f"    Invalid time format")
            else:
                print(f"    Wrong length: {len(key)}")
    else:
        print("Scheduled_Messages section not found!")

if __name__ == "__main__":
    test_config_parsing()
