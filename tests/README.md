# MeshCore Bot Tests

This directory contains all test files for the MeshCore Bot project.

## Test Files

### Standard Test Files
- `test_ble_connection.py` - Tests for BLE connection functionality
- `test_channels.py` - Tests for channel management
- `test_config_parsing.py` - Tests for configuration parsing
- `test_config.py` - General configuration tests
- `test_contacts.py` - Tests for contact management
- `test_dynamic_channels.py` - Tests for dynamic channel functionality
- `test_event_structure.py` - Tests for event structure handling
- `test_get_channel.py` - Tests for channel retrieval
- `test_installation.py` - Tests for installation/setup
- `test_meshcore_official.py` - Tests for official meshcore integration
- `test_path_extraction.py` - Tests for path extraction functionality
- `test_path_info.py` - Tests for path information handling

### Utility and Analysis Tools
- `meshcore_packet_analyzer.py` - Packet analysis and testing tool
- `discover_ble_uuids.py` - BLE UUID discovery utility
- `example_usage.py` - Example usage and demo code

## Running Tests

To run tests from the project root:

```bash
# Run a specific test
python3 -m pytest tests/test_config.py

# Run all tests
python3 -m pytest tests/

# Run with verbose output
python3 -m pytest tests/ -v
```

## Running Utility Tools

```bash
# Run packet analyzer
python3 tests/meshcore_packet_analyzer.py

# Run BLE UUID discovery
python3 tests/discover_ble_uuids.py

# Run example usage demo
python3 tests/example_usage.py demo
```

## Note

These test files were moved from the project root to keep the main directory clean and organized.
