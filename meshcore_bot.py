#!/usr/bin/env python3
"""
MeshCore Bot using the official meshcore package
This version uses a modular structure for better organization
"""

import asyncio
import signal
import sys

# Import the modular bot
from modules.core import MeshCoreBot


if __name__ == "__main__":
    bot = MeshCoreBot()
    
    def signal_handler(sig, frame):
        print("\nShutting down...")
        asyncio.create_task(bot.stop())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        asyncio.run(bot.stop())



