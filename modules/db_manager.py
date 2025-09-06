#!/usr/bin/env python3
"""
Generalized Database Manager
Provides common database operations and table management for the MeshCore Bot
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path


class DBManager:
    """Generalized database manager for common operations"""
    
    def __init__(self, bot, db_path: str = "meshcore_bot.db"):
        self.bot = bot
        self.logger = bot.logger
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create geocoding_cache table for weather command optimization
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS geocoding_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query TEXT UNIQUE NOT NULL,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )
                ''')
                
                # Create generic cache table for other caching needs
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS generic_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cache_key TEXT UNIQUE NOT NULL,
                        cache_value TEXT NOT NULL,
                        cache_type TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_geocoding_query ON geocoding_cache(query)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_geocoding_expires ON geocoding_cache(expires_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_generic_key ON generic_cache(cache_key)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_generic_type ON generic_cache(cache_type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_generic_expires ON generic_cache(expires_at)')
                
                conn.commit()
                self.logger.info("Database manager initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    # Geocoding cache methods
    def get_cached_geocoding(self, query: str) -> Tuple[Optional[float], Optional[float]]:
        """Get cached geocoding result for a query"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT latitude, longitude FROM geocoding_cache 
                    WHERE query = ? AND expires_at > datetime('now')
                ''', (query,))
                result = cursor.fetchone()
                if result:
                    return result[0], result[1]
                return None, None
        except Exception as e:
            self.logger.error(f"Error getting cached geocoding: {e}")
            return None, None
    
    def cache_geocoding(self, query: str, latitude: float, longitude: float, cache_hours: int = 24):
        """Cache geocoding result for future use"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO geocoding_cache 
                    (query, latitude, longitude, expires_at) 
                    VALUES (?, ?, ?, datetime('now', '+{} hours'))
                '''.format(cache_hours), (query, latitude, longitude))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error caching geocoding: {e}")
    
    # Generic cache methods
    def get_cached_value(self, cache_key: str, cache_type: str) -> Optional[str]:
        """Get cached value for a key and type"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT cache_value FROM generic_cache 
                    WHERE cache_key = ? AND cache_type = ? AND expires_at > datetime('now')
                ''', (cache_key, cache_type))
                result = cursor.fetchone()
                if result:
                    return result[0]
                return None
        except Exception as e:
            self.logger.error(f"Error getting cached value: {e}")
            return None
    
    def cache_value(self, cache_key: str, cache_value: str, cache_type: str, cache_hours: int = 24):
        """Cache a value for future use"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO generic_cache 
                    (cache_key, cache_value, cache_type, expires_at) 
                    VALUES (?, ?, ?, datetime('now', '+{} hours'))
                '''.format(cache_hours), (cache_key, cache_value, cache_type))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error caching value: {e}")
    
    def get_cached_json(self, cache_key: str, cache_type: str) -> Optional[Dict]:
        """Get cached JSON value for a key and type"""
        cached_value = self.get_cached_value(cache_key, cache_type)
        if cached_value:
            try:
                return json.loads(cached_value)
            except json.JSONDecodeError:
                self.logger.warning(f"Failed to decode cached JSON for {cache_key}")
                return None
        return None
    
    def cache_json(self, cache_key: str, cache_value: Dict, cache_type: str, cache_hours: int = 24):
        """Cache a JSON value for future use"""
        try:
            json_str = json.dumps(cache_value)
            self.cache_value(cache_key, json_str, cache_type, cache_hours)
        except Exception as e:
            self.logger.error(f"Error caching JSON value: {e}")
    
    # Cache cleanup methods
    def cleanup_expired_cache(self):
        """Remove expired cache entries from all cache tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clean up geocoding cache
                cursor.execute("DELETE FROM geocoding_cache WHERE expires_at < datetime('now')")
                geocoding_deleted = cursor.rowcount
                
                # Clean up generic cache
                cursor.execute("DELETE FROM generic_cache WHERE expires_at < datetime('now')")
                generic_deleted = cursor.rowcount
                
                conn.commit()
                
                total_deleted = geocoding_deleted + generic_deleted
                if total_deleted > 0:
                    self.logger.info(f"Cleaned up {total_deleted} expired cache entries ({geocoding_deleted} geocoding, {generic_deleted} generic)")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up expired cache: {e}")
    
    def cleanup_geocoding_cache(self):
        """Remove expired geocoding cache entries"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM geocoding_cache WHERE expires_at < datetime('now')")
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    self.logger.info(f"Cleaned up {deleted_count} expired geocoding cache entries")
        except Exception as e:
            self.logger.error(f"Error cleaning up geocoding cache: {e}")
    
    # Database maintenance methods
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Geocoding cache stats
                cursor.execute('SELECT COUNT(*) FROM geocoding_cache')
                stats['geocoding_cache_entries'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM geocoding_cache WHERE expires_at > datetime('now')")
                stats['geocoding_cache_active'] = cursor.fetchone()[0]
                
                # Generic cache stats
                cursor.execute('SELECT COUNT(*) FROM generic_cache')
                stats['generic_cache_entries'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM generic_cache WHERE expires_at > datetime('now')")
                stats['generic_cache_active'] = cursor.fetchone()[0]
                
                # Cache type breakdown
                cursor.execute('''
                    SELECT cache_type, COUNT(*) FROM generic_cache 
                    WHERE expires_at > datetime('now')
                    GROUP BY cache_type
                ''')
                stats['cache_types'] = dict(cursor.fetchall())
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Error getting database stats: {e}")
            return {}
    
    def vacuum_database(self):
        """Optimize database by reclaiming unused space"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("VACUUM")
                self.logger.info("Database vacuum completed")
        except Exception as e:
            self.logger.error(f"Error vacuuming database: {e}")
    
    # Table management methods
    def create_table(self, table_name: str, schema: str):
        """Create a custom table with the given schema"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f'CREATE TABLE IF NOT EXISTS {table_name} ({schema})')
                conn.commit()
                self.logger.info(f"Created table: {table_name}")
        except Exception as e:
            self.logger.error(f"Error creating table {table_name}: {e}")
    
    def drop_table(self, table_name: str):
        """Drop a table (use with caution)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f'DROP TABLE IF EXISTS {table_name}')
                conn.commit()
                self.logger.info(f"Dropped table: {table_name}")
        except Exception as e:
            self.logger.error(f"Error dropping table {table_name}: {e}")
    
    def execute_query(self, query: str, params: Tuple = ()) -> List[Dict]:
        """Execute a custom query and return results as list of dictionaries"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Error executing query: {e}")
            return []
    
    def execute_update(self, query: str, params: Tuple = ()) -> int:
        """Execute an update/insert/delete query and return number of affected rows"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            self.logger.error(f"Error executing update: {e}")
            return 0
