#!/usr/bin/env python3
"""
Test script to verify dynamic channel fetching using get_channel commands
"""

import asyncio
import meshcore
from meshcore_cli.meshcore_cli import next_cmd

async def test_dynamic_channels():
    """Test dynamic channel fetching"""
    print("Connecting to MeshCore device...")
    
    try:
        # Connect to MeshCore device
        mc = await meshcore.MeshCore.create_ble(debug=True)
        
        if mc.is_connected:
            print(f"Connected to: {mc.self_info}")
            
            # Test dynamic channel fetching
            print("\nTesting dynamic channel fetching...")
            channels = {}
            
            for channel_num in range(10):  # Check channels 0-9
                try:
                    print(f"Fetching channel {channel_num}...")
                    result = await next_cmd(mc, ["get_channel", str(channel_num)])
                    if result and len(result) > 0:
                        channel_info = result[0]
                        if isinstance(channel_info, dict) and 'channel_name' in channel_info:
                            channels[channel_num] = {
                                'number': channel_num,
                                'name': channel_info['channel_name'],
                                'secret': channel_info.get('channel_secret', '')
                            }
                            print(f"  ✓ Channel {channel_num}: {channel_info['channel_name']}")
                        else:
                            print(f"  ✗ Channel {channel_num}: Invalid format")
                    else:
                        print(f"  ✗ Channel {channel_num}: No result")
                except Exception as e:
                    print(f"  ✗ Channel {channel_num}: Error - {e}")
            
            print(f"\nFound {len(channels)} channels:")
            for num, info in channels.items():
                print(f"  Channel {num}: {info['name']}")
            
            # Disconnect
            await mc.disconnect()
            print("\nDisconnected")
            
        else:
            print("Failed to connect")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_dynamic_channels())
