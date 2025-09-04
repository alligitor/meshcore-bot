#!/usr/bin/env python3
"""
Test script to verify MeshCore Bot installation
Run this script to check if all dependencies are installed correctly.
"""

import sys
import importlib
from pathlib import Path


def test_imports():
    """Test if all required modules can be imported"""
    print("Testing imports...")
    
    required_modules = [
        'asyncio',
        'configparser',
        'logging',
        'time',
        're',
        'serial',
        'serial.tools.list_ports',
        'datetime',
        'typing',
        'dataclasses',
        'pathlib',
        'colorlog',
        'schedule',
        'threading'
    ]
    
    optional_modules = [
        'bleak'
    ]
    
    failed_imports = []
    
    # Test required modules
    for module in required_modules:
        try:
            importlib.import_module(module)
            print(f"✓ {module}")
        except ImportError as e:
            print(f"✗ {module} - {e}")
            failed_imports.append(module)
    
    # Test optional modules
    print("\nOptional modules:")
    for module in optional_modules:
        try:
            importlib.import_module(module)
            print(f"✓ {module} (optional)")
        except ImportError:
            print(f"✗ {module} (optional) - not installed")
    
    return failed_imports


def test_bot_modules():
    """Test if bot modules can be imported"""
    print("\nTesting bot modules...")
    
    bot_modules = [
        'meshcore_bot',
        'meshcore_protocol'
    ]
    
    failed_imports = []
    
    for module in bot_modules:
        try:
            importlib.import_module(module)
            print(f"✓ {module}")
        except ImportError as e:
            print(f"✗ {module} - {e}")
            failed_imports.append(module)
    
    return failed_imports


def test_basic_functionality():
    """Test basic bot functionality"""
    print("\nTesting basic functionality...")
    
    try:
        from meshcore_bot import MeshCoreBot
        from meshcore_protocol import MeshCoreProtocol, MeshCoreMessage, MessageType
        
        # Test bot creation
        bot = MeshCoreBot()
        print("✓ Bot creation successful")
        
        # Test protocol creation
        protocol = MeshCoreProtocol()
        print("✓ Protocol creation successful")
        
        # Test message parsing
        test_message = '{"type": "text", "sender": "test", "channel": "general", "content": "test", "hops": 1, "path": "AB"}'
        parsed = protocol.parse_message(test_message)
        if parsed:
            print("✓ Message parsing successful")
        else:
            print("✗ Message parsing failed")
        
        # Test keyword loading
        keywords = bot.load_keywords()
        print(f"✓ Keyword loading successful ({len(keywords)} keywords)")
        
        # Test banned users loading
        banned = bot.load_banned_users()
        print(f"✓ Banned users loading successful ({len(banned)} banned users)")
        
        return True
        
    except Exception as e:
        print(f"✗ Basic functionality test failed: {e}")
        return False


def test_config_file():
    """Test configuration file handling"""
    print("\nTesting configuration file...")
    
    try:
        from meshcore_bot import MeshCoreBot
        
        # Test with non-existent config (should create default)
        test_config = "test_config.ini"
        bot = MeshCoreBot(test_config)
        
        if Path(test_config).exists():
            print("✓ Default config creation successful")
            
            # Clean up
            Path(test_config).unlink()
            print("✓ Test config cleanup successful")
        else:
            print("✗ Default config creation failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Config file test failed: {e}")
        return False


def test_serial_ports():
    """Test serial port detection"""
    print("\nTesting serial port detection...")
    
    try:
        import serial.tools.list_ports
        
        ports = list(serial.tools.list_ports.comports())
        print(f"✓ Found {len(ports)} serial ports:")
        
        for port in ports:
            print(f"  - {port.device}: {port.description}")
        
        return True
        
    except Exception as e:
        print(f"✗ Serial port detection failed: {e}")
        return False


def test_ble_support():
    """Test BLE support"""
    print("\nTesting BLE support...")
    
    try:
        import bleak
        print("✓ BLE support available (bleak installed)")
        return True
    except ImportError:
        print("✗ BLE support not available (bleak not installed)")
        print("  Install with: pip install bleak")
        return False


def main():
    """Run all tests"""
    print("MeshCore Bot Installation Test")
    print("==============================\n")
    
    # Test Python version
    print(f"Python version: {sys.version}")
    if sys.version_info < (3, 7):
        print("⚠ Warning: Python 3.7+ recommended")
    else:
        print("✓ Python version OK")
    
    print()
    
    # Run tests
    failed_imports = test_imports()
    failed_bot_imports = test_bot_modules()
    
    basic_ok = test_basic_functionality()
    config_ok = test_config_file()
    serial_ok = test_serial_ports()
    ble_ok = test_ble_support()
    
    # Summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    
    if not failed_imports and not failed_bot_imports and basic_ok and config_ok:
        print("✓ All core tests passed!")
        print("✓ MeshCore Bot is ready to use")
        
        if serial_ok:
            print("✓ Serial communication ready")
        else:
            print("⚠ Serial communication may have issues")
        
        if ble_ok:
            print("✓ BLE communication ready")
        else:
            print("⚠ BLE communication not available (install bleak)")
        
        print("\nNext steps:")
        print("1. Configure your device in config.ini")
        print("2. Run: python meshcore_bot.py")
        print("3. Or try: python example_usage.py demo")
        
    else:
        print("✗ Some tests failed:")
        
        if failed_imports:
            print(f"  - Missing required modules: {', '.join(failed_imports)}")
            print("    Install with: pip install -r requirements.txt")
        
        if failed_bot_imports:
            print(f"  - Bot modules not found: {', '.join(failed_bot_imports)}")
            print("    Make sure you're in the correct directory")
        
        if not basic_ok:
            print("  - Basic functionality test failed")
        
        if not config_ok:
            print("  - Configuration file test failed")
        
        print("\nPlease fix the issues above before using the bot.")


if __name__ == "__main__":
    main()
