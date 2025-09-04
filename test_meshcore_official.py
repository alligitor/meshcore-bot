#!/usr/bin/env python3
"""
Test script to understand how the official meshcore package works
"""

import asyncio
import meshcore
from meshcore import EventType

async def test_meshcore():
    """Test the official meshcore package"""
    print("Testing official meshcore package...")
    
    # Try to create a BLE connection
    try:
        # This will scan for devices
        mc = await meshcore.MeshCore.create_ble(debug=True)
        print(f"Connected to: {mc.self_info}")
        
        # Subscribe to message events
        async def on_message(event):
            print(f"Received message event: {event}")
        
        async def on_contact_msg(event):
            print(f"Received contact message: {event}")
        
        async def on_channel_msg(event):
            print(f"Received channel message: {event}")
        
        subscription1 = mc.subscribe(EventType.CONTACT_MSG_RECV, on_contact_msg)
        subscription2 = mc.subscribe(EventType.CHANNEL_MSG_RECV, on_channel_msg)
        
        # Start auto message fetching
        await mc.start_auto_message_fetching()
        
        print("Listening for messages... Press Ctrl+C to stop")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_meshcore())
