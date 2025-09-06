#!/usr/bin/env python3
"""
Repeater Management Command
Provides commands to manage repeater contacts and purging operations
"""

from .base_command import BaseCommand
from ..models import MeshMessage
from typing import List, Optional


class RepeaterCommand(BaseCommand):
    """Command for managing repeater contacts"""
    
    # Plugin metadata
    name = "repeater"
    keywords = ["repeater", "repeaters", "rp"]
    description = "Manage repeater contacts and purging operations"
    aliases = ["repeaters", "rp"]
    requires_dm = False
    cooldown_seconds = 0
    category = "management"
    
    def __init__(self, bot):
        super().__init__(bot)
    
    async def execute(self, message: MeshMessage) -> bool:
        """Execute repeater management command"""
        self.logger.info(f"Repeater command executed with content: {message.content}")
        
        # Parse the message content to extract subcommand and args
        content = message.content.strip()
        parts = content.split()
        
        if len(parts) < 2:
            response = self.get_help()
        else:
            subcommand = parts[1].lower()
            args = parts[2:] if len(parts) > 2 else []
            self.logger.info(f"Repeater subcommand: {subcommand}, args: {args}")
            
            try:
                if subcommand == "scan":
                    response = await self._handle_scan()
                elif subcommand == "list":
                    response = await self._handle_list(args)
                elif subcommand == "purge":
                    response = await self._handle_purge(args)
                elif subcommand == "restore":
                    response = await self._handle_restore(args)
                elif subcommand == "stats":
                    response = await self._handle_stats()
                elif subcommand == "help":
                    response = self.get_help()
                else:
                    response = f"Unknown subcommand: {subcommand}\n{self.get_help()}"
                    
            except Exception as e:
                self.logger.error(f"Error in repeater command: {e}")
                response = f"Error executing repeater command: {e}"
        
        # Send the response
        await self.bot.command_manager.send_response(message, response)
        return True
    
    async def _handle_scan(self) -> str:
        """Scan contacts for repeaters"""
        self.logger.info("Repeater scan command received")
        
        if not hasattr(self.bot, 'repeater_manager'):
            self.logger.error("Repeater manager not found on bot object")
            return "Repeater manager not initialized. Please check bot configuration."
        
        self.logger.info("Repeater manager found, starting scan...")
        
        try:
            cataloged_count = await self.bot.repeater_manager.scan_and_catalog_repeaters()
            self.logger.info(f"Scan completed, cataloged {cataloged_count} repeaters")
            return f"✅ Scanned contacts and cataloged {cataloged_count} new repeaters"
        except Exception as e:
            self.logger.error(f"Error in repeater scan: {e}")
            return f"❌ Error scanning for repeaters: {e}"
    
    async def _handle_list(self, args: List[str]) -> str:
        """List repeater contacts"""
        if not hasattr(self.bot, 'repeater_manager'):
            return "Repeater manager not initialized. Please check bot configuration."
        
        try:
            # Check for --all flag to show purged repeaters too
            show_all = "--all" in args or "-a" in args
            active_only = not show_all
            
            repeaters = await self.bot.repeater_manager.get_repeater_contacts(active_only=active_only)
            
            if not repeaters:
                status = "all" if show_all else "active"
                return f"No {status} repeaters found in database"
            
            # Format the output
            lines = []
            lines.append(f"📡 **Repeater Contacts** ({'All' if show_all else 'Active'}):")
            lines.append("")
            
            for repeater in repeaters:
                status_icon = "🟢" if repeater['is_active'] else "🔴"
                device_icon = "📡" if repeater['device_type'] == 'Repeater' else "🏠"
                
                last_seen = repeater['last_seen']
                if last_seen:
                    # Parse and format the timestamp
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                        last_seen_str = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        last_seen_str = last_seen
                else:
                    last_seen_str = "Unknown"
                
                lines.append(f"{status_icon} {device_icon} **{repeater['name']}**")
                lines.append(f"   Type: {repeater['device_type']}")
                lines.append(f"   Last seen: {last_seen_str}")
                lines.append(f"   Purge count: {repeater['purge_count']}")
                lines.append("")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Error listing repeaters: {e}"
    
    async def _handle_purge(self, args: List[str]) -> str:
        """Purge repeater contacts"""
        if not hasattr(self.bot, 'repeater_manager'):
            return "Repeater manager not initialized. Please check bot configuration."
        
        if not args:
            return "Usage: !repeater purge [days] [reason]\nExample: !repeater purge 30 'Auto-cleanup old repeaters'"
        
        try:
            if args[0].isdigit():
                # Purge old repeaters
                days = int(args[0])
                reason = " ".join(args[1:]) if len(args) > 1 else f"Auto-purge older than {days} days"
                
                purged_count = await self.bot.repeater_manager.purge_old_repeaters(days, reason)
                return f"✅ Purged {purged_count} repeaters older than {days} days"
            else:
                # Purge specific repeater by name (partial match)
                name_pattern = args[0]
                reason = " ".join(args[1:]) if len(args) > 1 else "Manual purge"
                
                # Find repeaters matching the name pattern
                repeaters = await self.bot.repeater_manager.get_repeater_contacts(active_only=True)
                matching_repeaters = [r for r in repeaters if name_pattern.lower() in r['name'].lower()]
                
                if not matching_repeaters:
                    return f"❌ No active repeaters found matching '{name_pattern}'"
                
                if len(matching_repeaters) == 1:
                    # Purge the single match
                    repeater = matching_repeaters[0]
                    success = await self.bot.repeater_manager.purge_repeater_from_contacts(
                        repeater['public_key'], reason
                    )
                    if success:
                        return f"✅ Purged repeater: {repeater['name']}"
                    else:
                        return f"❌ Failed to purge repeater: {repeater['name']}"
                else:
                    # Multiple matches - show options
                    lines = [f"Multiple repeaters found matching '{name_pattern}':"]
                    for i, repeater in enumerate(matching_repeaters, 1):
                        lines.append(f"{i}. {repeater['name']} ({repeater['device_type']})")
                    lines.append("")
                    lines.append("Please be more specific with the name.")
                    return "\n".join(lines)
                    
        except ValueError:
            return "❌ Invalid number of days. Please provide a valid integer."
        except Exception as e:
            return f"❌ Error purging repeaters: {e}"
    
    async def _handle_restore(self, args: List[str]) -> str:
        """Restore purged repeater contacts"""
        if not hasattr(self.bot, 'repeater_manager'):
            return "Repeater manager not initialized. Please check bot configuration."
        
        if not args:
            return "Usage: !repeater restore <name_pattern> [reason]\nExample: !repeater restore 'Hillcrest' 'Manual restore'"
        
        try:
            name_pattern = args[0]
            reason = " ".join(args[1:]) if len(args) > 1 else "Manual restore"
            
            # Find purged repeaters matching the name pattern
            repeaters = await self.bot.repeater_manager.get_repeater_contacts(active_only=False)
            matching_repeaters = [r for r in repeaters if not r['is_active'] and name_pattern.lower() in r['name'].lower()]
            
            if not matching_repeaters:
                return f"❌ No purged repeaters found matching '{name_pattern}'"
            
            if len(matching_repeaters) == 1:
                # Restore the single match
                repeater = matching_repeaters[0]
                success = await self.bot.repeater_manager.restore_repeater(
                    repeater['public_key'], reason
                )
                if success:
                    return f"✅ Restored repeater: {repeater['name']}"
                else:
                    return f"❌ Failed to restore repeater: {repeater['name']}"
            else:
                # Multiple matches - show options
                lines = [f"Multiple purged repeaters found matching '{name_pattern}':"]
                for i, repeater in enumerate(matching_repeaters, 1):
                    lines.append(f"{i}. {repeater['name']} ({repeater['device_type']})")
                lines.append("")
                lines.append("Please be more specific with the name.")
                return "\n".join(lines)
                
        except Exception as e:
            return f"❌ Error restoring repeaters: {e}"
    
    async def _handle_stats(self) -> str:
        """Show repeater management statistics"""
        if not hasattr(self.bot, 'repeater_manager'):
            return "Repeater manager not initialized. Please check bot configuration."
        
        try:
            stats = await self.bot.repeater_manager.get_purging_stats()
            
            lines = []
            lines.append("📊 **Repeater Management Statistics**")
            lines.append("")
            lines.append(f"📡 Total repeaters cataloged: {stats.get('total_repeaters', 0)}")
            lines.append(f"🟢 Active repeaters: {stats.get('active_repeaters', 0)}")
            lines.append(f"🔴 Purged repeaters: {stats.get('purged_repeaters', 0)}")
            lines.append("")
            
            recent_activity = stats.get('recent_activity_7_days', {})
            if recent_activity:
                lines.append("📈 **Recent Activity (7 days):**")
                for action, count in recent_activity.items():
                    action_icon = {"added": "➕", "purged": "➖", "restored": "🔄"}.get(action, "📝")
                    lines.append(f"   {action_icon} {action.title()}: {count}")
            else:
                lines.append("📈 **Recent Activity (7 days):** None")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Error getting statistics: {e}"
    
    def get_help(self) -> str:
        """Get help text for the repeater command"""
        return """📡 **Repeater Management Commands**

**Usage:** `!repeater <subcommand> [options]`

**Subcommands:**
• `scan` - Scan current contacts and catalog new repeaters
• `list` - List repeater contacts (use `--all` to show purged ones)
• `purge <days>` - Purge repeaters older than specified days
• `purge <name>` - Purge specific repeater by name
• `restore <name>` - Restore a previously purged repeater
• `stats` - Show repeater management statistics
• `help` - Show this help message

**Examples:**
• `!repeater scan` - Find and catalog new repeaters
• `!repeater list` - Show active repeaters
• `!repeater list --all` - Show all repeaters (including purged)
• `!repeater purge 30` - Purge repeaters older than 30 days
• `!repeater purge "Hillcrest"` - Purge specific repeater
• `!repeater restore "Hillcrest"` - Restore purged repeater
• `!repeater stats` - Show management statistics

**Note:** This system helps manage repeater contacts that can clutter your device's contact list. Repeaters and room servers typically don't need to be in your contacts for normal operation."""
