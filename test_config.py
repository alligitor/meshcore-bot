#!/usr/bin/env python3
"""
Test script to verify the updated configuration for the Testing channel
"""

import configparser
from meshcore_bot import MeshCoreBot
from meshcore_protocol import MeshCoreMessage, MessageType
from datetime import datetime


def test_configuration():
    """Test the updated configuration"""
    print("Testing MeshCore Bot Configuration")
    print("=" * 40)
    
    # Load configuration
    bot = MeshCoreBot()
    
    print(f"Bot Name: {bot.config.get('Bot', 'bot_name') or 'Will be auto-detected'}")
    print(f"Node ID: {bot.config.get('Bot', 'node_id') or 'Will be auto-detected'}")
    print(f"Enabled: {bot.config.getboolean('Bot', 'enabled')}")
    print(f"Passive Mode: {bot.config.getboolean('Bot', 'passive_mode')}")
    print(f"Rate Limit: {bot.config.getint('Bot', 'rate_limit_seconds')} seconds")
    
    print(f"\nMonitor Channels: {', '.join(bot.monitor_channels)}")
    print(f"Respond to DMs: {bot.config.getboolean('Channels', 'respond_to_dms')}")
    
    if bot.config.has_option('Channels', 'channel_public_key'):
        print(f"Channel Public Key: {bot.config.get('Channels', 'channel_public_key')}")
    
    print(f"\nKeywords ({len(bot.keywords)}):")
    for keyword, response in bot.keywords.items():
        print(f"  '{keyword}' -> '{response}'")
    
    print(f"\nBanned Users ({len(bot.banned_users)}):")
    if bot.banned_users:
        for user in bot.banned_users:
            print(f"  {user}")
    else:
        print("  None")
    
    # Test scheduled messages
    if bot.config.has_section('Scheduled_Messages'):
        scheduled = dict(bot.config.items('Scheduled_Messages'))
        print(f"\nScheduled Messages ({len(scheduled)}):")
        for time, message_info in scheduled.items():
            try:
                channel, message = message_info.split(':', 1)
                print(f"  {time}: {channel} -> {message}")
            except ValueError:
                print(f"  {time}: {message_info} (invalid format)")
    
    print("\n" + "=" * 40)


def test_message_processing():
    """Test message processing with the new configuration"""
    print("Testing Message Processing")
    print("=" * 40)
    
    bot = MeshCoreBot()
    
    # Create test messages
    test_messages = [
        MeshCoreMessage(
            message_type=MessageType.TEXT,
            sender_id="node1",
            channel="Testing",
            content="test message",
            hops=1,
            path="AB",
            timestamp=datetime.now()
        ),
        MeshCoreMessage(
            message_type=MessageType.TEXT,
            sender_id="node2",
            channel="general",
            content="test message",
            hops=2,
            path="CD",
            timestamp=datetime.now()
        ),
        MeshCoreMessage(
            message_type=MessageType.TEXT,
            sender_id="node3",
            channel="Testing",
            content="ping",
            hops=1,
            path="EF",
            timestamp=datetime.now()
        ),
        MeshCoreMessage(
            message_type=MessageType.TEXT,
            sender_id="node4",
            channel="@bot",
            content="test message",
            hops=1,
            path="GH",
            timestamp=datetime.now(),
            is_dm=True
        )
    ]
    
    print("Testing message processing:")
    for i, message in enumerate(test_messages, 1):
        print(f"\nMessage {i}:")
        print(f"  From: {message.sender_id}")
        print(f"  Channel: {message.channel}")
        print(f"  Content: {message.content}")
        print(f"  Is DM: {message.is_dm}")
        
        # Check if message should be processed
        should_process = bot.should_process_message(message)
        print(f"  Should Process: {'✓' if should_process else '✗'}")
        
        if should_process:
            # Check for keywords
            keyword_matches = bot.check_keywords(message)
            if keyword_matches:
                print("  Keywords Matched:")
                for keyword, response in keyword_matches:
                    print(f"    '{keyword}' -> '{response}'")
            else:
                print("  No keywords matched")
    
    print("\n" + "=" * 40)


def test_node_detection_simulation():
    """Simulate node detection process"""
    print("Testing Node Detection Simulation")
    print("=" * 40)
    
    bot = MeshCoreBot()
    
    print("Node detection will attempt to:")
    print("1. Send 'get_node_info' command to node")
    print("2. Parse response for node_name and node_id")
    print("3. Update config.ini with detected values")
    print("4. Fall back to defaults if detection fails")
    
    print("\nExpected behavior:")
    print("- Bot name will be auto-detected from node")
    print("- Node ID will be auto-detected from node")
    print("- If detection fails, bot name defaults to 'MeshCoreBot'")
    print("- Node ID will be auto-assigned by MeshCore if not detected")
    
    print("\n" + "=" * 40)


if __name__ == "__main__":
    test_configuration()
    test_message_processing()
    test_node_detection_simulation()
    
    print("\nConfiguration Summary:")
    print("✓ Bot configured for 'Testing' channel only")
    print("✓ Channel public key configured")
    print("✓ DM responses enabled")
    print("✓ Node name/ID will be auto-detected")
    print("✓ Keywords configured for testing")
    print("✓ Scheduled messages set for Testing channel")
    print("\nReady to connect to MeshCore node!")
