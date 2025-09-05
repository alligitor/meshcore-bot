#!/usr/bin/env python3
"""
Test script to fetch and display channel information from MeshCore device
"""

import asyncio
import meshcore
from meshcore_cli.meshcore_cli import next_cmd

async def test_channels():
    """Test fetching channels from MeshCore device"""
    print("Connecting to MeshCore device...")
    
    try:
        # Connect to MeshCore device
        mc = await meshcore.MeshCore.create_ble(debug=True)
        
        if mc.is_connected:
            print(f"Connected to: {mc.self_info}")
            
            # Try to fetch channels
            print("\nFetching channels...")
            try:
                result = await next_cmd(mc, ["channels"])
                print(f"Channels command result: {result}")
                
                if result:
                    print(f"Found {len(result)} channels:")
                    for i, channel in enumerate(result):
                        print(f"  Channel {i}: {channel}")
                else:
                    print("No channels returned")
                    
            except Exception as e:
                print(f"Error fetching channels: {e}")
            
            # Try individual channel queries
            print("\nTrying individual channel queries...")
            for channel_num in range(5):
                try:
                    result = await next_cmd(mc, ["get_channel", str(channel_num)])
                    print(f"Channel {channel_num}: {result}")
                except Exception as e:
                    print(f"Channel {channel_num}: Error - {e}")
            
            # Disconnect
            await mc.disconnect()
            print("\nDisconnected")
            
        else:
            print("Failed to connect")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_channels())
