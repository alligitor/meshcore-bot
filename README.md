# MeshCore Bot Framework

A Python framework for creating bots that connect to MeshCore networks via serial port or BLE. This bot can respond to messages containing specific keywords, manage user bans, send scheduled messages, and support future integrations with external data sources like weather and tide APIs.

## Features

- **Multi-Protocol Support**: Connect via serial port or Bluetooth Low Energy (BLE)
- **Keyword Response System**: Configurable keyword-response pairs with template variables
- **Rate Limiting**: Configurable rate limiting to prevent spam
- **User Management**: Ban/unban users with persistent configuration
- **Scheduled Messages**: Send messages at specific times
- **DM Support**: Respond to direct messages
- **Comprehensive Logging**: Colored console output and file logging
- **CLI Interface**: Interactive and command-line management tools
- **Extensible Architecture**: Easy to add new features and integrations

## Requirements

- Python 3.7+
- MeshCore-compatible device (Heltec V3, RAK Wireless, etc.)
- USB cable or BLE capability

## Installation

1. Clone or download this repository:
```bash
git clone <repository-url>
cd meshcore-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the bot by editing `config.ini` (a default config will be created if it doesn't exist)

## Configuration

The bot uses a `config.ini` file for all settings. Here's an overview of the configuration sections:

### Connection Settings
```ini
[Connection]
connection_type = serial          # serial or ble
serial_port = /dev/ttyUSB0        # Serial port path
serial_baudrate = 115200          # Baud rate
ble_device_name = MeshCore        # BLE device name
timeout = 30                      # Connection timeout
```

### Bot Settings
```ini
[Bot]
bot_name = MeshCoreBot            # Bot identification name
node_id =                         # Leave empty for auto-assignment
enabled = true                    # Enable/disable bot
passive_mode = false              # Only listen, don't respond
rate_limit_seconds = 10           # Rate limiting interval
```

### Keywords and Responses
```ini
[Keywords]
# Format: keyword = response_template
# Available variables: {hops}, {path}, {sender}, {channel}, {content}, {timestamp}
test = "Message received! Hops: {hops}, Path: {path}, From: {sender}"
weather = "Weather info: {content}"
help = "Available commands: test, weather, help"
```

### Channel Management
```ini
[Channels]
monitor_channels = general,test,emergency  # Channels to monitor
respond_to_dms = true                      # Enable DM responses
```

### User Management
```ini
[Banned_Users]
banned_users = user1,user2                 # Comma-separated list
```

### Scheduled Messages
```ini
[Scheduled_Messages]
# Format: time = channel:message
08:00 = general:Good morning! Weather update coming soon.
12:00 = general:Lunch time reminder
18:00 = general:Evening update
```

### Logging
```ini
[Logging]
log_level = INFO                  # DEBUG, INFO, WARNING, ERROR, CRITICAL
log_file = meshcore_bot.log       # Log file path (empty for console only)
colored_output = true             # Enable colored console output
```

## Usage

### Running the Bot

1. **Basic Usage**:
```bash
python meshcore_bot.py
```

2. **With custom config**:
```bash
python meshcore_bot.py --config my_config.ini
```

### CLI Management

The bot includes a comprehensive CLI for management:

1. **Interactive Mode**:
```bash
python bot_cli.py --interactive
```

2. **Command Line Mode**:
```bash
# Show bot status
python bot_cli.py status

# Add a keyword
python bot_cli.py keywords add "hello" "Hello there! How can I help?"

# Ban a user
python bot_cli.py users ban "spam_user"

# Send a message
python bot_cli.py send general "Hello everyone!"

# Add scheduled message
python bot_cli.py schedule add "09:00" general "Good morning!"
```

### Interactive CLI Commands

When running in interactive mode, you can use these commands:

- `status` - Show bot status and configuration
- `keywords` - List all keyword-response pairs
- `add-keyword <keyword> <response>` - Add new keyword
- `remove-keyword <keyword>` - Remove keyword
- `ban <user_id>` - Ban a user
- `unban <user_id>` - Unban a user
- `banned` - List banned users
- `send <channel> <message>` - Send message to channel
- `schedule` - List scheduled messages
- `add-schedule <time> <channel> <message>` - Add scheduled message
- `remove-schedule <time>` - Remove scheduled message
- `help` - Show help
- `quit` or `exit` - Exit CLI

## Message Response Templates

When configuring keyword responses, you can use these template variables:

- `{hops}` - Number of hops the message traveled
- `{path}` - Two-character path identifiers
- `{sender}` - Sender's node ID
- `{channel}` - Channel name
- `{content}` - Original message content
- `{timestamp}` - Message timestamp

Example:
```ini
[Keywords]
test = "Message received! Hops: {hops}, Path: {path}, From: {sender}"
weather = "Weather for {sender}: {content}"
echo = "You said: {content}"
```

## Protocol Adaptation

The bot includes a flexible protocol adapter that can handle multiple message formats:

1. **JSON Format** (preferred):
```json
{
  "type": "text",
  "sender": "node1",
  "channel": "general",
  "content": "Hello world",
  "hops": 2,
  "path": "AB",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

2. **Pipe-Separated Format**:
```
MSG|node1|general|Hello world|2|AB|msg_001|2024-01-01T12:00:00Z
```

3. **Space-Separated Format**:
```
MSG node1 general Hello world 2 AB
```

## Hardware Setup

### Heltec V3 Setup

1. Flash MeshCore firmware to your Heltec V3 device using the [MeshCore Flasher](https://flasher.meshcore.co.uk)
2. Connect the device via USB
3. Update the `config.ini` with the correct serial port:
   ```ini
   [Connection]
   connection_type = serial
   serial_port = /dev/ttyUSB0  # Linux
   # serial_port = COM3        # Windows
   # serial_port = /dev/tty.usbserial-*  # macOS
   ```

### BLE Setup

1. Ensure your MeshCore device supports BLE
2. Update the `config.ini`:
   ```ini
   [Connection]
   connection_type = ble
   ble_device_name = MeshCore
   ```

## Troubleshooting

### Common Issues

1. **Serial Port Not Found**:
   - Check device connection
   - Verify port name in config
   - Try listing available ports: `python -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"`

2. **BLE Connection Issues**:
   - Ensure device is discoverable
   - Check device name in config
   - Verify BLE permissions on your system

3. **Message Parsing Errors**:
   - Check the protocol format in `meshcore_protocol.py`
   - Verify message format from your MeshCore device
   - Enable DEBUG logging for detailed information

4. **Rate Limiting**:
   - Adjust `rate_limit_seconds` in config
   - Check logs for rate limiting messages

### Debug Mode

Enable debug logging for detailed information:
```ini
[Logging]
log_level = DEBUG
```

## Extending the Bot

### Adding External Data Sources

The bot is designed to be easily extended. To add weather or tide data:

1. Create a new module (e.g., `weather_integration.py`)
2. Implement data fetching functions
3. Add configuration options to `config.ini`
4. Integrate with the main bot class

Example weather integration:
```python
class WeatherIntegration:
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def get_weather(self, location: str) -> str:
        # Implement weather API call
        return f"Weather for {location}: Sunny, 22°C"
```

### Custom Message Handlers

You can extend the message processing by adding custom handlers:

```python
class CustomMessageHandler:
    def __init__(self, bot):
        self.bot = bot
    
    async def handle_message(self, message: MeshMessage):
        # Custom message processing logic
        if "custom_command" in message.content:
            await self.bot.send_message(message.channel, "Custom response!")
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [MeshCore Project](https://github.com/meshcore-dev/MeshCore) for the mesh networking protocol
- The MeshCore community for documentation and examples

## Support

- Check the [MeshCore documentation](https://github.com/meshcore-dev/MeshCore)
- Join the MeshCore Discord for community support
- Open an issue on this repository for bug reports or feature requests
