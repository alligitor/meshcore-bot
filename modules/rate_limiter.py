#!/usr/bin/env python3
"""
Rate limiting functionality for the MeshCore Bot
Controls how often messages can be sent to prevent spam
"""

import time


class RateLimiter:
    """Rate limiting for message sending"""
    
    def __init__(self, seconds: int):
        self.seconds = seconds
        self.last_send = 0
    
    def can_send(self) -> bool:
        """Check if we can send a message"""
        return time.time() - self.last_send >= self.seconds
    
    def time_until_next(self) -> float:
        """Get time until next allowed send"""
        elapsed = time.time() - self.last_send
        return max(0, self.seconds - elapsed)
    
    def record_send(self):
        """Record that we sent a message"""
        self.last_send = time.time()


class BotTxRateLimiter:
    """Rate limiting for bot transmission to prevent network overload"""
    
    def __init__(self, seconds: float = 1.0):
        self.seconds = seconds
        self.last_tx = 0
    
    def can_tx(self) -> bool:
        """Check if bot can transmit a message"""
        return time.time() - self.last_tx >= self.seconds
    
    def time_until_next_tx(self) -> float:
        """Get time until next allowed transmission"""
        elapsed = time.time() - self.last_tx
        return max(0, self.seconds - elapsed)
    
    def record_tx(self):
        """Record that bot transmitted a message"""
        self.last_tx = time.time()
    
    async def wait_for_tx(self):
        """Wait until bot can transmit (async)"""
        import asyncio
        while not self.can_tx():
            wait_time = self.time_until_next_tx()
            if wait_time > 0:
                await asyncio.sleep(wait_time + 0.05)  # Small buffer
