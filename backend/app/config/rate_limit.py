from slowapi import Limiter
from slowapi.util import get_remote_address

# Global rate limiter using in-memory storage (can be swapped for Redis if needed later)
# We use client IP address as the key for limiting
limiter = Limiter(key_func=get_remote_address)
