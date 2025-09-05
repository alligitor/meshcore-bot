#!/usr/bin/env python3
"""
Test script to examine the actual event structure for channel messages
"""

import asyncio
import meshcore
from meshcore import EventType

async def test_event_structure():
    """Test the event structure for channel messages"""
    print("Testing event structure for channel messages...")
    
    try:
        # Create a BLE connection
        mc = await meshcore.MeshCore.create_ble(debug=True)
        print(f"Connected to: {mc.self_info}")
        
        # Subscribe to channel message events
        async def on_channel_msg(event):
            print(f"\n=== CHANNEL MESSAGE EVENT ===")
            print(f"Event type: {event.type}")
            print(f"Event payload: {event.payload}")
            print(f"Event payload type: {type(event.payload)}")
            print(f"Event payload keys: {list(event.payload.keys()) if hasattr(event.payload, 'keys') else 'No keys'}")
            print(f"Event metadata: {getattr(event, 'metadata', 'No metadata')}")
            print(f"Event dir: {[x for x in dir(event) if not x.startswith('_')]}")
            
            # Try to access all possible attributes
            for attr in dir(event):
                if not attr.startswith('_'):
                    try:
                        value = getattr(event, attr)
                        print(f"  {attr}: {value}")
                    except Exception as e:
                        print(f"  {attr}: Error accessing - {e}")
            
            print("=== END EVENT ===\n")
        
        subscription = mc.subscribe(EventType.CHANNEL_MSG_RECV, on_channel_msg)
        
        # Start auto message fetching
        await mc.start_auto_message_fetching()
        
        print("Listening for channel messages... Press Ctrl+C to stop")
        print("Send a test message to a channel to see the event structure")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_event_structure())
