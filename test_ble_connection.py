#!/usr/bin/env python3
"""
BLE Connection Test Script for MeshCore Bot
This script helps debug BLE connectivity issues.
"""

import asyncio
import sys
import configparser
from pathlib import Path


async def test_ble_scan():
    """Test BLE scanning functionality"""
    print("Testing BLE Scanning...")
    print("=" * 40)
    
    try:
        from bleak import BleakScanner
        
        print("Scanning for BLE devices...")
        devices = await BleakScanner.discover(timeout=10)
        
        if not devices:
            print("No BLE devices found!")
            return False
        
        print(f"Found {len(devices)} BLE devices:")
        for i, device in enumerate(devices, 1):
            print(f"{i:2d}. Name: {device.name or 'Unknown'}")
            print(f"    Address: {device.address}")
            print(f"    RSSI: {device.rssi}")
            if device.metadata:
                print(f"    Metadata: {device.metadata}")
            print()
        
        return True
        
    except ImportError:
        print("BLE support not available. Install bleak:")
        print("  pip install bleak")
        return False
    except Exception as e:
        print(f"BLE scanning failed: {e}")
        return False


async def test_specific_device(device_name):
    """Test connection to a specific device"""
    print(f"Testing connection to: {device_name}")
    print("=" * 40)
    
    try:
        from bleak import BleakScanner, BleakClient
        
        # Clean device name
        device_name = device_name.strip().strip('"').strip("'")
        print(f"Looking for device: '{device_name}'")
        
        # Scan for devices
        print("Scanning...")
        devices = await BleakScanner.discover(timeout=10)
        
        # Find our device
        target_device = None
        for device in devices:
            if device.name and device.name.strip() == device_name:
                target_device = device
                break
        
        if not target_device:
            print(f"Device '{device_name}' not found!")
            print("Available devices:")
            for device in devices:
                if device.name:
                    print(f"  - {device.name}")
            return False
        
        print(f"Found device: {target_device.name}")
        print(f"Address: {target_device.address}")
        # Use advertisement data for RSSI to avoid deprecation warning
        if hasattr(target_device, 'advertisement') and target_device.advertisement:
            print(f"RSSI: {target_device.advertisement.rssi}")
        else:
            print("RSSI: Not available")
        
        # Try to connect
        print("Attempting to connect...")
        client = BleakClient(target_device.address)
        
        try:
            await client.connect()
            print("✓ Successfully connected!")
            
            # Get services
            print("Discovering services...")
            services = client.services
            service_count = len(list(services))
            print(f"Found {service_count} services:")
            
            for service in services:
                print(f"  Service: {service.uuid}")
                print(f"    Description: {service.description}")
                
                # Get characteristics
                for char in service.characteristics:
                    print(f"    Characteristic: {char.uuid}")
                    print(f"      Properties: {char.properties}")
                    print(f"      Description: {char.description}")
            
            # Disconnect
            await client.disconnect()
            print("✓ Disconnected successfully")
            return True
            
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
        
    except Exception as e:
        print(f"Test failed: {e}")
        return False


def load_config():
    """Load configuration from config.ini"""
    config_file = "config.ini"
    if not Path(config_file).exists():
        print(f"Config file {config_file} not found!")
        return None
    
    config = configparser.ConfigParser()
    config.read(config_file)
    return config


async def main():
    """Main test function"""
    print("MeshCore Bot - BLE Connection Test")
    print("=" * 50)
    
    # Check if bleak is available
    try:
        import bleak
        print("✓ BLE support available")
    except ImportError:
        print("✗ BLE support not available")
        print("Install bleak: pip install bleak")
        return
    
    # Load config
    config = load_config()
    if not config:
        return
    
    # Check connection type
    connection_type = config.get('Connection', 'connection_type', fallback='serial')
    if connection_type != 'ble':
        print(f"Connection type is set to '{connection_type}', not 'ble'")
        print("Update config.ini to use BLE connection")
        return
    
    # Get device name
    device_name = config.get('Connection', 'ble_device_name', fallback='')
    if not device_name:
        print("No BLE device name configured!")
        return
    
    print(f"Configured device: {device_name}")
    print()
    
    # Run tests
    print("1. Testing BLE scanning...")
    scan_success = await test_ble_scan()
    print()
    
    if scan_success:
        print("2. Testing specific device connection...")
        device_success = await test_specific_device(device_name)
        print()
        
        if device_success:
            print("✓ All BLE tests passed!")
            print("Your MeshCore node should be ready for the bot.")
        else:
            print("✗ Device connection test failed")
            print("Check that:")
            print("  - Your MeshCore node is powered on")
            print("  - BLE is enabled on the node")
            print("  - The device name is correct")
            print("  - You're close enough to the device")
    else:
        print("✗ BLE scanning failed")
        print("Check that:")
        print("  - BLE is enabled on your computer")
        print("  - You have permission to access BLE")
        print("  - There are BLE devices nearby")


if __name__ == "__main__":
    asyncio.run(main())
