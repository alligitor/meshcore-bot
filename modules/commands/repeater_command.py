#!/usr/bin/env python3
"""
Repeater Management Command
Provides commands to manage repeater contacts and purging operations
"""

import asyncio
from .base_command import BaseCommand
from ..models import MeshMessage
from typing import List, Optional


class RepeaterCommand(BaseCommand):
    """Command for managing repeater contacts"""
    
    # Plugin metadata
    name = "repeater"
    keywords = ["repeater", "repeaters", "rp"]
    description = "Manage repeater contacts and purging operations (DM only)"
    requires_dm = True
    cooldown_seconds = 0
    category = "management"
    
    def __init__(self, bot):
        super().__init__(bot)
    
    def matches_keyword(self, message: MeshMessage) -> bool:
        """Check if message starts with 'repeater' keyword"""
        content = message.content.strip()
        
        # Handle exclamation prefix
        if content.startswith('!'):
            content = content[1:].strip()
        
        # Check if message starts with any of our keywords
        content_lower = content.lower()
        for keyword in self.keywords:
            if content_lower.startswith(keyword + ' '):
                return True
        return False
    
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
                elif subcommand == "status":
                    response = await self._handle_status()
                elif subcommand == "manage":
                    response = await self._handle_manage(args)
                elif subcommand == "add":
                    response = await self._handle_add(args)
                elif subcommand == "discover":
                    response = await self._handle_discover()
                elif subcommand == "auto":
                    response = await self._handle_auto(args)
                elif subcommand == "tst":
                    response = await self._handle_test(args)
                elif subcommand == "locations":
                    response = await self._handle_locations()
                elif subcommand == "help":
                    response = self.get_help()
                else:
                    response = f"Unknown subcommand: {subcommand}\n{self.get_help()}"
                    
            except Exception as e:
                self.logger.error(f"Error in repeater command: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                response = f"Error executing repeater command: {e}"
        
        # Handle multi-message responses (like locations command)
        if isinstance(response, tuple) and response[0] == "multi_message":
            # Send first message
            await self.bot.command_manager.send_response(message, response[1])
            
            # Wait for bot TX rate limiter to allow next message
            import asyncio
            rate_limit = self.bot.config.getfloat('Bot', 'bot_tx_rate_limit_seconds', fallback=1.0)
            # Use a conservative sleep time to avoid rate limiting
            sleep_time = max(rate_limit + 1.0, 2.0)  # At least 2 seconds, or rate_limit + 1 second
            await asyncio.sleep(sleep_time)
            
            # Send second message
            await self.bot.command_manager.send_response(message, response[2])
        else:
            # Send single message as usual
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
            
            # Get more detailed information about what happened
            if cataloged_count > 0:
                return f"✅ Scanned contacts and cataloged {cataloged_count} new repeaters"
            else:
                # Check if there are any repeaters in the database
                repeaters = await self.bot.repeater_manager.get_repeater_contacts(active_only=True)
                if repeaters:
                    return f"✅ Scanned contacts - no new repeaters found, but updated location data for existing {len(repeaters)} repeaters"
                else:
                    return "✅ Scanned contacts - no repeaters found in contact list"
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
            return "Usage: !repeater purge [all|days|name] [reason]\nExamples:\n  !repeater purge all 'Clear all repeaters'\n  !repeater purge all force 'Force clear all repeaters'\n  !repeater purge 30 'Auto-cleanup old repeaters'\n  !repeater purge 'Hillcrest' 'Remove specific repeater'"
        
        try:
            if args[0].lower() == 'all':
                # Check for force flag
                force_purge = len(args) > 1 and args[1].lower() == 'force'
                if force_purge:
                    reason = " ".join(args[2:]) if len(args) > 2 else "Force purge - all repeaters"
                else:
                    reason = " ".join(args[1:]) if len(args) > 1 else "Manual purge - all repeaters"
                
                # Always get repeaters directly from device contacts for purging
                # This ensures we have the correct contact_key for removal
                self.logger.info("Scanning device contacts for repeaters to purge...")
                device_repeaters = []
                if hasattr(self.bot.meshcore, 'contacts'):
                    for contact_key, contact_data in self.bot.meshcore.contacts.items():
                        if self.bot.repeater_manager._is_repeater_device(contact_data):
                            public_key = contact_data.get('public_key', contact_key)
                            name = contact_data.get('adv_name', contact_data.get('name', 'Unknown'))
                            device_repeaters.append({
                                'public_key': public_key,
                                'contact_key': contact_key,  # Include the contact key for removal
                                'name': name,
                                'contact_data': contact_data
                            })
                
                if not device_repeaters:
                    return "❌ No repeaters found on device to purge"
                
                repeaters = device_repeaters
                self.logger.info(f"Found {len(repeaters)} repeaters directly from device contacts")
                
                # Also catalog them in the database for future reference
                cataloged = await self.bot.repeater_manager.scan_and_catalog_repeaters()
                if cataloged > 0:
                    self.logger.info(f"Cataloged {cataloged} new repeaters in database")
                
                # Force a complete refresh of contacts from device after purging
                self.logger.info("Forcing contact list refresh from device to ensure persistence...")
                try:
                    from meshcore_cli.meshcore_cli import next_cmd
                    await asyncio.wait_for(
                        next_cmd(self.bot.meshcore, ["contacts"]),
                        timeout=30.0
                    )
                    self.logger.info("Contact list refreshed from device")
                except Exception as e:
                    self.logger.warning(f"Failed to refresh contact list: {e}")
                
                purged_count = 0
                failed_count = 0
                failed_repeaters = []
                
                for i, repeater in enumerate(repeaters):
                    self.logger.info(f"Purging repeater {i+1}/{len(repeaters)}: {repeater['name']} (force={force_purge})")
                    
                    # Always use the new method that works with contact keys
                    success = await self.bot.repeater_manager.purge_repeater_by_contact_key(
                        repeater['contact_key'], reason
                    )
                    
                    if success:
                        purged_count += 1
                    else:
                        failed_count += 1
                        failed_repeaters.append(repeater['name'])
                    
                    # Add a small delay between purges to avoid overwhelming the device
                    if i < len(repeaters) - 1:
                        await asyncio.sleep(1)
                
                # Final verification: Check if contacts were actually removed from device
                self.logger.info("Performing final verification of contact removal...")
                try:
                    from meshcore_cli.meshcore_cli import next_cmd
                    await asyncio.wait_for(
                        next_cmd(self.bot.meshcore, ["contacts"]),
                        timeout=30.0
                    )
                    
                    # Count remaining repeaters on device
                    remaining_repeaters = 0
                    if hasattr(self.bot.meshcore, 'contacts'):
                        for contact_key, contact_data in self.bot.meshcore.contacts.items():
                            if self.bot.repeater_manager._is_repeater_device(contact_data):
                                remaining_repeaters += 1
                    
                    self.logger.info(f"Final verification: {remaining_repeaters} repeaters still on device")
                    
                except Exception as e:
                    self.logger.warning(f"Final verification failed: {e}")
                
                # Build response message
                purge_type = "Force purged" if force_purge else "Purged"
                response = f"✅ {purge_type} {purged_count}/{len(repeaters)} repeaters"
                if failed_count > 0:
                    response += f"\n❌ Failed to purge {failed_count} repeaters: {', '.join(failed_repeaters[:5])}"
                    if len(failed_repeaters) > 5:
                        response += f" (and {len(failed_repeaters) - 5} more)"
                    if not force_purge:
                        response += f"\n💡 Try '!repeater purge all force' to force remove stubborn repeaters"
                
                return response
                
            elif args[0].isdigit():
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
    
    async def _handle_status(self) -> str:
        """Show contact list status and limits"""
        if not hasattr(self.bot, 'repeater_manager'):
            return "Repeater manager not initialized. Please check bot configuration."
        
        try:
            status = await self.bot.repeater_manager.get_contact_list_status()
            
            if not status:
                return "❌ Failed to get contact list status"
            
            lines = []
            lines.append("📊 **Contact Status**")
            lines.append(f"📱 {status['current_contacts']}/{status['estimated_limit']} ({status['usage_percentage']:.0f}%)")
            lines.append(f"👥 {status['companion_count']} companions, 📡 {status['repeater_count']} repeaters")
            lines.append(f"⏰ {status['stale_contacts_count']} stale contacts")
            
            # Status indicators
            if status['is_at_limit']:
                lines.append("🚨 **CRITICAL**: 95%+ full!")
            elif status['is_near_limit']:
                lines.append("⚠️ **WARNING**: 80%+ full")
            else:
                lines.append("✅ Adequate space")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Error getting contact status: {e}"
    
    async def _handle_manage(self, args: List[str]) -> str:
        """Manage contact list to prevent hitting limits"""
        if not hasattr(self.bot, 'repeater_manager'):
            return "Repeater manager not initialized. Please check bot configuration."
        
        try:
            # Check for --dry-run flag
            dry_run = "--dry-run" in args or "-d" in args
            auto_cleanup = not dry_run
            
            if dry_run:
                # Just show what would be done
                status = await self.bot.repeater_manager.get_contact_list_status()
                if not status:
                    return "❌ Failed to get contact list status"
                
                lines = []
                lines.append("🔍 **Contact List Management (Dry Run)**")
                lines.append("")
                lines.append(f"📊 Current status: {status['current_contacts']}/{status['estimated_limit']} ({status['usage_percentage']:.1f}%)")
                
                if status['is_near_limit']:
                    lines.append("")
                    lines.append("⚠️ **Actions that would be taken:**")
                    if status['stale_contacts']:
                        lines.append(f"   • Remove {min(10, len(status['stale_contacts']))} stale contacts")
                    if status['repeater_count'] > 0:
                        lines.append("   • Remove old repeaters (14+ days)")
                    if status['is_at_limit']:
                        lines.append("   • Aggressive cleanup (7+ day repeaters, 14+ day stale contacts)")
                else:
                    lines.append("✅ No management actions needed")
                
                return "\n".join(lines)
            else:
                # Actually perform management
                result = await self.bot.repeater_manager.manage_contact_list(auto_cleanup=True)
                
                if not result.get('success', False):
                    return f"❌ Contact list management failed: {result.get('error', 'Unknown error')}"
                
                lines = []
                lines.append("🔧 **Contact List Management Results**")
                lines.append("")
                
                status = result['status']
                lines.append(f"📊 Final status: {status['current_contacts']}/{status['estimated_limit']} ({status['usage_percentage']:.1f}%)")
                
                actions = result.get('actions_taken', [])
                if actions:
                    lines.append("")
                    lines.append("✅ **Actions taken:**")
                    for action in actions:
                        lines.append(f"   • {action}")
                else:
                    lines.append("")
                    lines.append("ℹ️ No actions were needed")
                
                return "\n".join(lines)
                
        except Exception as e:
            return f"❌ Error managing contact list: {e}"
    
    async def _handle_add(self, args: List[str]) -> str:
        """Add a discovered contact to the contact list"""
        if not hasattr(self.bot, 'repeater_manager'):
            return "Repeater manager not initialized. Please check bot configuration."
        
        if not args:
            return "❌ Please specify a contact name to add"
        
        try:
            contact_name = args[0]
            public_key = args[1] if len(args) > 1 else None
            reason = " ".join(args[2:]) if len(args) > 2 else "Manual addition"
            
            success = await self.bot.repeater_manager.add_discovered_contact(
                contact_name, public_key, reason
            )
            
            if success:
                return f"✅ Successfully added contact: {contact_name}"
            else:
                return f"❌ Failed to add contact: {contact_name}"
                
        except Exception as e:
            return f"❌ Error adding contact: {e}"
    
    async def _handle_discover(self) -> str:
        """Discover companion contacts"""
        if not hasattr(self.bot, 'repeater_manager'):
            return "Repeater manager not initialized. Please check bot configuration."
        
        try:
            success = await self.bot.repeater_manager.discover_companion_contacts("Manual discovery command")
            
            if success:
                return "✅ Companion contact discovery initiated"
            else:
                return "❌ Failed to initiate companion contact discovery"
                
        except Exception as e:
            return f"❌ Error discovering contacts: {e}"
    
    async def _handle_auto(self, args: List[str]) -> str:
        """Toggle manual contact addition setting"""
        if not hasattr(self.bot, 'repeater_manager'):
            return "Repeater manager not initialized. Please check bot configuration."
        
        if not args:
            return "❌ Please specify 'on' or 'off' for manual contact addition setting"
        
        try:
            setting = args[0].lower()
            reason = " ".join(args[1:]) if len(args) > 1 else "Manual toggle"
            
            if setting in ['on', 'enable', 'true', '1']:
                enabled = True
                setting_text = "enabled"
            elif setting in ['off', 'disable', 'false', '0']:
                enabled = False
                setting_text = "disabled"
            else:
                return "❌ Invalid setting. Use 'on' or 'off'"
            
            success = await self.bot.repeater_manager.toggle_auto_add(enabled, reason)
            
            if success:
                return f"✅ Manual contact addition {setting_text}"
            else:
                return f"❌ Failed to {setting_text} manual contact addition"
                
        except Exception as e:
            return f"❌ Error toggling manual contact addition: {e}"
    
    async def _handle_test(self, args: List[str]) -> str:
        """Test meshcore-cli command functionality"""
        if not hasattr(self.bot, 'repeater_manager'):
            return "Repeater manager not initialized. Please check bot configuration."
        
        try:
            results = await self.bot.repeater_manager.test_meshcore_cli_commands()
            
            lines = []
            lines.append("🧪 **MeshCore-CLI Command Test Results**")
            lines.append("")
            
            if 'error' in results:
                lines.append(f"❌ **ERROR**: {results['error']}")
                return "\n".join(lines)
            
            # Test results
            help_status = "✅ PASS" if results.get('help', False) else "❌ FAIL"
            remove_status = "✅ PASS" if results.get('remove_contact', False) else "❌ FAIL"
            
            lines.append(f"📋 Help command: {help_status}")
            lines.append(f"🗑️ Remove contact command: {remove_status}")
            lines.append("")
            
            if not results.get('remove_contact', False):
                lines.append("⚠️ **WARNING**: remove_contact command not available!")
                lines.append("This means repeater purging will not work properly.")
                lines.append("Check your meshcore-cli installation and device connection.")
            else:
                lines.append("✅ All required commands are available.")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Error testing meshcore-cli commands: {e}"
    
    async def _handle_locations(self) -> str:
        """Show location data status for repeaters"""
        try:
            if not hasattr(self.bot, 'repeater_manager'):
                return "Repeater manager not initialized. Please check bot configuration."
            
            # Get all active repeaters
            repeaters = await self.bot.repeater_manager.get_repeater_contacts(active_only=True)
            
            if not repeaters:
                return "No active repeaters found in database"
            
            # Analyze location data
            total_repeaters = len(repeaters)
            with_coordinates = 0
            with_city = 0
            with_state = 0
            with_country = 0
            no_location = 0
            
            location_examples = []
            
            for repeater in repeaters:
                has_coords = repeater.get('latitude') is not None and repeater.get('longitude') is not None
                has_city = bool(repeater.get('city'))
                has_state = bool(repeater.get('state'))
                has_country = bool(repeater.get('country'))
                
                if has_coords:
                    with_coordinates += 1
                if has_city:
                    with_city += 1
                if has_state:
                    with_state += 1
                if has_country:
                    with_country += 1
                if not (has_coords or has_city or has_state or has_country):
                    no_location += 1
                
                # Collect examples for display
                if len(location_examples) < 3:  # Reduced to 3 examples to fit in message
                    location_parts = []
                    if has_city:
                        location_parts.append(repeater['city'])
                    if has_state:
                        location_parts.append(repeater['state'])
                    if has_country:
                        location_parts.append(repeater['country'])
                    
                    if location_parts:
                        location_examples.append(f"• {repeater['name']}: {', '.join(location_parts)}")
                    elif has_coords:
                        location_examples.append(f"• {repeater['name']}: {repeater['latitude']:.4f}, {repeater['longitude']:.4f}")
                    else:
                        location_examples.append(f"• {repeater['name']}: No location data")
            
            # Build first message (summary)
            summary_lines = [
                f"📍 Repeater Locations ({total_repeaters} total):",
                f"GPS: {with_coordinates} ({with_coordinates/total_repeaters*100:.0f}%)",
                f"City: {with_city} ({with_city/total_repeaters*100:.0f}%)",
                f"State: {with_state} ({with_state/total_repeaters*100:.0f}%)",
                f"Country: {with_country} ({with_country/total_repeaters*100:.0f}%)",
                f"None: {no_location} ({no_location/total_repeaters*100:.0f}%)"
            ]
            
            first_message = "\n".join(summary_lines)
            
            # Build second message (examples) if we have examples
            if location_examples:
                example_lines = ["Examples:"]
                example_lines.extend(location_examples)
                second_message = "\n".join(example_lines)
                
                # Return tuple for multi-message response
                return ("multi_message", first_message, second_message)
            else:
                return first_message
            
        except Exception as e:
            self.logger.error(f"Error getting repeater location status: {e}")
            return f"❌ Error getting location status: {e}"
    
    def get_help(self) -> str:
        """Get help text for the repeater command"""
        return """📡 **Repeater & Contact Management Commands**

**Usage:** `!repeater <subcommand> [options]`

**Repeater Management:**
• `scan` - Scan current contacts and catalog new repeaters
• `list` - List repeater contacts (use `--all` to show purged ones)
• `locations` - Show location data status for repeaters
        • `purge all` - Purge all repeaters
        • `purge all force` - Force purge all repeaters (uses multiple removal methods)
        • `purge <days>` - Purge repeaters older than specified days
        • `purge <name>` - Purge specific repeater by name
• `restore <name>` - Restore a previously purged repeater
• `stats` - Show repeater management statistics

**Contact List Management:**
• `status` - Show contact list status and limits
• `manage` - Manage contact list to prevent hitting limits
• `manage --dry-run` - Show what management actions would be taken
• `add <name> [key]` - Add a discovered contact to contact list
        • `discover` - Discover companion contacts
        • `auto <on|off>` - Toggle manual contact addition setting
        • `test` - Test meshcore-cli command functionality

**Examples:**
• `!repeater scan` - Find and catalog new repeaters
• `!repeater status` - Check contact list capacity
• `!repeater manage` - Auto-manage contact list
• `!repeater manage --dry-run` - Preview management actions
• `!repeater add "John"` - Add contact named John
• `!repeater discover` - Discover new companion contacts
        • `!repeater auto off` - Disable manual contact addition
        • `!repeater test` - Test meshcore-cli commands
        • `!repeater purge all` - Purge all repeaters
        • `!repeater purge all force` - Force purge all repeaters
        • `!repeater purge 30` - Purge repeaters older than 30 days
• `!repeater stats` - Show management statistics

**Note:** This system helps manage both repeater contacts and overall contact list capacity. It automatically removes stale contacts and old repeaters when approaching device limits.

        **Automatic Features:**
        • NEW_CONTACT events are automatically monitored
        • Repeaters are automatically cataloged when discovered
        • Contact list capacity is monitored in real-time
        • `auto_manage_contacts = device`: Device handles auto-addition, bot manages capacity
        • `auto_manage_contacts = bot`: Bot automatically adds companion contacts and manages capacity
        • `auto_manage_contacts = false`: Manual mode - use !repeater commands to manage contacts"""
