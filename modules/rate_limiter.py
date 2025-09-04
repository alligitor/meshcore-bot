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
