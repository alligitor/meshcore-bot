#!/usr/bin/env python3
"""
Plugin loader for dynamic command discovery and loading
Handles scanning, loading, and registering command plugins
"""

import os
import sys
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional, Type
import logging

from .commands.base_command import BaseCommand


class PluginLoader:
    """Handles dynamic loading and discovery of command plugins"""
    
    def __init__(self, bot, commands_dir: str = None):
        self.bot = bot
        self.logger = bot.logger
        self.commands_dir = commands_dir or os.path.join(os.path.dirname(__file__), 'commands')
        self.loaded_plugins: Dict[str, BaseCommand] = {}
        self.plugin_metadata: Dict[str, Dict[str, Any]] = {}
        self.keyword_mappings: Dict[str, str] = {}  # keyword -> plugin_name
        
    def discover_plugins(self) -> List[str]:
        """Discover all Python files in the commands directory that could be plugins"""
        plugin_files = []
        commands_path = Path(self.commands_dir)
        
        if not commands_path.exists():
            self.logger.error(f"Commands directory does not exist: {self.commands_dir}")
            return plugin_files
        
        # Scan for Python files (excluding __init__.py and base_command.py)
        for file_path in commands_path.glob("*.py"):
            if file_path.name not in ["__init__.py", "base_command.py", "plugin_loader.py"]:
                plugin_files.append(file_path.stem)
        
        self.logger.info(f"Discovered {len(plugin_files)} potential plugin files: {plugin_files}")
        return plugin_files
    
    def load_plugin(self, plugin_name: str) -> Optional[BaseCommand]:
        """Load a single plugin by name"""
        try:
            # Construct the full module path
            module_path = f"modules.commands.{plugin_name}"
            
            # Check if module is already loaded
            if module_path in sys.modules:
                module = sys.modules[module_path]
            else:
                # Import the module
                module = importlib.import_module(module_path)
            
            # Find the command class (should be the only class that inherits from BaseCommand)
            command_class = None
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BaseCommand) and 
                    obj != BaseCommand and 
                    obj.__module__ == module_path):
                    command_class = obj
                    break
            
            if not command_class:
                self.logger.warning(f"No valid command class found in {plugin_name}")
                return None
            
            # Instantiate the command
            plugin_instance = command_class(self.bot)
            
            # Validate plugin metadata
            metadata = plugin_instance.get_metadata()
            if not metadata.get('name'):
                # Use the class name as the plugin name if not specified
                metadata['name'] = command_class.__name__.lower().replace('command', '')
                plugin_instance.name = metadata['name']
            
            self.logger.info(f"Successfully loaded plugin: {metadata['name']} from {plugin_name}")
            return plugin_instance
            
        except Exception as e:
            self.logger.error(f"Failed to load plugin {plugin_name}: {e}")
            return None
    
    def load_all_plugins(self) -> Dict[str, BaseCommand]:
        """Load all discovered plugins"""
        plugin_files = self.discover_plugins()
        loaded_plugins = {}
        
        for plugin_file in plugin_files:
            plugin_instance = self.load_plugin(plugin_file)
            if plugin_instance:
                metadata = plugin_instance.get_metadata()
                plugin_name = metadata['name']
                loaded_plugins[plugin_name] = plugin_instance
                self.plugin_metadata[plugin_name] = metadata
                
                # Build keyword mappings
                self._build_keyword_mappings(plugin_name, metadata)
        
        self.loaded_plugins = loaded_plugins
        self.logger.info(f"Loaded {len(loaded_plugins)} plugins: {list(loaded_plugins.keys())}")
        return loaded_plugins
    
    def _build_keyword_mappings(self, plugin_name: str, metadata: Dict[str, Any]):
        """Build keyword to plugin name mappings"""
        # Map keywords to plugin name
        for keyword in metadata.get('keywords', []):
            self.keyword_mappings[keyword.lower()] = plugin_name
        
        # Map aliases to plugin name
        for alias in metadata.get('aliases', []):
            self.keyword_mappings[alias.lower()] = plugin_name
    
    def get_plugin_by_keyword(self, keyword: str) -> Optional[BaseCommand]:
        """Get a plugin instance by keyword"""
        plugin_name = self.keyword_mappings.get(keyword.lower())
        if plugin_name:
            return self.loaded_plugins.get(plugin_name)
        return None
    
    def get_plugin_by_name(self, name: str) -> Optional[BaseCommand]:
        """Get a plugin instance by name"""
        return self.loaded_plugins.get(name)
    
    def get_all_plugins(self) -> Dict[str, BaseCommand]:
        """Get all loaded plugins"""
        return self.loaded_plugins.copy()
    
    def get_plugin_metadata(self, plugin_name: str = None) -> Dict[str, Any]:
        """Get metadata for a specific plugin or all plugins"""
        if plugin_name:
            return self.plugin_metadata.get(plugin_name, {})
        return self.plugin_metadata.copy()
    
    def get_plugins_by_category(self, category: str) -> Dict[str, BaseCommand]:
        """Get all plugins in a specific category"""
        return {
            name: plugin for name, plugin in self.loaded_plugins.items()
            if plugin.category == category
        }
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a specific plugin"""
        try:
            # Remove from loaded plugins
            if plugin_name in self.loaded_plugins:
                del self.loaded_plugins[plugin_name]
            
            # Remove from metadata
            if plugin_name in self.plugin_metadata:
                del self.plugin_metadata[plugin_name]
            
            # Remove keyword mappings
            keywords_to_remove = []
            for keyword, mapped_name in self.keyword_mappings.items():
                if mapped_name == plugin_name:
                    keywords_to_remove.append(keyword)
            
            for keyword in keywords_to_remove:
                del self.keyword_mappings[keyword]
            
            # Reload the plugin
            plugin_instance = self.load_plugin(plugin_name)
            if plugin_instance:
                metadata = plugin_instance.get_metadata()
                self.loaded_plugins[plugin_name] = plugin_instance
                self.plugin_metadata[plugin_name] = metadata
                self._build_keyword_mappings(plugin_name, metadata)
                self.logger.info(f"Successfully reloaded plugin: {plugin_name}")
                return True
            else:
                self.logger.error(f"Failed to reload plugin: {plugin_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error reloading plugin {plugin_name}: {e}")
            return False
    
    def validate_plugin(self, plugin_instance: BaseCommand) -> List[str]:
        """Validate a plugin instance and return any issues"""
        issues = []
        metadata = plugin_instance.get_metadata()
        
        # Check required metadata
        if not metadata.get('name'):
            issues.append("Plugin missing 'name' metadata")
        
        if not metadata.get('description'):
            issues.append("Plugin missing 'description' metadata")
        
        # Check if execute method is implemented
        if not hasattr(plugin_instance, 'execute'):
            issues.append("Plugin missing 'execute' method")
        
        # Check for keyword conflicts
        for keyword in metadata.get('keywords', []):
            if keyword.lower() in self.keyword_mappings:
                existing_plugin = self.keyword_mappings[keyword.lower()]
                if existing_plugin != metadata['name']:
                    issues.append(f"Keyword '{keyword}' conflicts with plugin '{existing_plugin}'")
        
        return issues


# Import inspect at module level for the load_plugin method
import inspect
