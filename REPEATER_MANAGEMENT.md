# Repeater Contact Management System

## Overview

The MeshCore Bot now includes a comprehensive repeater contact management system that addresses the issue where only users in the device's contact list can DM the bot. This system automatically identifies repeaters and room servers, catalogs them in a database, and provides tools to purge them from your contact list periodically.

## Problem Solved

- **Issue**: Repeaters and room servers accumulate in your device's contact list
- **Impact**: Only contacts in the device's contact list can DM the bot
- **Solution**: Automated detection, cataloging, and purging of repeater contacts

## Features

### 🔍 Automatic Detection
- Scans your device's contact list for repeaters and room servers
- **LoRa-aware**: Uses only local contact data to avoid LoRa communication overhead
- Identifies repeaters by checking device role fields (role, device_role, type, mode)
- Analyzes advertisement flags, path information, and telemetry data
- Falls back to name pattern matching with validation

### 📊 Database Management
- **SQLite database** for reliable, lightweight storage
- Tracks repeater metadata (name, public key, device type, timestamps)
- Maintains audit log of all purging operations
- Configurable database location via `repeater_db_path` in config

### 🗑️ Intelligent Purging
- **Actual contact removal** from device using `meshcore-cli remove_contact` command
- **LoRa-aware**: 30-second timeouts and error handling for LoRa communication
- **Batch processing**: Delays between removals to avoid overwhelming the network
- Purge repeaters older than specified days
- Purge specific repeaters by name
- Restore previously purged repeaters (marks for re-discovery)
- Automatic cleanup of old audit logs

### 📈 Statistics & Monitoring
- View total, active, and purged repeater counts
- Track recent purging activity
- Monitor system health and usage

## Usage

### Bot Commands

The system provides a comprehensive `!repeater` command with multiple subcommands:

#### Scan for Repeaters
```
!repeater scan
```
Scans your current contacts and catalogs any new repeaters found.

#### List Repeaters
```
!repeater list              # Show active repeaters
!repeater list --all        # Show all repeaters (including purged)
```

#### Purge Repeaters
```
!repeater purge 30                    # Purge repeaters older than 30 days
!repeater purge "Hillcrest"           # Purge specific repeater by name
!repeater purge 30 "Auto-cleanup"     # Purge with custom reason
```

#### Restore Repeaters
```
!repeater restore "Hillcrest"         # Restore specific repeater
!repeater restore "Hillcrest" "Manual restore"  # Restore with reason
```

#### View Statistics
```
!repeater stats
```
Shows comprehensive statistics about repeater management.

#### Get Help
```
!repeater help
```
Displays detailed help for all repeater commands.

## Configuration

Add the following to your `config.ini` file:

```ini
[Bot]
# ... existing bot settings ...
# Path to repeater contacts database
repeater_db_path = repeater_contacts.db
```

## Database Schema

### repeater_contacts Table
- `id`: Primary key
- `public_key`: Unique repeater public key
- `name`: Repeater name
- `device_type`: 'Repeater' or 'RoomServer'
- `first_seen`: When first cataloged
- `last_seen`: When last seen
- `contact_data`: JSON string of full contact data
- `is_active`: Whether currently active (not purged)
- `purge_count`: Number of times purged

### purging_log Table
- `id`: Primary key
- `timestamp`: When action occurred
- `action`: 'added', 'purged', or 'restored'
- `public_key`: Repeater public key
- `name`: Repeater name
- `reason`: Reason for action

## Implementation Details

### Repeater Detection Logic

The system identifies repeaters using local contact data analysis (LoRa-aware):

1. **Role Fields**: Checks contact data for role fields (role, device_role, type, mode)
2. **Advertisement Flags**: Analyzes flags and advert_flags for repeater indicators
3. **Path Analysis**: Uses out_path_len and path information to identify repeaters
4. **Telemetry Data**: Checks telemetry fields for repeater-specific indicators
5. **Name Validation**: Uses name patterns with validation to avoid false positives
6. **No LoRa Communication**: All detection happens locally to avoid network overhead

### Database Benefits

**SQLite** was chosen because:
- ✅ **Lightweight**: No server setup required
- ✅ **Built-in Python support**: No additional dependencies
- ✅ **ACID compliance**: Reliable data storage
- ✅ **SQL queries**: Easy to query and manage data
- ✅ **Perfect for small-medium datasets**: Ideal for repeater management

### Integration

The system is fully integrated into the bot:
- Automatically initialized when bot starts
- Repeater manager available as `bot.repeater_manager`
- Command automatically loaded via plugin system
- Database path configurable via config file

## Example Workflow

1. **Initial Setup**: Bot starts and initializes repeater manager
2. **Scan**: Run `!repeater scan` to catalog existing repeaters
3. **Monitor**: Use `!repeater list` to see what's been found
4. **Purge**: Run `!repeater purge 30` to remove old repeaters
5. **Restore**: Use `!repeater restore` if you need a repeater back
6. **Statistics**: Check `!repeater stats` for system health

## Files Added

- `modules/repeater_manager.py` - Core repeater management functionality
- `modules/commands/repeater_command.py` - Bot command interface
- `repeater_management_demo.py` - Demonstration script
- `REPEATER_MANAGEMENT.md` - This documentation

## Benefits

1. **Cleaner Contact List**: Actually removes repeater contacts from device using CLI commands
2. **Better DM Functionality**: Only real users can DM the bot (repeaters are removed from contact list)
3. **LoRa-Optimized**: Designed for LoRa networks with timeouts and batch processing
4. **Accurate Detection**: Uses local contact data analysis for reliable identification
5. **Automated Management**: Set-and-forget repeater purging with network awareness
6. **Audit Trail**: Track all purging operations
7. **Flexible Control**: Manual override for specific repeaters
8. **Statistics**: Monitor system usage and health

## Future Enhancements

Potential improvements could include:
- Automatic purging on a schedule
- Integration with meshcore-cli for actual contact removal
- More sophisticated repeater detection algorithms
- Export/import functionality for repeater databases
- Integration with external repeater databases

## Troubleshooting

### Database Issues
- Check file permissions for database location
- Ensure sufficient disk space
- Verify SQLite is available (built into Python)

### Command Not Found
- Ensure `repeater_command.py` is in the `modules/commands/` directory
- Check bot logs for plugin loading errors
- Verify the plugin loader is working correctly

### No Repeaters Found
- Run `!repeater scan` to catalog repeaters
- Check if your contacts have device role information in their contact data
- Verify contact data contains role fields, flags, or path information
- Check bot logs for any detection errors

### LoRa Communication Issues
- The system uses 30-second timeouts for LoRa commands
- Batch processing adds 2-second delays between contact removals
- If commands timeout, the system continues with database operations
- Check bot logs for timeout warnings or command errors

## Support

For issues or questions about the repeater management system:
1. Check the bot logs for error messages
2. Run `!repeater stats` to check system status
3. Use `!repeater help` for command reference
4. Review this documentation for configuration options
