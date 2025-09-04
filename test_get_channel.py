#!/usr/bin/env python3
"""
Test script to see what get_channel command returns
"""

import asyncio
import meshcore
from meshcore_cli.meshcore_cli import next_cmd

async def test_get_channel():
    """Test get_channel command"""
    print("Connecting to MeshCore device...")
    
    try:
        # Connect to MeshCore device
        mc = await meshcore.MeshCore.create_ble(debug=True)
        
        if mc.is_connected:
            print(f"Connected to: {mc.self_info}")
            
            # Test get_channel for channel 5 (MyTest)
            print("\nTesting get_channel for channel 5...")
            try:
                result = await next_cmd(mc, ["get_channel", "5"])
                print(f"Result type: {type(result)}")
                print(f"Result: {result}")
                if result:
                    print(f"Result length: {len(result)}")
                    for i, item in enumerate(result):
                        print(f"  Item {i}: {item} (type: {type(item)})")
                        if isinstance(item, dict):
                            for key, value in item.items():
                                print(f"    {key}: {value}")
            except Exception as e:
                print(f"Error: {e}")
            
            # Test get_channel for channel 4 (Testing)
            print("\nTesting get_channel for channel 4...")
            try:
                result = await next_cmd(mc, ["get_channel", "4"])
                print(f"Result type: {type(result)}")
                print(f"Result: {result}")
                if result:
                    print(f"Result length: {len(result)}")
                    for i, item in enumerate(result):
                        print(f"  Item {i}: {item} (type: {type(item)})")
                        if isinstance(item, dict):
                            for key, value in item.items():
                                print(f"    {key}: {value}")
            except Exception as e:
                print(f"Error: {e}")
            
            # Disconnect
            await mc.disconnect()
            print("\nDisconnected")
            
        else:
            print("Failed to connect")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_get_channel())

