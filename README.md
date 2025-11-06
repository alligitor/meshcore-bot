# MeshCore Bot

A Python bot that connects to MeshCore mesh networks via serial port or BLE. The bot responds to messages containing configured keywords, executes commands, and provides various data services including weather, solar conditions, and satellite pass information.

## Features

- **Connection Methods**: Serial port or BLE (Bluetooth Low Energy)
- **Keyword Responses**: Configurable keyword-response pairs with template variables
- **Command System**: Plugin-based command architecture with built-in commands
- **Rate Limiting**: Configurable rate limiting to prevent network spam
- **User Management**: Ban/unban users with persistent storage
- **Scheduled Messages**: Send messages at configured times
- **Direct Message Support**: Respond to private messages
- **Logging**: Console and file logging with configurable levels

## Requirements

- Python 3.7+
- MeshCore-compatible device (Heltec V3, RAK Wireless, etc.)
- USB cable or BLE capability

## Installation

### Quick Start (Development)
1. Clone the repository:
```bash
git clone <repository-url>
cd meshcore-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy and configure the bot:
```bash
cp config.ini.example config.ini
# Edit config.ini with your settings
```

4. Run the bot:
```bash
python3 meshcore_bot.py
```

### Production Installation (Systemd Service)
For production deployment as a system service:

1. Install as systemd service:
```bash
sudo ./install-service.sh
```

2. Configure the bot:
```bash
sudo nano /opt/meshcore-bot/config.ini
```

3. Start the service:
```bash
sudo systemctl start meshcore-bot
```

4. Check status:
```bash
sudo systemctl status meshcore-bot
```

See [SERVICE-INSTALLATION.md](SERVICE-INSTALLATION.md) for detailed service installation instructions.

## Configuration

The bot uses `config.ini` for all settings. Key configuration sections:

### Connection
```ini
[Connection]
connection_type = serial          # serial or ble
serial_port = /dev/ttyUSB0        # Serial port path
timeout = 30                      # Connection timeout
```

### Bot Settings
```ini
[Bot]
bot_name = MeshCoreBot            # Bot identification name
enabled = true                    # Enable/disable bot
rate_limit_seconds = 2            # Rate limiting interval
startup_advert = flood            # Send advert on startup
```

### Keywords
```ini
[Keywords]
# Format: keyword = response_template
# Variables: {sender}, {connection_info}, {snr}, {timestamp}, {path}
test = "Message received from {sender} | {connection_info}"
help = "Bot Help: test, ping, help, hello, cmd, wx, aqi, sun, moon, solar, hfcond, satpass, dice, roll, joke, dadjoke, sports, channels, path, prefix, repeater, stats"
```

### Channels
```ini
[Channels]
monitor_channels = general,test,emergency  # Channels to monitor
respond_to_dms = true                      # Enable DM responses
```

### External Data APIs
```ini
[External_Data]
# API keys for external services
n2yo_api_key =                    # Satellite pass data
airnow_api_key =                  # Air quality data
```

### Logging
```ini
[Logging]
log_level = INFO                  # DEBUG, INFO, WARNING, ERROR, CRITICAL
log_file = meshcore_bot.log       # Log file path
colored_output = true             # Enable colored console output
```

## Usage

### Running the Bot

```bash
python meshcore_bot.py
```


### Available Commands

The bot responds to these commands:

**Basic Commands:**
- `test` - Test message response
- `ping` - Ping/pong response
- `help` - Show available commands
- `hello` - Greeting response
- `cmd` - List available commands

**Information Commands:**
- `wx <location>` - Weather information
- `aqi <location>` - Air quality index
- `sun` - Sunrise/sunset times
- `moon` - Moon phase and times
- `solar` - Solar conditions
- `hfcond` - HF band conditions
- `satpass <NORAD>` - Satellite pass information (default: radio passes, all passes above horizon)
- `satpass <NORAD> visual` - Visual passes only (must be visually observable)
- `satpass <shortcut>` - Use shortcuts like `iss`, `hst`, `hubble`, `goes18`, `tiangong`

**Gaming Commands:**
- `dice` - Roll dice (d6 by default, or specify like `dice d20`, `dice 2d6`)
- `roll` - Roll random number (1-100 by default, or specify like `roll 50`)

**Entertainment Commands:**
- `joke` - Get a random joke
- `dadjoke` - Get a dad joke from icanhazdadjoke.com

**Sports Commands:**
- `sports` - Get scores for default teams
- `sports <team>` - Get scores for specific team
- `sports <league>` - Get scores for league (nfl, mlb, nba, etc.)

**MeshCore Network Commands:**
- `channels` - List hashtag channels
- `path` - Decode message routing path
- `prefix <XX>` - Look up repeaters by prefix
- `repeater` - Manage repeater contacts and scan for new ones (DM only)
- `stats` - Show bot usage statistics
- `advert` - Send network advert (DM only)

## Message Response Templates

Keyword responses support these template variables:

- `{sender}` - Sender's node ID
- `{connection_info}` - Connection details (direct/routed)
- `{snr}` - Signal-to-noise ratio
- `{timestamp}` - Message timestamp
- `{path}` - Message routing path

Example:
```ini
[Keywords]
test = "Message received from {sender} | {connection_info}"
ping = "Pong!"
help = "Bot Help: test, ping, help, hello, cmd, wx, aqi, sun, moon, solar, hfcond, satpass, dice, roll, joke, dadjoke, sports, channels, path, prefix, repeater, stats"
```

## Hardware Setup

### Serial Connection

1. Flash MeshCore firmware to your device
2. Connect via USB
3. Configure serial port in `config.ini`:
   ```ini
   [Connection]
   connection_type = serial
   serial_port = /dev/ttyUSB0  # Linux
   # serial_port = COM3        # Windows
   # serial_port = /dev/tty.usbserial-*  # macOS
   ```

### BLE Connection

1. Ensure your MeshCore device supports BLE
2. Configure BLE in `config.ini`:
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
   - List available ports: `python -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"`

2. **BLE Connection Issues**:
   - Ensure device is discoverable
   - Check device name in config
   - Verify BLE permissions

3. **Message Parsing Errors**:
   - Enable DEBUG logging for detailed information
   - Check meshcore library documentation for protocol details

4. **Rate Limiting**:
   - Adjust `rate_limit_seconds` in config
   - Check logs for rate limiting messages

### Debug Mode

Enable debug logging:
```ini
[Logging]
log_level = DEBUG
```

## Architecture

The bot uses a modular plugin architecture:

- **Core modules** (`modules/`): Shared utilities and core functionality
- **Command plugins** (`modules/commands/`): Individual command implementations
- **Plugin loader**: Dynamic discovery and loading of command plugins
- **Message handler**: Processes incoming messages and routes to appropriate handlers

### Adding New Commands

1. Create a new command file in `modules/commands/`
2. Inherit from `BaseCommand`
3. Implement the `execute()` method
4. The plugin loader will automatically discover and load the command

Example:
```python
from .base_command import BaseCommand
from ..models import MeshMessage

class MyCommand(BaseCommand):
    name = "mycommand"
    keywords = ['mycommand']
    description = "My custom command"
    
    async def execute(self, message: MeshMessage) -> bool:
        await self.send_response(message, "Hello from my command!")
        return True
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License.

## Acknowledgments

- [MeshCore Project](https://github.com/meshcore-dev/MeshCore) for the mesh networking protocol
- Some commands adapted from MeshingAround bot by K7MHI Kelly Keeton 2024
