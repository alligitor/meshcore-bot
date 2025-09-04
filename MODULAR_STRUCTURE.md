# MeshCore Bot Modular Structure

The MeshCore Bot has been reorganized into a modular structure for better organization and maintainability. This document describes the new architecture.

## Directory Structure

```
meshcore_bot/
├── meshcore_bot.py              # Main entry point (simplified)
├── modules/                     # Core modules directory
│   ├── __init__.py             # Package initialization
│   ├── core.py                 # Main bot class and core functionality
│   ├── models.py               # Data models (MeshMessage, etc.)
│   ├── rate_limiter.py         # Rate limiting functionality
│   ├── message_handler.py      # Message processing and routing
│   ├── command_manager.py      # Command management and response generation
│   ├── channel_manager.py      # Channel operations and management
│   ├── scheduler.py            # Scheduled message handling
│   └── commands/               # Individual command implementations
│       ├── __init__.py         # Commands package initialization
│       ├── base_command.py     # Base class for all commands
│       ├── test_command.py     # Test command implementation
│       ├── ping_command.py     # Ping command implementation
│       ├── help_command.py     # Help command implementation
│       ├── advert_command.py   # Advert command implementation
│       └── t_phrase_command.py # T-Phrase command implementation
```

## Module Descriptions

### Core Modules

#### `core.py`
- **Purpose**: Main bot class and initialization
- **Responsibilities**: 
  - Configuration loading
  - Connection management (BLE/Serial)
  - Module initialization
  - Startup/shutdown logic
  - Startup advert handling

#### `models.py`
- **Purpose**: Shared data structures
- **Contents**: 
  - `MeshMessage` dataclass for message representation
  - Other shared data models

#### `rate_limiter.py`
- **Purpose**: Message rate limiting
- **Responsibilities**:
  - Prevent spam by limiting message frequency
  - Configurable time intervals
  - Track last message time

#### `message_handler.py`
- **Purpose**: Message processing and routing
- **Responsibilities**:
  - Handle incoming contact messages (DMs)
  - Handle incoming channel messages
  - Extract path information and metadata
  - Route messages to appropriate command handlers
  - Message validation and filtering
  - **Enhanced Signal Quality Extraction**:
    - Extract SNR (Signal-to-Noise Ratio) from multiple sources
    - Extract RSSI (Received Signal Strength Indicator) from multiple sources
    - Cache signal quality data from RF log events
    - Associate signal quality with corresponding messages
  - **Advanced Packet Decoding**:
    - Decode MeshCore packet structure directly from message payloads
    - Extract routing path information (node IDs, path length, route type)
    - Parse packet headers for payload version and type
    - Provide detailed routing information for enhanced responses
    - **Direct extraction** - no time-based association needed

#### `command_manager.py`
- **Purpose**: Command processing and response generation
- **Responsibilities**:
  - Keyword matching
  - Custom syntax processing (e.g., "t phrase")
  - Response formatting with message data
  - Send DMs and channel messages
  - Load configuration for keywords and syntax

#### `channel_manager.py`
- **Purpose**: Channel operations and management
- **Responsibilities**:
  - Fetch channels from MeshCore device
  - Channel name/number mapping
  - Optimized channel fetching (stops at empty channels)

#### `scheduler.py`
- **Purpose**: Scheduled message handling
- **Responsibilities**:
  - Load scheduled messages from config
  - Time-based message scheduling
  - Background scheduler thread

### Command Modules

#### `commands/base_command.py`
- **Purpose**: Base class for all commands
- **Responsibilities**:
  - Define command interface
  - Common command functionality
  - Help text generation
  - Execution validation

#### Individual Command Modules
Each command has its own module implementing the `BaseCommand` interface:

- **`test_command.py`**: Handles "test" keyword responses
- **`ping_command.py`**: Handles "ping" keyword responses  
- **`help_command.py`**: Provides compact, LoRa-optimized help system
- **`advert_command.py`**: Handles "advert" command (DM only, 1-hour cooldown)
- **`t_phrase_command.py`**: Handles "t phrase" custom syntax
- **`at_phrase_command.py`**: Handles "@{string}" custom syntax (DM only)
- **`cmd_command.py`**: Lists available commands in compact format (LoRa-friendly)
- **`hello_command.py`**: Handles various greetings with robot-themed responses

## Benefits of Modular Structure

### 1. **Separation of Concerns**
- Each module has a single, well-defined responsibility
- Easier to understand and maintain individual components
- Clear interfaces between modules

### 2. **Easier Testing**
- Individual modules can be tested in isolation
- Mock dependencies for unit testing
- Better test coverage and debugging

### 3. **Simplified Development**
- New commands can be added by creating new command modules
- Existing functionality can be modified without affecting other modules
- Clear patterns for implementing new features

### 4. **Better Code Organization**
- Related functionality is grouped together
- Easier to find specific code
- Reduced file sizes and complexity

### 5. **Reusability**
- Modules can be reused in other projects
- Common functionality is centralized
- Easier to share code between different bot implementations

## Adding New Commands

To add a new command:

### **Enhanced Signal Quality Monitoring**

The bot now provides comprehensive signal quality information for all incoming messages, including both SNR (Signal-to-Noise Ratio) and RSSI (Received Signal Strength Indicator).

**Signal Quality Data:**
- **SNR**: Signal-to-Noise Ratio in dB (higher is better)
- **RSSI**: Received Signal Strength Indicator in dBm (closer to 0 is stronger)
- **Automatic Extraction**: Bot automatically extracts signal quality from RF log events
- **Smart Caching**: Associates signal quality with messages using pubkey matching
- **Multiple Sources**: Checks payload, metadata, and cached data for signal quality

**Display in Responses:**
- **Test Command**: `Message received from {sender} | {connection_info} | SNR: {snr} dB | RSSI: {rssi} dBm | Received at: {timestamp}`
- **T Phrase**: `ack {sender}: {phrase} | Direct connection (0 hops) | SNR: {snr} dB | RSSI: {rssi} dBm`
- **@ Phrase**: Same format as T Phrase (DM only)

**Technical Implementation:**
- **RF Log Handler**: Processes `RX_LOG_DATA` events to extract SNR and RSSI
- **Dual Cache System**: Separate caches for SNR and RSSI data
- **Pubkey Association**: Links signal quality data to messages using sender pubkey
- **Fallback Handling**: Gracefully handles missing signal quality data
- **Real-time Updates**: Signal quality data is updated with each RF log event

**Configuration:**
Signal quality display is automatically enabled and requires no additional configuration. The bot will show "Unknown" for SNR/RSSI when data is not available.

### **Self-Documenting Help System (LoRa-Optimized)**

The bot now features a compact, self-documenting help system designed for LoRa's 140 character limit. Each command provides its own help text via the `help <command>` syntax.

**Examples:**
- `help` → "Bot Help: test, ping, help, cmd, advert, t phrase, @string | Use 'help <command>' for details" (93 chars)
- `help @` → "Help @: Responds to '@{string}' with ack + connection info (DM only)." (69 chars)
- `help t` → "Help t: Responds to 't phrase' with ack + connection info." (58 chars)
- `help cmd` → "Help cmd: Lists commands in compact format." (43 chars)

**Features:**
- **LoRa Friendly**: All help responses fit within 140 character limit
- **Dynamic Help**: Each command provides its own help text via `get_help_text()` method
- **Command Aliases**: `help @` maps to the `at_phrase` command, `help t` maps to the `t_phrase` command
- **Compact Format**: Optimized for low-bandwidth mesh networks
- **Configurable**: General help response is configurable in `config.ini`
- **Automatic Updates**: New commands automatically appear in help when added

**Configuration:**
The general help response is configurable in `config.ini`:
```ini
[Keywords]
help = "Bot Help: test, ping, help, cmd, advert, t phrase, @string | Use 'help <command>' for details"
```

### **New cmd Command (LoRa-Friendly)**

The bot now includes a `cmd` command that lists all available commands in a compact, comma-separated format designed for LoRa's character limitations.

**Usage:**
- `cmd` → Lists all available commands in a compact format

**Response:**
```
Available commands: test, ping, help, cmd, advert, t phrase, @string
```

**Features:**
- **LoRa Optimized**: Only 68 characters, well within ~140 character limit
- **Compact Format**: Comma-separated list for easy reading
- **Complete Coverage**: Includes all basic commands, custom syntax, and special commands
- **User-Friendly**: Shows actual usage syntax (e.g., "t phrase" instead of "t_phrase")

### **New Hello Command with Robot Greetings**

The bot now includes a fun "hello" command that responds to various greeting variants with robot-themed responses from popular culture.

**Usage:**
- `hello`, `hi`, `hey`, `howdy`, `greetings`, `salutations` → Bot responds with robot greeting

**Response Format:**
```
Hi, I'm {botname}. {random_robot_greeting}
```

**Examples:**
- `hello` → "Hi, I'm HowlBot. Greetings, meat-based organism!"
- `hi` → "Hi, I'm HowlBot. Hello, meatbag!"
- `howdy` → "Hi, I'm HowlBot. Salutations, carbon-based lifeform!"

**Robot Greetings Include:**
- "Greetings, human!"
- "Hello, meatbag!"
- "Salutations, carbon-based lifeform!"
- "Greetings, organic entity!"
- "Hello, biological unit!"
- And 10+ more variations...

**Features:**
- **Multiple Variants**: Responds to 6 different greeting words
- **Random Responses**: Each greeting gets a different robot response (even same word gets different responses)
- **Bot Name Integration**: Uses configured bot name from config.ini
- **Robot Personality**: Fun, sci-fi themed responses
- **LoRa Friendly**: Responses fit within character limits
- **No Config Required**: Randomization is built into the command logic

### **New @{string} Syntax (DM Only)**

The bot now supports a new `@{string}` syntax that works exactly like the existing `t {string}` syntax, but only in direct messages. This makes it easier for users to interact with the bot via DMs.

**Examples:**
- `@hello world` → `ack {sender}: hello world | {connection_info}`
- `@test message` → `ack {sender}: test message | {connection_info}`

**Configuration:**
```ini
[Custom_Syntax]
@_phrase = "ack {sender}: {phrase} | {connection_info}"
```

**Features:**
- **DM Only**: Only works in direct messages, not in channels
- **Same Response Format**: Uses the same response template as `t_phrase`
- **Configurable**: Response format can be customized in `config.ini`
- **Automatic Detection**: Bot automatically detects `@` prefix and processes accordingly

### **Standard Command Addition**

1. **Create a new command module** in `modules/commands/`
2. **Inherit from `BaseCommand`** and implement required methods
3. **Add the command to `CommandManager`** in the `commands` dictionary
4. **Update configuration** if needed

Example:
```python
# modules/commands/weather_command.py
from .base_command import BaseCommand
from ..models import MeshMessage

class WeatherCommand(BaseCommand):
    def get_help_text(self) -> str:
        return "Get current weather information."
    
    async def execute(self, message: MeshMessage) -> bool:
        # Implementation here
        return True
```

## Configuration

The modular structure maintains the same configuration format as before. All settings are loaded through the core module and distributed to appropriate modules as needed.

## Future Enhancements

The modular structure makes it easy to add:

- **Plugin system** for third-party command modules
- **API integrations** in separate modules
- **Advanced message processing** pipelines
- **Multiple bot instances** with different configurations
- **Web interface** for bot management
- **Database integration** for persistent storage

## Migration Notes

- **Existing functionality**: All existing bot features work exactly the same
- **Configuration**: No changes to `config.ini` required
- **API**: External interface remains unchanged
- **Performance**: No performance impact from modularization

## Advanced Packet Decoding and Routing

The bot now implements sophisticated packet decoding to extract detailed routing information directly from incoming message packets, providing the same level of routing detail as the example code you shared.

### Features
- **Raw Packet Decoding**: Decodes MeshCore packet structure from raw hex data
- **Routing Path Extraction**: Extracts actual node IDs and path information from packet headers
- **Route Type Detection**: Identifies direct vs. routed connections from packet headers
- **Payload Analysis**: Parses payload version and type information
- **Enhanced Responses**: Includes detailed routing information in all command responses

### Technical Implementation
- **`decode_meshcore_packet()` Method**: Implements the decoding strategy from your example code
- **Header Parsing**: Extracts path length, route type, payload version, and payload type
- **Path Node Extraction**: Converts raw bytes to readable 2-character hex node IDs
- **Route Classification**: Determines if message is direct or routed based on header bits
- **Message Integration**: Updates message path information with decoded routing data
- **Direct Extraction**: Routing information comes directly from message payloads, no time-based association needed

### Packet Structure Decoding
The bot now decodes the same packet structure as your example:
- **Header Byte**: Contains route type (lower 2 bits), payload type (bits 2-5), and version (bits 6-7)
- **Path Length**: Second byte indicates the number of path bytes
- **Path Bytes**: 2-byte little-endian node IDs representing the routing path
- **Payload**: Remaining data after the path information

### Response Enhancement
All commands now display enhanced connection information including:
- **Connection Type**: Direct (0 hops) or Routed (X hops)
- **Signal Quality**: SNR and RSSI values
- **Routing Details**: Actual node path (e.g., "Route: 01,5f,7e (3 nodes)") or "Direct"
