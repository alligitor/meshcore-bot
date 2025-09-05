#!/usr/bin/env python3
"""
Test script to verify the race condition fixes in RF data correlation
"""

import asyncio
import time
import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.message_handler import MessageHandler
from modules.core import MeshCoreBot
import configparser

class MockBot:
    """Mock bot for testing"""
    def __init__(self):
        self.logger = self
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.channel_manager = MockChannelManager()
    
    def info(self, msg):
        print(f"INFO: {msg}")
    
    def debug(self, msg):
        print(f"DEBUG: {msg}")
    
    def warning(self, msg):
        print(f"WARNING: {msg}")
    
    def error(self, msg):
        print(f"ERROR: {msg}")

class MockChannelManager:
    """Mock channel manager"""
    def get_channel_name(self, channel_idx):
        return f"TestChannel{channel_idx}"

async def test_race_condition_fix():
    """Test the race condition fixes"""
    print("Testing RF Data Correlation Race Condition Fixes")
    print("=" * 50)
    
    # Create mock bot and message handler
    bot = MockBot()
    handler = MessageHandler(bot)
    
    print(f"RF Data Timeout: {handler.rf_data_timeout}s")
    print(f"Message Timeout: {handler.message_timeout}s")
    print(f"Enhanced Correlation: {handler.enhanced_correlation}")
    print()
    
    # Test 1: Basic RF data storage and retrieval
    print("Test 1: Basic RF data storage and retrieval")
    import time
    current_time = time.time()
    
    # Simulate RF data
    rf_data = {
        'timestamp': current_time,
        'pubkey_prefix': 'f2981503387e5fd5dfaeeb0cdb920b2c409387a92d77a5dc8706',
        'snr': -3.5,
        'rssi': -104,
        'raw_hex': 'f2981503387e5fd5dfaeeb0cdb920b2c409387a92d77a5dc8706',
        'payload': '1503387e5fd5dfaeeb0cdb920b2c409387a92d77a5dc8706',
        'payload_length': 24,
        'routing_info': {
            'path_length': 3,
            'path_hex': '387e5f',
            'path_nodes': ['38', '7e', '5f'],
            'route_type': 'ROUTE_TYPE_DIRECT',
            'transport_size': 2,
            'payload_type': 'CHANNEL_ACK'
        }
    }
    
    # Store RF data
    handler.recent_rf_data.append(rf_data)
    handler.rf_data_by_timestamp[current_time] = rf_data
    handler.rf_data_by_pubkey[rf_data['pubkey_prefix']] = [rf_data]
    
    # Test immediate correlation
    found_data = handler.find_recent_rf_data(rf_data['pubkey_prefix'])
    if found_data:
        print("✅ Immediate correlation successful")
        print(f"   Found SNR: {found_data['snr']}, RSSI: {found_data['rssi']}")
    else:
        print("❌ Immediate correlation failed")
    
    print()
    
    # Test 2: Message correlation system
    print("Test 2: Message correlation system")
    
    # Simulate a message payload
    message_payload = {
        'channel_idx': 1,
        'text': 'Jade: Test',
        'pubkey_prefix': 'f2981503387e5fd5dfaeeb0cdb920b2c409387a92d77a5dc8706',
        'path_len': 3
    }
    
    # Store message for correlation
    message_id = f"test_{int(time.time() * 1000)}"
    handler.store_message_for_correlation(message_id, message_payload)
    
    # Try to correlate
    correlated_data = handler.correlate_message_with_rf_data(message_id)
    if correlated_data:
        print("✅ Message correlation successful")
        print(f"   Correlated SNR: {correlated_data['snr']}, RSSI: {correlated_data['rssi']}")
    else:
        print("❌ Message correlation failed")
    
    print()
    
    # Test 3: Extended timeout correlation
    print("Test 3: Extended timeout correlation")
    
    # Create older RF data (within extended timeout)
    older_time = current_time - 20  # 20 seconds ago
    older_rf_data = {
        'timestamp': older_time,
        'pubkey_prefix': 'f2981503387e5fd5dfaeeb0cdb920b2c409387a92d77a5dc8706',
        'snr': -5.0,
        'rssi': -110,
        'raw_hex': 'f2981503387e5fd5dfaeeb0cdb920b2c409387a92d77a5dc8706',
        'payload': '1503387e5fd5dfaeeb0cdb920b2c409387a92d77a5dc8706',
        'payload_length': 24,
        'routing_info': None
    }
    
    handler.recent_rf_data.append(older_rf_data)
    
    # Test with extended timeout
    extended_data = handler.find_recent_rf_data('f2981503387e5fd5dfaeeb0cdb920b2c409387a92d77a5dc8706', max_age_seconds=30.0)
    if extended_data:
        print("✅ Extended timeout correlation successful")
        print(f"   Found SNR: {extended_data['snr']}, RSSI: {extended_data['rssi']}")
    else:
        print("❌ Extended timeout correlation failed")
    
    print()
    
    # Test 4: Partial pubkey matching
    print("Test 4: Partial pubkey matching")
    
    # Test with partial pubkey
    partial_pubkey = 'f2981503387e5fd5'  # First 16 characters
    partial_data = handler.find_recent_rf_data(partial_pubkey)
    if partial_data:
        print("✅ Partial pubkey matching successful")
        print(f"   Found SNR: {partial_data['snr']}, RSSI: {partial_data['rssi']}")
    else:
        print("❌ Partial pubkey matching failed")
    
    print()
    
    # Test 5: Cleanup functionality
    print("Test 5: Cleanup functionality")
    
    # Add some old pending messages
    old_time = time.time() - 15  # 15 seconds ago
    handler.pending_messages['old_message'] = {
        'data': message_payload,
        'timestamp': old_time,
        'processed': False
    }
    
    print(f"Pending messages before cleanup: {len(handler.pending_messages)}")
    handler.cleanup_old_messages()
    print(f"Pending messages after cleanup: {len(handler.pending_messages)}")
    
    if len(handler.pending_messages) == 1:  # Only the test message should remain
        print("✅ Cleanup functionality working")
    else:
        print("❌ Cleanup functionality failed")
    
    print()
    print("Race Condition Fix Tests Complete!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_race_condition_fix())
