#!/usr/bin/env python3
"""
MeshCore Protocol Implementation
Based on the actual MeshCore packet.h specification
"""

import struct
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any
import hashlib


class MessageType(Enum):
    """Message types for compatibility"""
    TEXT = "text"
    JSON = "json"
    PIPE = "pipe"
    BINARY = "binary"


class PayloadType(Enum):
    """MeshCore payload types from packet.h"""
    REQ = 0x00
    RESPONSE = 0x01
    TXT_MSG = 0x02
    ACK = 0x03
    ADVERT = 0x04
    GRP_TXT = 0x05
    GRP_DATA = 0x06
    ANON_REQ = 0x07
    PATH = 0x08
    TRACE = 0x09
    MULTIPART = 0x0A
    RAW_CUSTOM = 0x0F


class RouteType(Enum):
    """MeshCore route types from packet.h"""
    TRANSPORT_FLOOD = 0x00
    FLOOD = 0x01
    DIRECT = 0x02
    TRANSPORT_DIRECT = 0x03


class PayloadVersion(Enum):
    """MeshCore payload versions from packet.h"""
    VER_1 = 0x00  # 1-byte src/dest hashes, 2-byte MAC
    VER_2 = 0x01  # FUTURE
    VER_3 = 0x02  # FUTURE
    VER_4 = 0x03  # FUTURE


@dataclass
class MeshCoreMessage:
    """Parsed MeshCore message"""
    content: str
    message_type: MessageType
    sender_id: Optional[str] = None
    channel: Optional[str] = None
    hops: Optional[int] = None
    path: Optional[List[str]] = None
    payload_type: Optional[PayloadType] = None
    route_type: Optional[RouteType] = None
    payload_version: Optional[PayloadVersion] = None
    transport_codes: Optional[List[int]] = None
    raw_data: Optional[bytes] = None
    timestamp: Optional[int] = None
    is_dm: bool = False


@dataclass
class MeshCorePacket:
    """Parsed MeshCore packet structure"""
    header: int
    route_type: RouteType
    payload_type: PayloadType
    payload_version: PayloadVersion
    transport_codes: List[int]
    path: bytes
    path_len: int
    payload: bytes
    payload_len: int
    raw_data: bytes
    
    def get_snr(self) -> float:
        """Get SNR value (if available)"""
        # This would need to be implemented based on how SNR is stored
        return 0.0


class MeshCoreProtocol:
    """MeshCore protocol parser and formatter"""
    
    # Constants from packet.h
    PH_ROUTE_MASK = 0x03
    PH_TYPE_SHIFT = 2
    PH_TYPE_MASK = 0x0F
    PH_VER_SHIFT = 6
    PH_VER_MASK = 0x03
    
    MAX_PATH_SIZE = 64
    MAX_PACKET_PAYLOAD = 240
    MAX_HASH_SIZE = 32
    MAX_MTU_SIZE = 512
    
    def __init__(self):
        self.logger = None
    
    def set_logger(self, logger):
        """Set logger for debugging"""
        self.logger = logger
    
    def parse_message(self, raw_message: str) -> Optional[MeshCoreMessage]:
        """Parse text-based message (for backward compatibility)"""
        try:
            # Try JSON format
            if raw_message.startswith('{') and raw_message.endswith('}'):
                return self._parse_json_message(raw_message)
            
            # Try pipe-separated format
            elif '|' in raw_message:
                return self._parse_pipe_message(raw_message)
            
            # Try space-separated format
            elif ' ' in raw_message:
                return self._parse_space_message(raw_message)
            
            # Plain text
            else:
                return MeshCoreMessage(
                    content=raw_message,
                    message_type=MessageType.TEXT
                )
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error parsing text message: {e}")
            return None
    
    def parse_binary_message(self, raw_data: bytes) -> Optional[MeshCoreMessage]:
        """Parse binary MeshCore packet"""
        if self.logger:
            self.logger.debug(f"parse_binary_message called with {len(raw_data)} bytes: {raw_data.hex()[:32]}...")
        try:
            packet = self.parse_binary_packet(raw_data)
            if not packet:
                if self.logger:
                    self.logger.debug("parse_binary_packet returned None")
                return None
            
            message = self._convert_packet_to_message(packet)
            if self.logger:
                self.logger.debug(f"Created message: {message.content}")
            return message
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error parsing binary message: {e}")
            return None
    
    def parse_binary_packet(self, raw_data: bytes) -> Optional[MeshCorePacket]:
        """Parse binary packet according to MeshCore protocol"""
        if self.logger:
            self.logger.debug(f"Parsing binary packet: {raw_data.hex()}")
        
        if len(raw_data) < 2:
            if self.logger:
                self.logger.debug(f"Packet too short: {len(raw_data)} bytes")
            return None
        
        try:
            # Parse header
            header = raw_data[0]
            
            # Extract route type (bits 0-1)
            route_type_val = header & self.PH_ROUTE_MASK
            route_type = RouteType(route_type_val)
            
            # Extract payload type (bits 2-5)
            payload_type_val = (header >> self.PH_TYPE_SHIFT) & self.PH_TYPE_MASK
            payload_type = PayloadType(payload_type_val)
            
            # Extract payload version (bits 6-7)
            payload_version_val = (header >> self.PH_VER_SHIFT) & self.PH_VER_MASK
            payload_version = PayloadVersion(payload_version_val)
            
            # Check if packet has transport codes
            has_transport = (route_type == RouteType.TRANSPORT_FLOOD or 
                           route_type == RouteType.TRANSPORT_DIRECT)
            
            # Parse packet structure
            i = 1  # Start after header
            
            # Parse transport codes if present
            transport_codes = [0, 0]
            if has_transport and len(raw_data) >= i + 4:
                transport_codes[0] = struct.unpack('<H', raw_data[i:i+2])[0]
                transport_codes[1] = struct.unpack('<H', raw_data[i+2:i+4])[0]
                i += 4
            
            # Parse path length
            if i >= len(raw_data):
                if self.logger:
                    self.logger.debug("Packet truncated at path length")
                return None
            
            path_len = raw_data[i]
            i += 1
            
            # Validate path length
            if path_len > self.MAX_PATH_SIZE:
                if self.logger:
                    self.logger.debug(f"Path too long: {path_len} bytes")
                return None
            
            # Parse path
            if i + path_len > len(raw_data):
                if self.logger:
                    self.logger.debug(f"Packet truncated at path: i={i}, path_len={path_len}, total_len={len(raw_data)}")
                return None
            
            path = raw_data[i:i+path_len]
            i += path_len
            
            # Remaining data is payload
            payload = raw_data[i:]
            payload_len = len(payload)
            
            if self.logger:
                self.logger.debug(f"Parsed packet: header=0x{header:02x}, route_type={route_type}, payload_type={payload_type}, path_len={path_len}, payload_len={payload_len}")
            
            if payload_len > self.MAX_PACKET_PAYLOAD:
                if self.logger:
                    self.logger.debug(f"Payload too long: {payload_len} bytes")
                return None
            
            return MeshCorePacket(
                header=header,
                route_type=route_type,
                payload_type=payload_type,
                payload_version=payload_version,
                transport_codes=transport_codes,
                path=path,
                path_len=path_len,
                payload=payload,
                payload_len=payload_len,
                raw_data=raw_data
            )
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error parsing binary packet: {e}")
            return None
    
    def _convert_packet_to_message(self, packet: MeshCorePacket) -> MeshCoreMessage:
        """Convert parsed packet to message format"""
        content = f"Binary packet: {packet.raw_data.hex()[:32]}..."
        
        # Try to extract text content from payload based on type
        if packet.payload_type == PayloadType.TXT_MSG:
            try:
                # TXT_MSG format: dest_hash(1) + src_hash(1) + MAC(2) + timestamp(4) + text
                if packet.payload_len >= 8:
                    # Skip dest_hash, src_hash, MAC (4 bytes)
                    # Extract timestamp (4 bytes)
                    timestamp = struct.unpack('<I', packet.payload[4:8])[0]
                    # Remaining is text
                    text_data = packet.payload[8:]
                    try:
                        text_content = text_data.decode('utf-8').rstrip('\x00')
                        content = text_content
                    except UnicodeDecodeError:
                        content = f"Text message (binary): {text_data.hex()}"
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"Error extracting text from TXT_MSG: {e}")
        
        elif packet.payload_type == PayloadType.GRP_TXT:
            try:
                # GRP_TXT format: channel_hash(1) + MAC(2) + timestamp(4) + "name: msg"
                if packet.payload_len >= 7:
                    # Skip channel_hash, MAC (3 bytes)
                    # Extract timestamp (4 bytes)
                    timestamp = struct.unpack('<I', packet.payload[3:7])[0]
                    # Remaining is "name: msg"
                    text_data = packet.payload[7:]
                    try:
                        text_content = text_data.decode('utf-8').rstrip('\x00')
                        content = text_content
                    except UnicodeDecodeError:
                        content = f"Group text (binary): {text_data.hex()}"
            except Exception as e:
                if self.logger:
                    self.logger.debug(f"Error extracting text from GRP_TXT: {e}")
        
        # Extract path information
        path_info = []
        if packet.path_len > 0:
            for i in range(0, packet.path_len, 2):
                if i + 1 < packet.path_len:
                    hop = struct.unpack('<H', packet.path[i:i+2])[0]
                    path_info.append(f"{hop:04x}")
        
        # Determine if this is a DM based on payload type
        is_dm = packet.payload_type == PayloadType.TXT_MSG
        
        return MeshCoreMessage(
            content=content,
            message_type=MessageType.BINARY,
            payload_type=packet.payload_type,
            route_type=packet.route_type,
            payload_version=packet.payload_version,
            transport_codes=packet.transport_codes,
            path=path_info,
            hops=len(path_info),
            raw_data=packet.raw_data,
            is_dm=is_dm
        )
    
    def format_message(self, message: MeshCoreMessage) -> str:
        """Format message for transmission"""
        if message.message_type == MessageType.JSON:
            return self._format_json_message(message)
        elif message.message_type == MessageType.PIPE:
            return self._format_pipe_message(message)
        else:
            return message.content
    
    def _parse_json_message(self, raw_message: str) -> MeshCoreMessage:
        """Parse JSON format message"""
        import json
        data = json.loads(raw_message)
        return MeshCoreMessage(
            content=data.get('content', ''),
            message_type=MessageType.JSON,
            sender_id=data.get('sender_id'),
            channel=data.get('channel'),
            hops=data.get('hops')
        )
    
    def _parse_pipe_message(self, raw_message: str) -> MeshCoreMessage:
        """Parse pipe-separated format message"""
        parts = raw_message.split('|')
        return MeshCoreMessage(
            content=parts[0] if parts else '',
            message_type=MessageType.PIPE,
            sender_id=parts[1] if len(parts) > 1 else None,
            channel=parts[2] if len(parts) > 2 else None,
            hops=int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
        )
    
    def _parse_space_message(self, raw_message: str) -> MeshCoreMessage:
        """Parse space-separated format message"""
        parts = raw_message.split()
        return MeshCoreMessage(
            content=parts[0] if parts else '',
            message_type=MessageType.TEXT,
            sender_id=parts[1] if len(parts) > 1 else None,
            channel=parts[2] if len(parts) > 2 else None,
            hops=int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
        )
    
    def _format_json_message(self, message: MeshCoreMessage) -> str:
        """Format message as JSON"""
        import json
        data = {
            'content': message.content,
            'sender_id': message.sender_id,
            'channel': message.channel,
            'hops': message.hops
        }
        return json.dumps(data)
    
    def _format_pipe_message(self, message: MeshCoreMessage) -> str:
        """Format message as pipe-separated"""
        parts = [message.content]
        if message.sender_id:
            parts.append(message.sender_id)
        if message.channel:
            parts.append(message.channel)
        if message.hops is not None:
            parts.append(str(message.hops))
        return '|'.join(parts)
    
    def format_command(self, command: str, **kwargs) -> str:
        """Format a command message for sending to MeshCore node"""
        import json
        command_data = {
            'type': 'command',
            'command': command,
            'timestamp': int(time.time()),
            **kwargs
        }
        return json.dumps(command_data)


class SerialProtocolAdapter:
    """Serial protocol adapter"""
    
    def __init__(self, serial_connection):
        self.serial_connection = serial_connection
        self.protocol = MeshCoreProtocol()
    
    async def send_message(self, message: str) -> bool:
        """Send message via serial"""
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.write(f"{message}\n".encode())
                return True
            return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"Serial send error: {e}")
            return False
    
    async def read_message(self) -> Optional[str]:
        """Read message via serial"""
        try:
            if self.serial_connection and self.serial_connection.is_open:
                if self.serial_connection.in_waiting:
                    line = self.serial_connection.readline().decode().strip()
                    return line if line else None
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Serial read error: {e}")
            return None


class BLEProtocolAdapter:
    """BLE protocol adapter"""
    
    # Nordic UART Service UUIDs
    SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    TX_CHARACTERISTIC_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    RX_CHARACTERISTIC_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
    
    def __init__(self, client):
        self.client = client
        self.protocol = MeshCoreProtocol()
        self.custom_handler = None
    
    async def send_message(self, message: str) -> bool:
        """Send message via BLE"""
        try:
            if self.client and self.client.is_connected:
                await self.client.write_gatt_char(
                    self.TX_CHARACTERISTIC_UUID,
                    message.encode()
                )
                return True
            return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"BLE send error: {e}")
            return False
    
    async def read_message(self) -> Optional[str]:
        """Read message via BLE (polling method)"""
        try:
            if self.client and self.client.is_connected:
                data = await self.client.read_gatt_char(self.RX_CHARACTERISTIC_UUID)
                
                # Try UTF-8 first
                try:
                    return data.decode('utf-8')
                except UnicodeDecodeError:
                    # Fall back to binary parsing
                    message = self.protocol.parse_binary_message(data)
                    return message.content if message else None
                    
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"BLE read error: {e}")
            return None
    
    async def setup_notifications(self, custom_handler=None):
        """Setup BLE notifications for incoming messages"""
        if not self.client or not self.client.is_connected:
            return False
        
        try:
            # Store custom handler if provided
            if custom_handler:
                self.custom_handler = custom_handler
            
            # Enable notifications on RX characteristic
            await self.client.start_notify(self.RX_CHARACTERISTIC_UUID, self._notification_handler)
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to setup BLE notifications: {e}")
            return False
    
    def _notification_handler(self, sender, data):
        """Handle incoming BLE notifications"""
        try:
            # Use custom handler if provided
            if self.custom_handler:
                self.custom_handler(data)
                return
            
            # Default handling
            try:
                message_str = data.decode('utf-8')
                if self.logger:
                    self.logger.debug(f"BLE Notification (UTF-8): {message_str}")
                # Parse as text message
                message = self.protocol.parse_message(message_str)
                if message:
                    if self.logger:
                        self.logger.debug(f"Parsed text message: {message.content}")
            except UnicodeDecodeError:
                # If UTF-8 fails, try binary packet parsing
                if self.logger:
                    self.logger.debug(f"BLE Notification (Binary): {data.hex()}")
                message = self.protocol.parse_binary_message(data)
                if message:
                    if self.logger:
                        self.logger.debug(f"Parsed binary packet: {message.content}")
                else:
                    if self.logger:
                        self.logger.debug(f"Could not parse binary packet: {data.hex()}")
            
            # You can process the message here or store it for later processing
            # For now, just log it
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error handling BLE notification: {e}")
