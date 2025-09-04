#!/usr/bin/env python3
"""
BLE UUID Discovery Script for MeshCore
This script connects to your MeshCore device and discovers all available services and characteristics.
"""

import asyncio
import configparser
from pathlib import Path


async def discover_device_uuids():
    """Discover all UUIDs on the MeshCore device"""
    print("MeshCore BLE UUID Discovery")
    print("=" * 40)
    
    # Load config
    config_file = "config.ini"
    if not Path(config_file).exists():
        print(f"Config file {config_file} not found!")
        return
    
    config = configparser.ConfigParser()
    config.read(config_file)
    
    device_name = config.get('Connection', 'ble_device_name', fallback='')
    if not device_name:
        print("No BLE device name configured!")
        return
    
    print(f"Target device: {device_name}")
    print()
    
    try:
        from bleak import BleakScanner, BleakClient
        
        # Clean device name
        device_name = device_name.strip().strip('"').strip("'")
        
        # Scan for device
        print("Scanning for device...")
        devices = await BleakScanner.discover(timeout=10)
        
        target_device = None
        for device in devices:
            if device.name and device.name.strip() == device_name:
                target_device = device
                break
        
        if not target_device:
            print(f"Device '{device_name}' not found!")
            return
        
        print(f"Found device: {target_device.name}")
        print(f"Address: {target_device.address}")
        print()
        
        # Connect to device
        print("Connecting to device...")
        client = BleakClient(target_device.address)
        await client.connect()
        
        if not client.is_connected:
            print("Failed to connect!")
            return
        
        print("✓ Connected successfully!")
        print()
        
        # Discover all services
        print("Discovering services and characteristics...")
        print("-" * 50)
        
        services = client.services
        service_count = len(list(services))
        print(f"Found {service_count} service(s):")
        print()
        
        all_uuids = {
            'services': [],
            'characteristics': []
        }
        
        for i, service in enumerate(services, 1):
            print(f"Service {i}:")
            print(f"  UUID: {service.uuid}")
            print(f"  Description: {service.description}")
            
            all_uuids['services'].append({
                'uuid': service.uuid,
                'description': service.description
            })
            
            # Get characteristics for this service
            char_count = len(service.characteristics)
            print(f"  Characteristics ({char_count}):")
            
            for j, char in enumerate(service.characteristics, 1):
                print(f"    {j}. UUID: {char.uuid}")
                print(f"       Properties: {char.properties}")
                print(f"       Description: {char.description}")
                
                all_uuids['characteristics'].append({
                    'uuid': char.uuid,
                    'properties': char.properties,
                    'description': char.description,
                    'service_uuid': service.uuid
                })
            
            print()
        
        # Analyze the discovered UUIDs
        print("UUID Analysis:")
        print("-" * 50)
        
        # Check for Nordic UART Service
        nus_service_found = False
        nus_tx_found = False
        nus_rx_found = False
        
        for service in all_uuids['services']:
            if service['uuid'].lower() == '6e400001-b5a3-f393-e0a9-e50e24dcca9e':
                nus_service_found = True
                print("✓ Nordic UART Service found")
                break
        
        for char in all_uuids['characteristics']:
            if char['uuid'].lower() == '6e400002-b5a3-f393-e0a9-e50e24dcca9e':
                nus_tx_found = True
                print("✓ Nordic UART TX characteristic found")
            elif char['uuid'].lower() == '6e400003-b5a3-f393-e0a9-e50e24dcca9e':
                nus_rx_found = True
                print("✓ Nordic UART RX characteristic found")
        
        if not nus_service_found:
            print("✗ Nordic UART Service not found")
        if not nus_tx_found:
            print("✗ Nordic UART TX characteristic not found")
        if not nus_rx_found:
            print("✗ Nordic UART RX characteristic not found")
        
        print()
        
        # Look for alternative MeshCore UUIDs
        print("Looking for MeshCore-specific UUIDs...")
        meshcore_uuids = []
        
        for char in all_uuids['characteristics']:
            if 'mesh' in char['description'].lower() or 'core' in char['description'].lower():
                meshcore_uuids.append(char)
                print(f"Potential MeshCore characteristic: {char['uuid']} ({char['description']})")
        
        if not meshcore_uuids:
            print("No obvious MeshCore-specific characteristics found")
        
        print()
        
        # Summary
        print("Summary:")
        print("-" * 50)
        if nus_service_found and nus_tx_found and nus_rx_found:
            print("✓ Device uses standard Nordic UART Service")
            print("✓ Current UUIDs in meshcore_protocol.py are correct")
        else:
            print("✗ Device does not use standard Nordic UART Service")
            print("✗ UUIDs in meshcore_protocol.py may need updating")
            print("\nAlternative UUIDs found:")
            for char in all_uuids['characteristics']:
                if 'write' in char['properties']:
                    print(f"  Write characteristic: {char['uuid']} ({char['description']})")
                if 'read' in char['properties'] or 'notify' in char['properties']:
                    print(f"  Read/Notify characteristic: {char['uuid']} ({char['description']})")
        
        # Disconnect
        await client.disconnect()
        print("\n✓ Disconnected successfully")
        
    except ImportError:
        print("BLE support not available. Install bleak: pip install bleak")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(discover_device_uuids())
