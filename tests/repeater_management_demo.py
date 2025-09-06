#!/usr/bin/env python3
"""
Repeater Management Demo Script
Demonstrates the repeater contact management functionality
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from modules.repeater_manager import RepeaterManager


class MockBot:
    """Mock bot class for demonstration purposes"""
    
    def __init__(self):
        self.logger = self._create_mock_logger()
    
    def _create_mock_logger(self):
        """Create a mock logger for demonstration"""
        import logging
        logger = logging.getLogger("MockBot")
        logger.setLevel(logging.INFO)
        
        # Create console handler
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger


async def demo_repeater_management():
    """Demonstrate repeater management functionality"""
    print("🔧 Repeater Management System Demo")
    print("=" * 50)
    
    # Create mock bot and repeater manager
    bot = MockBot()
    repeater_manager = RepeaterManager(bot, "demo_repeater_contacts.db")
    
    print("\n1. 📡 Adding sample repeater contacts...")
    
    # Simulate adding some repeater contacts
    sample_contacts = [
        {
            'public_key': '15a24fcbc0dd1234567890abcdef1234567890abcdef1234567890abcdef12',
            'adv_name': 'Hillcrest Repeater',
            'type': 'repeater',
            'name': 'Hillcrest Repeater'
        },
        {
            'public_key': '25b35fddc1ee2345678901bcdef2345678901bcdef2345678901bcdef23456',
            'adv_name': 'Downtown Room Server',
            'type': 'roomserver',
            'name': 'Downtown Room Server'
        },
        {
            'public_key': '35c46feed2ff3456789012cdef3456789012cdef3456789012cdef34567890',
            'adv_name': 'Westside Repeater',
            'type': 'repeater',
            'name': 'Westside Repeater'
        }
    ]
    
    # Add contacts to database (simulating the detection process)
    for contact in sample_contacts:
        # In the real implementation, this would use repeater_manager._is_repeater_device(contact)
        # The detection is now synchronous and LoRa-aware (no network communication needed)
        device_type = 'RoomServer' if 'room' in contact['adv_name'].lower() else 'Repeater'
        
        # Simulate database insertion
        import sqlite3
        with sqlite3.connect(repeater_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO repeater_contacts 
                (public_key, name, device_type, contact_data)
                VALUES (?, ?, ?, ?)
            ''', (
                contact['public_key'],
                contact['adv_name'],
                device_type,
                '{"demo": "sample_contact"}'
            ))
            conn.commit()
    
    print("✅ Added 3 sample repeater contacts")
    
    print("\n2. 📋 Listing all repeater contacts...")
    repeaters = await repeater_manager.get_repeater_contacts(active_only=False)
    for repeater in repeaters:
        status = "🟢 Active" if repeater['is_active'] else "🔴 Purged"
        print(f"   {status} {repeater['name']} ({repeater['device_type']})")
    
    print("\n3. 🗑️ Purging old repeaters (simulating 30+ days old)...")
    # Simulate old timestamps
    import sqlite3
    from datetime import datetime, timedelta
    old_date = (datetime.now() - timedelta(days=35)).isoformat()
    
    with sqlite3.connect(repeater_manager.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE repeater_contacts SET last_seen = ? WHERE name = ?',
            (old_date, 'Hillcrest Repeater')
        )
        conn.commit()
    
    purged_count = await repeater_manager.purge_old_repeaters(days=30, reason="Demo: Auto-purge old repeaters")
    print(f"✅ Purged {purged_count} old repeaters")
    
    print("\n4. 📊 Getting management statistics...")
    stats = await repeater_manager.get_purging_stats()
    print(f"   Total repeaters: {stats.get('total_repeaters', 0)}")
    print(f"   Active repeaters: {stats.get('active_repeaters', 0)}")
    print(f"   Purged repeaters: {stats.get('purged_repeaters', 0)}")
    
    print("\n5. 🔄 Restoring a purged repeater...")
    # Find a purged repeater to restore
    purged_repeaters = [r for r in repeaters if not r['is_active']]
    if purged_repeaters:
        success = await repeater_manager.restore_repeater(
            purged_repeaters[0]['public_key'], 
            "Demo: Manual restore"
        )
        if success:
            print(f"✅ Restored: {purged_repeaters[0]['name']}")
        else:
            print(f"❌ Failed to restore: {purged_repeaters[0]['name']}")
    
    print("\n6. 🧹 Cleaning up demo database...")
    # Clean up the demo database
    Path("demo_repeater_contacts.db").unlink(missing_ok=True)
    print("✅ Demo database cleaned up")
    
    print("\n🎉 Demo completed successfully!")
    print("\nTo use this in your bot:")
    print("1. The RepeaterManager is automatically initialized in your bot")
    print("2. Use the !repeater command to manage repeaters")
    print("3. Run '!repeater scan' to catalog repeaters from your contacts")
    print("4. Run '!repeater list' to see all repeaters")
    print("5. Run '!repeater purge 30' to purge old repeaters")
    print("\nKey Features:")
    print("• LoRa-aware: Uses local contact data for detection (no network overhead)")
    print("• Actually removes contacts from device using remove_contact command")
    print("• 30-second timeouts and batch processing for LoRa communication")
    print("• Maintains audit trail of all operations")
    print("• Provides statistics and monitoring capabilities")


if __name__ == "__main__":
    asyncio.run(demo_repeater_management())
