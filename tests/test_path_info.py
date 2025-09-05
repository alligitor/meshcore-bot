#!/usr/bin/env python3
"""
Test script to investigate path information availability in meshcore-cli
"""

import asyncio
import meshcore
from meshcore import EventType

async def test_path_information():
    """Test to see what path information is available"""
    print("Testing path information availability in meshcore-cli...")
    
    try:
        # Create a BLE connection
        mc = await meshcore.MeshCore.create_ble(debug=True)
        print(f"Connected to: {mc.self_info}")
        
        # Wait for contacts to load
        print("Waiting for contacts to load...")
        await asyncio.sleep(10)
        
        # Try to manually request contacts if none loaded
        if len(mc.contacts) == 0:
            print("No contacts loaded automatically, trying manual request...")
            try:
                from meshcore_cli.meshcore_cli import next_cmd
                result = await next_cmd(mc, ["contacts"])
                print(f"Manual contacts request result: {result}")
                await asyncio.sleep(5)  # Wait for contacts to process
            except Exception as e:
                print(f"Error requesting contacts: {e}")
        
        # Examine contacts for path information
        print(f"\nExamining {len(mc.contacts)} contacts for path information:")
        path_contacts = []
        for key, contact in mc.contacts.items():
            out_path = contact.get('out_path', '')
            out_path_len = contact.get('out_path_len', -1)
            if out_path and out_path_len > 0:
                path_contacts.append({
                    'name': contact.get('adv_name', 'Unknown'),
                    'pubkey': contact.get('public_key', '')[:16] + '...',
                    'out_path': out_path,
                    'out_path_len': out_path_len
                })
                print(f"  {contact.get('adv_name', 'Unknown')}: {out_path} ({out_path_len} hops)")
        
        print(f"\nFound {len(path_contacts)} contacts with path information")
        
        # Test path discovery for a specific contact
        if path_contacts:
            test_contact = path_contacts[0]
            print(f"\nTesting path discovery for: {test_contact['name']}")
            print(f"  Path: {test_contact['out_path']}")
            print(f"  Hops: {test_contact['out_path_len']}")
            
            # Convert hex path to readable format
            path_bytes = bytes.fromhex(test_contact['out_path'])
            path_nodes = []
            for i in range(0, len(path_bytes), 2):
                if i + 1 < len(path_bytes):
                    node_id = int.from_bytes(path_bytes[i:i+2], byteorder='little')
                    path_nodes.append(f"{node_id:04x}")
            
            print(f"  Path nodes: {' -> '.join(path_nodes)}")
        
        # Set up event handlers to capture path information
        path_events = []
        
        async def on_path_update(event):
            print(f"PATH_UPDATE event: {event.payload}")
            path_events.append(('PATH_UPDATE', event.payload))
        
        async def on_path_response(event):
            print(f"PATH_RESPONSE event: {event.payload}")
            path_events.append(('PATH_RESPONSE', event.payload))
        
        async def on_channel_message(event):
            print(f"CHANNEL_MSG_RECV event: {event.payload}")
            print(f"  Path length: {event.payload.get('path_len', 'N/A')}")
            print(f"  Sender: {event.payload.get('text', 'N/A')[:20]}...")
            
            # Try to look up path information from contacts
            if hasattr(event, 'metadata') and event.metadata:
                pubkey_prefix = event.metadata.get('pubkey_prefix', '')
                if pubkey_prefix:
                    print(f"  Looking for contact with pubkey_prefix: {pubkey_prefix}")
                    for key, contact in mc.contacts.items():
                        if contact.get('public_key', '').startswith(pubkey_prefix):
                            out_path = contact.get('out_path', '')
                            out_path_len = contact.get('out_path_len', -1)
                            if out_path and out_path_len > 0:
                                print(f"  Found path: {out_path} ({out_path_len} hops)")
                                # Convert to readable format
                                path_bytes = bytes.fromhex(out_path)
                                path_nodes = []
                                for i in range(0, len(path_bytes), 2):
                                    if i + 1 < len(path_bytes):
                                        node_id = int.from_bytes(path_bytes[i:i+2], byteorder='little')
                                        path_nodes.append(f"{node_id:04x}")
                                print(f"  Path nodes: {' -> '.join(path_nodes)}")
                            break
        
        # Subscribe to events
        mc.subscribe(EventType.PATH_UPDATE, on_path_update)
        mc.subscribe(EventType.PATH_RESPONSE, on_path_response)
        mc.subscribe(EventType.CHANNEL_MSG_RECV, on_channel_message)
        
        print("\nListening for messages and path events (30 seconds)...")
        await asyncio.sleep(30)
        
        print(f"\nCaptured {len(path_events)} path events:")
        for event_type, payload in path_events:
            print(f"  {event_type}: {payload}")
        
        await mc.disconnect()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_path_information())
