#!/usr/bin/env python3
"""
Test script to examine contacts in the meshcore package
"""

import asyncio
import meshcore
from meshcore import EventType
from meshcore_cli.meshcore_cli import send_cmd

async def test_contacts():
    """Test contact discovery and examination"""
    try:
        print("Connecting to MeshCore node...")
        mc = await meshcore.MeshCore.create_ble(debug=True)
        
        if mc.is_connected:
            print(f"Connected to: {mc.self_info}")
            
            # Try to manually load contacts
            print("Attempting to load contacts...")
            
            # Check if there are any commands to load contacts
            print("Available methods on meshcore object:")
            for method in dir(mc):
                if not method.startswith('_') and 'contact' in method.lower():
                    print(f"  {method}")
            
            # Try to ensure contacts are loaded
            if hasattr(mc, 'ensure_contacts'):
                print("Calling ensure_contacts()...")
                await mc.ensure_contacts()
            
            # Wait a bit more
            print("Waiting for contacts to load (10 seconds)...")
            await asyncio.sleep(10)
            
            # Examine contacts
            print(f"\nContacts ({len(mc.contacts)}):")
            for key, contact in mc.contacts.items():
                print(f"  Key: {key}")
                print(f"  Contact: {contact}")
                print(f"  Name: {contact.get('adv_name', 'N/A')}")
                print(f"  Type: {contact.get('type', 'N/A')}")
                print(f"  Pubkey: {contact.get('pubkey', 'N/A')}")
                print(f"  Pubkey prefix: {contact.get('pubkey_prefix', 'N/A')}")
                print("  ---")
            
            # Check pending contacts
            print(f"\nPending contacts ({len(mc.pending_contacts)}):")
            for contact in mc.pending_contacts:
                print(f"  Contact: {contact}")
                print(f"  Name: {contact.get('adv_name', 'N/A')}")
                print(f"  Pubkey: {contact.get('pubkey', 'N/A')}")
                print(f"  Pubkey prefix: {contact.get('pubkey_prefix', 'N/A')}")
                print("  ---")
            
            # Try to manually request contacts from the device
            print("\nTrying to request contacts from device...")
            try:
                # Send a command to get contacts
                from meshcore_cli.meshcore_cli import next_cmd
                result = await next_cmd(mc, ["contacts"])
                print(f"Contacts command result: {result}")
            except Exception as e:
                print(f"Error requesting contacts: {e}")
            
            # Test get_contact_by_key_prefix
            test_prefix = "460728508c17"
            print(f"\nTesting get_contact_by_key_prefix('{test_prefix}'):")
            contact = mc.get_contact_by_key_prefix(test_prefix)
            if contact:
                print(f"Found contact: {contact}")
            else:
                print("Contact not found")
                
                # Try to find by name
                print(f"\nTrying to find by name...")
                for key, contact in mc.contacts.items():
                    if contact.get('adv_name') == test_prefix:
                        print(f"Found by name: {contact}")
                        break
                else:
                    print("Not found by name either")
            
            # Test get_contact_by_name
            print(f"\nTesting get_contact_by_name('{test_prefix}'):")
            contact = mc.get_contact_by_name(test_prefix)
            if contact:
                print(f"Found contact: {contact}")
            else:
                print("Contact not found by name")
            
            await mc.disconnect()
        else:
            print("Failed to connect")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_contacts())
