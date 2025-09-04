#!/usr/bin/env python3
"""
Message handling functionality for the MeshCore Bot
Processes incoming messages and routes them to appropriate command handlers
"""

import asyncio
from typing import Optional
from meshcore import EventType

from .models import MeshMessage


class MessageHandler:
    """Handles incoming messages and routes them to command processors"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        # Cache for storing SNR and RSSI data from RF log events
        self.snr_cache = {}
        self.rssi_cache = {}
        
        # Time-based cache for recent RF log data (last 5 seconds)
        self.recent_rf_data = []
        self.rf_data_timeout = 5.0  # seconds
    
    async def handle_contact_message(self, event, metadata=None):
        """Handle incoming contact message (DM)"""
        try:
            payload = event.payload
            
            # Debug: Log the full payload structure
            self.logger.debug(f"Contact message payload: {payload}")
            self.logger.debug(f"Payload keys: {list(payload.keys())}")
            self.logger.debug(f"Event metadata: {event.metadata if hasattr(event, 'metadata') else 'None'}")
            
            self.logger.info(f"Received DM from {payload.get('pubkey_prefix', 'unknown')}: {payload.get('text', '')}")
            
            # Extract path information from contacts using pubkey_prefix
            path_info = "Unknown"
            path_len = payload.get('path_len', 255)
            
            if metadata and 'pubkey_prefix' in metadata:
                pubkey_prefix = metadata.get('pubkey_prefix', '')
                if pubkey_prefix:
                    self.logger.debug(f"Looking up path for pubkey_prefix: {pubkey_prefix}")
                    
                    # Look up the contact to get path information
                    if hasattr(self.bot.meshcore, 'contacts') and self.bot.meshcore.contacts:
                        for contact_key, contact_data in self.bot.meshcore.contacts.items():
                            if contact_data.get('public_key', '').startswith(pubkey_prefix):
                                out_path = contact_data.get('out_path', '')
                                out_path_len = contact_data.get('out_path_len', -1)
                                
                                if out_path and out_path_len > 0:
                                    # Convert hex path to readable node IDs using first 2 chars of pubkey
                                    try:
                                        path_bytes = bytes.fromhex(out_path)
                                        path_nodes = []
                                        for i in range(0, len(path_bytes), 2):
                                            if i + 1 < len(path_bytes):
                                                node_id = int.from_bytes(path_bytes[i:i+2], byteorder='little')
                                                # Convert to 2-character hex representation
                                                path_nodes.append(f"{node_id:02x}")
                                        
                                        path_info = f"{','.join(path_nodes)} ({out_path_len} hops)"
                                        self.logger.debug(f"Found path info: {path_info}")
                                    except Exception as e:
                                        self.logger.debug(f"Error converting path: {e}")
                                        path_info = f"Path: {out_path} ({out_path_len} hops)"
                                    break
                                elif out_path_len == 0:
                                    path_info = "Direct"
                                    self.logger.debug(f"Direct connection: {path_info}")
                                    break
                                else:
                                    path_info = "Unknown path"
                                    self.logger.debug(f"No path info available: {path_info}")
                                    break
            
            # Fallback to basic path logic if no detailed info found
            if path_info == "Unknown":
                if path_len == 255:
                    path_info = "Direct"
                elif path_len > 0:
                    path_info = f"Routed ({path_len} hops)"
                elif path_len == 0:
                    path_info = "Direct"
            
            # Try to decode packet and extract routing information from stored raw data
            decoded_packet = None
            routing_info = None
            # Look for raw packet data in recent RF data
            message_pubkey = payload.get('pubkey_prefix', '')  # Use payload instead of metadata
            if message_pubkey:
                recent_rf_data = self.find_recent_rf_data(message_pubkey)
                if recent_rf_data and recent_rf_data.get('raw_hex'):
                    decoded_packet = self.decode_meshcore_packet(recent_rf_data['raw_hex'])
                    if decoded_packet:
                        self.logger.debug(f"Decoded packet for routing from RF data: {decoded_packet}")
                        
                        # Extract routing information
                        if recent_rf_data.get('routing_info'):
                            routing_info = recent_rf_data['routing_info']
                            self.logger.debug(f"Found routing info: {routing_info}")
                
                # If we have routing info, use it for path information
                if routing_info:
                    path_len = routing_info.get('path_length', 0)
                    if path_len > 0:
                        path_hex = routing_info.get('path_hex', '')
                        path_nodes = routing_info.get('path_nodes', [])
                        route_type = routing_info.get('route_type', 'Unknown')
                        
                        # Convert path to readable format
                        if path_nodes:
                            path_info = f"{','.join(path_nodes)} ({path_len} hops via {route_type})"
                        else:
                            path_info = f"Path: {path_hex} ({path_len} hops via {route_type})"
                        
                        self.logger.info(f"🛣️  MESSAGE ROUTING: {path_info}")
                    else:
                        path_info = f"Direct via {routing_info.get('route_type', 'Unknown')}"
                        self.logger.info(f"📡 DIRECT MESSAGE: {path_info}")
            
            # Get additional metadata - try multiple sources for SNR and RSSI
            snr = 'unknown'
            rssi = 'unknown'
            
            # Try to get SNR from payload first - check multiple possible field names
            if 'SNR' in payload:
                snr = payload.get('SNR')
            elif 'snr' in payload:
                snr = payload.get('snr')
            elif 'signal_to_noise' in payload:
                snr = payload.get('signal_to_noise')
            elif 'signal_noise_ratio' in payload:
                snr = payload.get('signal_noise_ratio')
            # Try to get SNR from event metadata if available
            elif metadata:
                if 'snr' in metadata:
                    snr = metadata.get('snr')
                elif 'SNR' in metadata:
                    snr = metadata.get('SNR')
            
            # If still no SNR, try to get it from the cache using pubkey prefix from payload
            if snr == 'unknown':
                pubkey_prefix = payload.get('pubkey_prefix', '')
                if pubkey_prefix and pubkey_prefix in self.snr_cache:
                    snr = self.snr_cache[pubkey_prefix]
                    self.logger.debug(f"Retrieved cached SNR {snr} for pubkey {pubkey_prefix}")
            
            # Try to get RSSI from payload first
            if 'RSSI' in payload:
                rssi = payload.get('RSSI')
            elif 'rssi' in payload:
                rssi = payload.get('rssi')
            elif 'signal_strength' in payload:
                rssi = payload.get('signal_strength')
            # Try to get RSSI from event metadata if available
            elif metadata:
                if 'rssi' in metadata:
                    rssi = metadata.get('rssi')
                elif 'RSSI' in metadata:
                    rssi = metadata.get('RSSI')
            
            # If still no RSSI, try to get it from the cache using pubkey prefix from payload
            if rssi == 'unknown':
                pubkey_prefix = payload.get('pubkey_prefix', '')
                if pubkey_prefix and pubkey_prefix in self.rssi_cache:
                    rssi = self.rssi_cache[pubkey_prefix]
                    self.logger.debug(f"Retrieved cached RSSI {rssi} for pubkey {pubkey_prefix}")
            
            # For DMs, we can't decode the encrypted packet, but we can get SNR/RSSI from the payload
            # For channel messages, we can decode the packet since they use shared keys
            message_pubkey = payload.get('pubkey_prefix', '')
            self.logger.debug(f"Processing DM from pubkey: {message_pubkey}")
            
            # DMs are encrypted with recipient's public key, so we can't decode the raw packet
            # But we can get SNR/RSSI from the message payload if available
            if 'SNR' in payload:
                snr = payload.get('SNR')
                self.logger.debug(f"Using SNR from DM payload: {snr}")
            elif 'snr' in payload:
                snr = payload.get('snr')
                self.logger.debug(f"Using SNR from DM payload: {snr}")
            
            if 'RSSI' in payload:
                rssi = payload.get('RSSI')
                self.logger.debug(f"Using RSSI from DM payload: {rssi}")
            elif 'rssi' in payload:
                rssi = payload.get('rssi')
                self.logger.debug(f"Using RSSI from DM payload: {rssi}")
            
            # Since DMs don't include SNR/RSSI in payload, try to get it from recent RF data
            # This is a fallback since RF data often comes right before/after the message
            if snr == 'unknown' or rssi == 'unknown':
                recent_rf_data = self.find_recent_rf_data()
                if recent_rf_data:
                    self.logger.debug(f"Found recent RF data for DM: {recent_rf_data}")
                    
                    if snr == 'unknown' and recent_rf_data.get('snr'):
                        snr = recent_rf_data['snr']
                        self.logger.debug(f"Using SNR from recent RF data: {snr}")
                    
                    if rssi == 'unknown' and recent_rf_data.get('rssi'):
                        rssi = recent_rf_data['rssi']
                        self.logger.debug(f"Using RSSI from recent RF data: {rssi}")
            
            # For DMs, we can't determine the actual routing path from encrypted data
            # Use the path_len from the payload (255 means unknown/direct)
            path_len = payload.get('path_len', 255)
            if path_len == 255:
                path_info = "Direct (0 hops)"
            else:
                path_info = f"Routed through {path_len} hops"
            
            self.logger.debug(f"DM path info: {path_info}")
            
            timestamp = payload.get('sender_timestamp', 'unknown')
            
            # Look up contact name from pubkey prefix
            sender_id = payload.get('pubkey_prefix', '')
            if hasattr(self.bot.meshcore, 'contacts') and self.bot.meshcore.contacts:
                for contact_key, contact_data in self.bot.meshcore.contacts.items():
                    if contact_data.get('public_key', '').startswith(sender_id):
                        # Use the contact name if available, otherwise use adv_name
                        contact_name = contact_data.get('name', contact_data.get('adv_name', sender_id))
                        sender_id = contact_name
                        break
            
            # Convert to our message format
            message = MeshMessage(
                content=payload.get('text', ''),
                sender_id=sender_id,
                is_dm=True,
                timestamp=timestamp,
                snr=snr,
                rssi=rssi,
                hops=path_len if path_len != 255 else 0,
                path=path_info
            )
            
            # Always decode and log path information for debugging (regardless of keywords)
            recent_rf_data = self.find_recent_rf_data()
            
            # If we have RF data with routing information, update the path with that instead
            if recent_rf_data and recent_rf_data.get('routing_info'):
                rf_routing = recent_rf_data['routing_info']
                if rf_routing.get('path_length', 0) > 0:
                    path_nodes = rf_routing.get('path_nodes', [])
                    route_type = rf_routing.get('route_type', 'Unknown')
                    if path_nodes:
                        message.path = f"{','.join(path_nodes)} ({len(path_nodes)} hops via {route_type})"
                        self.logger.info(f"🛣️  CONTACT USING RF ROUTING: {message.path}")
                    else:
                        message.path = f"{rf_routing.get('path_hex', 'Unknown')} ({rf_routing.get('path_length', 0)} hops via {route_type})"
                        self.logger.info(f"🛣️  CONTACT USING RF ROUTING: {message.path}")
                else:
                    message.path = f"Direct via {rf_routing.get('route_type', 'Unknown')}"
                    self.logger.info(f"📡 CONTACT USING RF ROUTING: {message.path}")
            
            await self._debug_decode_message_path(message, sender_id, recent_rf_data)
            
            # Always attempt packet decoding and log the results for debugging
            await self._debug_decode_packet_for_message(message, sender_id, recent_rf_data)
            
            await self.process_message(message)
            
        except Exception as e:
            self.logger.error(f"Error handling contact message: {e}")
    
    async def handle_raw_data(self, event, metadata=None):
        """Handle raw data events (full packet data from debug mode)"""
        try:
            payload = event.payload
            self.logger.info(f"📦 RAW_DATA EVENT RECEIVED: {payload}")
            
            # This should contain the full packet data we need
            if hasattr(payload, 'data') or 'data' in payload:
                raw_data = payload.get('data', payload.data if hasattr(payload, 'data') else None)
                if raw_data:
                    self.logger.info(f"🔍 FULL PACKET DATA: {raw_data}")
                    
                    # Try to decode this as a MeshCore packet
                    if isinstance(raw_data, str):
                        # Convert to hex if it's not already
                        if not raw_data.startswith('0x'):
                            raw_hex = raw_data
                        else:
                            raw_hex = raw_data[2:]  # Remove 0x prefix
                        
                        # Decode the packet
                        packet_info = self.decode_meshcore_packet(raw_hex)
                        if packet_info:
                            self.logger.info(f"✅ SUCCESSFULLY DECODED RAW PACKET: {packet_info}")
                        else:
                            self.logger.warning("❌ Failed to decode raw packet data")
                    else:
                        self.logger.warning(f"❌ Unexpected raw data type: {type(raw_data)}")
                else:
                    self.logger.warning("❌ No data field in RAW_DATA event")
            else:
                self.logger.warning(f"❌ Unexpected RAW_DATA payload structure: {payload}")
                
        except Exception as e:
            self.logger.error(f"Error handling raw data event: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    async def handle_rf_log_data(self, event, metadata=None):
        """Handle RF log data events to cache SNR information and store raw packet data"""
        try:
            payload = event.payload
            
            # Extract SNR from payload
            if 'snr' in payload:
                snr_value = payload.get('snr')
                
                # Try to get pubkey from metadata first
                pubkey_prefix = None
                if metadata and 'pubkey_prefix' in metadata:
                    pubkey_prefix = metadata.get('pubkey_prefix')
                    self.logger.debug(f"Got pubkey_prefix from metadata: {pubkey_prefix[:16]}...")
                
                # Fallback: extract pubkey from raw_hex if no metadata
                if not pubkey_prefix:
                    raw_hex = payload.get('raw_hex', '')
                    if raw_hex and len(raw_hex) >= 64:  # Pubkey is 64 hex chars
                        # Extract first 64 characters as pubkey (32 bytes)
                        pubkey_prefix = raw_hex[:64]
                        self.logger.debug(f"Extracted pubkey from raw_hex: {pubkey_prefix[:16]}...")
                    elif raw_hex and len(raw_hex) >= 32:
                        # For shorter packets, try to extract sender pubkey from payload
                        # This handles cases where the packet is truncated
                        decoded_packet = self.decode_meshcore_packet(raw_hex)
                        if decoded_packet and decoded_packet.get('payload'):
                            # Try to extract sender info from payload
                            payload_hex = decoded_packet['payload']
                            if len(payload_hex) >= 64:
                                # Assume first 64 chars might be sender pubkey
                                potential_pubkey = payload_hex[:64]
                                self.logger.debug(f"Extracted potential pubkey from payload: {potential_pubkey[:16]}...")
                                pubkey_prefix = potential_pubkey
                
                if pubkey_prefix and snr_value is not None:
                    # Cache the SNR value for this pubkey
                    self.snr_cache[pubkey_prefix] = snr_value
                    self.logger.debug(f"Cached SNR {snr_value} for pubkey {pubkey_prefix[:16]}...")
                
                # Extract and cache RSSI if available
                if 'rssi' in payload:
                    rssi_value = payload.get('rssi')
                    if pubkey_prefix and rssi_value is not None:
                        # Cache the RSSI value for this pubkey
                        self.rssi_cache[pubkey_prefix] = rssi_value
                        self.logger.debug(f"Cached RSSI {rssi_value} for pubkey {pubkey_prefix[:16]}...")
                
                # Store recent RF data with timestamp for SNR/RSSI matching only
                if pubkey_prefix:
                    import time
                    current_time = time.time()
                    
                    # Store both raw packet data and extracted payload for analysis
                    raw_hex = payload.get('raw_hex', '')
                    extracted_payload = payload.get('payload', '')
                    payload_length = payload.get('payload_length', 0)
                    
                    # Extract routing information from raw packet if available
                    routing_info = None
                    if raw_hex:
                        decoded_packet = self.decode_meshcore_packet(raw_hex)
                        if decoded_packet:
                            routing_info = {
                                'path_length': decoded_packet.get('path_len', 0),
                                'path_hex': decoded_packet.get('path_hex', ''),
                                'path_nodes': decoded_packet.get('path', []),
                                'route_type': decoded_packet.get('route_type_name', 'Unknown'),
                                'transport_size': decoded_packet.get('transport_size', 0),
                                'payload_type': decoded_packet.get('payload_type_name', 'Unknown')
                            }
                            
                            # Log the routing information for analysis
                            if routing_info['path_length'] > 0:
                                self.logger.info(f"🛣️  ROUTING INFO: {routing_info['route_type']} | Path: {routing_info['path_hex']} ({routing_info['path_length']} bytes) | Type: {routing_info['payload_type']}")
                            else:
                                self.logger.info(f"📡 DIRECT MESSAGE: {routing_info['route_type']} | Type: {routing_info['payload_type']}")
                    
                    rf_data = {
                        'timestamp': current_time,
                        'pubkey_prefix': pubkey_prefix,
                        'snr': snr_value,
                        'rssi': payload.get('rssi') if 'rssi' in payload else None,
                        'raw_hex': raw_hex,  # Full packet data
                        'payload': extracted_payload,  # Extracted payload
                        'payload_length': payload_length,  # Payload length
                        'routing_info': routing_info  # Extracted routing information
                    }
                    self.recent_rf_data.append(rf_data)
                    
                    # Clean up old data
                    self.recent_rf_data = [data for data in self.recent_rf_data 
                                         if current_time - data['timestamp'] < self.rf_data_timeout]
                    
                    self.logger.debug(f"Stored recent RF data with routing info: {rf_data}")
                        
        except Exception as e:
            self.logger.error(f"Error handling RF log data: {e}")
    
    def find_recent_rf_data(self, message_pubkey=None, max_age_seconds=5.0):
        """Find recent RF data for SNR/RSSI and packet decoding"""
        import time
        current_time = time.time()
        
        # Filter recent RF data by age
        recent_data = [data for data in self.recent_rf_data 
                      if current_time - data['timestamp'] < max_age_seconds]
        
        if not recent_data:
            return None
        
        # If we have a specific pubkey, try to find exact or partial matches
        if message_pubkey:
            for data in recent_data:
                rf_pubkey = data['pubkey_prefix']
                # Check for exact match or partial match
                if (rf_pubkey == message_pubkey or 
                    rf_pubkey.startswith(message_pubkey) or 
                    message_pubkey.startswith(rf_pubkey)):
                    self.logger.debug(f"Found exact/partial pubkey match: {rf_pubkey} matches {message_pubkey}")
                    return data
        
        # If no specific pubkey or no matches, return the most recent data
        # This is more reliable since RF data often comes right after messages
        # and represents the same transmission even if pubkeys don't match
        if recent_data:
            most_recent = max(recent_data, key=lambda x: x['timestamp'])
            self.logger.debug(f"Using most recent RF data for SNR/RSSI and packet decoding: {most_recent}")
            return most_recent
        
        return None
    

    
    def decode_meshcore_packet(self, raw_hex: str) -> Optional[dict]:
        """
        Decode a MeshCore packet from raw hex data using the proven approach from mctomqtt.py
        
        Args:
            raw_hex: Raw packet data as hex string
            
        Returns:
            Decoded packet information or None if parsing fails
        """
        try:
            byte_data = bytes.fromhex(raw_hex)
            
            # Basic validation
            if len(byte_data) < 2:
                self.logger.debug(f"Packet too short: {len(byte_data)} bytes")
                return None
                
            header = byte_data[0]
            
            # Check if transport codes are present based on route type
            route_type = header & 0x03
            has_transport = route_type in [0, 1, 2, 3]  # All route types have transport codes
            
            # Transport codes size: appears to be 2 bytes for most types, 4 bytes only for specific cases
            # Based on packet analysis, even route type 3 seems to use 2 bytes
            transport_size = 2 if has_transport else 0
            
            # Path length offset: 1 byte for header + transport codes size
            path_len_offset = 1 + transport_size
            
            if len(byte_data) < path_len_offset + 1:
                self.logger.debug(f"Packet too short for path length: {len(byte_data)} bytes")
                return None
                
            path_len = byte_data[path_len_offset]
            
            # Path starts after header + transport codes + path length
            path_start = path_len_offset + 1
            
            if len(byte_data) < path_start + path_len:
                self.logger.debug(f"Packet too short for path: need {path_start + path_len}, have {len(byte_data)}")
                return None
                
            path = byte_data[path_start:path_start + path_len].hex()
            payload = byte_data[path_start + path_len:]
            
            # Extract packet metadata from header
            payload_version = (header >> 6) & 0x03
            payload_type = (header >> 2) & 0x0F
            
            # Convert path to individual node IDs
            path_values = []
            for i in range(0, len(path), 2):
                if i + 1 < len(path):
                    path_values.append(path[i:i+2])
            
            packet_info = {
                'header': f"0x{header:02x}",
                'route_type': route_type,
                'route_type_name': self._get_route_type_name(route_type),
                'payload_type': payload_type,
                'payload_type_name': self.get_payload_type_name(payload_type),
                'payload_version': payload_version,
                'has_transport_codes': has_transport,
                'transport_size': transport_size,
                'path_len': path_len,
                'path': path_values,
                'path_hex': path,
                'payload_hex': payload.hex(),
                'payload_bytes': len(payload)
            }
            
            self.logger.debug(f"Successfully decoded packet: {packet_info}")
            return packet_info
            
        except Exception as e:
            self.logger.error(f"Error decoding packet '{raw_hex}': {e}")
            return None
    
    def _get_route_type_name(self, route_type):
        """Get human-readable name for route type"""
        route_types = {
            0x00: "ROUTE_TYPE_TRANSPORT_FLOOD",
            0x01: "ROUTE_TYPE_FLOOD", 
            0x02: "ROUTE_TYPE_DIRECT",
            0x03: "ROUTE_TYPE_TRANSPORT_DIRECT"
        }
        return route_types.get(route_type, f"UNKNOWN_ROUTE_{route_type:02x}")
    
    def get_payload_type_name(self, payload_type: int) -> str:
        """Get human-readable name for payload type"""
        payload_types = {
            0x00: "UNKNOWN",
            0x01: "HELLO",
            0x02: "TXT_MSG",
            0x03: "ACK",
            0x04: "ADVERT",
            0x05: "GRP_TXT",
            0x06: "GRP_JOIN",
            0x07: "GRP_LEAVE",
            0x08: "PATH",
            0x09: "CHANNEL_JOIN",
            0x0A: "CHANNEL_LEAVE",
            0x0B: "CHANNEL_MSG",
            0x0C: "CHANNEL_ACK",
            0x0D: "CHANNEL_NACK",
            0x0E: "CHANNEL_INVITE",
            0x0F: "CHANNEL_KICK"
        }
        return payload_types.get(payload_type, f"UNKNOWN_{payload_type:02x}")
    
    async def handle_channel_message(self, event, metadata=None):
        """Handle incoming channel message"""
        try:
            payload = event.payload
            channel_idx = payload.get('channel_idx', 0)
            
            # Debug: Log the full payload structure
            self.logger.debug(f"Channel message payload: {payload}")
            self.logger.debug(f"Payload keys: {list(payload.keys())}")
            
            # Get sender information from text field if it's in "SENDER: message" format
            text = payload.get('text', '')
            sender_id = "Channel User"  # Default fallback
            
            # Try to extract sender from text field (e.g., "HOWL: Test" -> "HOWL")
            message_content = text  # Default to full text
            if ':' in text and not text.startswith(':'):
                parts = text.split(':', 1)
                if len(parts) == 2 and parts[0].strip():
                    sender_id = parts[0].strip()
                    message_content = parts[1].strip()  # Use the part after the colon for keyword processing
                    self.logger.debug(f"Extracted sender from text: {sender_id}")
                    self.logger.debug(f"Message content for processing: {message_content}")
            
            # Get channel name from channel number
            channel_name = self.bot.channel_manager.get_channel_name(channel_idx)
            
            self.logger.info(f"Received channel message ({channel_name}) from {sender_id}: {text}")
            
            # Get SNR and RSSI using the same logic as contact messages
            snr = 'unknown'
            rssi = 'unknown'
            
            # Try to get SNR from payload first
            if 'SNR' in payload:
                snr = payload.get('SNR')
            elif 'snr' in payload:
                snr = payload.get('snr')
            # Try to get SNR from event metadata if available
            elif metadata:
                if 'snr' in metadata:
                    snr = metadata.get('snr')
                elif 'SNR' in metadata:
                    snr = metadata.get('SNR')
            
            # If still no SNR, try to get it from the cache using pubkey prefix from payload
            if snr == 'unknown':
                pubkey_prefix = payload.get('pubkey_prefix', '')
                if pubkey_prefix and pubkey_prefix in self.snr_cache:
                    snr = self.snr_cache[pubkey_prefix]
                    self.logger.debug(f"Retrieved cached SNR {snr} for pubkey {pubkey_prefix}")
            
            # Try to get RSSI from payload first
            if 'RSSI' in payload:
                rssi = payload.get('RSSI')
            elif 'rssi' in payload:
                rssi = payload.get('rssi')
            elif 'signal_strength' in payload:
                rssi = payload.get('signal_strength')
            # Try to get RSSI from event metadata if available
            elif metadata:
                if 'rssi' in metadata:
                    rssi = metadata.get('rssi')
                elif 'RSSI' in metadata:
                    rssi = metadata.get('RSSI')
            
            # If still no RSSI, try to get it from the cache using pubkey prefix from payload
            if rssi == 'unknown':
                pubkey_prefix = payload.get('pubkey_prefix', '')
                if pubkey_prefix and pubkey_prefix in self.rssi_cache:
                    rssi = self.rssi_cache[pubkey_prefix]
                    self.logger.debug(f"Retrieved cached RSSI {rssi} for pubkey {pubkey_prefix}")
            
            # For channel messages, we can decode the packet since they use shared channel keys
            # This gives us access to the actual routing information
            message_pubkey = payload.get('pubkey_prefix', '')
            self.logger.debug(f"Processing channel message from pubkey: {message_pubkey}")
            
            # Try to decode the packet to get routing information directly from the packet
            # According to MeshCore FAQ, the path gets embedded into the packet for future messages
            recent_rf_data = self.find_recent_rf_data()
            if recent_rf_data and recent_rf_data.get('raw_hex'):
                raw_hex = recent_rf_data['raw_hex']
                self.logger.info(f"🔍 FOUND RF DATA: {len(raw_hex)} chars, starts with: {raw_hex[:32]}...")
                self.logger.debug(f"Full RF data: {raw_hex}")
                
                # Extract SNR/RSSI from the RF data
                if recent_rf_data.get('snr'):
                    snr = recent_rf_data['snr']
                    self.logger.debug(f"Using SNR from RF data: {snr}")
                
                if recent_rf_data.get('rssi'):
                    rssi = recent_rf_data['rssi']
                    self.logger.debug(f"Using RSSI from RF data: {rssi}")
                
                # Decode the packet to extract the embedded path information
                packet_info = self.decode_meshcore_packet(raw_hex)
                if packet_info and packet_info.get('path_nodes'):
                    # Use the path information directly from the decoded packet
                    hops = len(packet_info['path_nodes'])
                    path_string = ','.join(packet_info['path_nodes'])
                    self.logger.info(f"🎯 EXTRACTED PATH FROM PACKET: {path_string} ({hops} hops)")
                else:
                    # Packet decoding failed - use basic path info from payload
                    self.logger.debug("Packet decoding failed, using basic path info")
                    hops = payload.get('path_len', 255)
                    path_string = None
            else:
                self.logger.warning("❌ NO RF DATA found for channel message")
                hops = payload.get('path_len', 255)
                path_string = None
            
            # Convert to our message format
            message = MeshMessage(
                content=message_content,  # Use the extracted message content
                sender_id=sender_id,
                channel=channel_name,
                timestamp=payload.get('sender_timestamp', 0),
                snr=snr,
                rssi=rssi,
                hops=hops,
                is_dm=False
            )
            
            # Extract path information from contacts using pubkey_prefix from metadata
            path_info = "Unknown"
            path_len = payload.get('path_len', 255)
            
            if metadata and 'pubkey_prefix' in metadata:
                pubkey_prefix = metadata.get('pubkey_prefix', '')
                if pubkey_prefix:
                    self.logger.debug(f"Looking up path for pubkey_prefix: {pubkey_prefix}")
                    
                    # Look up the contact to get path information
                    if hasattr(self.bot.meshcore, 'contacts') and self.bot.meshcore.contacts:
                        for contact_key, contact_data in self.bot.meshcore.contacts.items():
                            if contact_data.get('public_key', '').startswith(pubkey_prefix):
                                out_path = contact_data.get('out_path', '')
                                out_path_len = contact_data.get('out_path_len', -1)
                                
                                if out_path and out_path_len > 0:
                                    # Convert hex path to readable node IDs using first 2 chars of pubkey
                                    try:
                                        path_bytes = bytes.fromhex(out_path)
                                        path_nodes = []
                                        for i in range(0, len(path_bytes), 2):
                                            if i + 1 < len(path_bytes):
                                                node_id = int.from_bytes(path_bytes[i:i+2], byteorder='little')
                                                # Convert to 2-character hex representation
                                                path_nodes.append(f"{node_id:02x}")
                                        
                                        path_info = f"{','.join(path_nodes)} ({out_path_len} hops)"
                                        self.logger.debug(f"Found path info: {path_info}")
                                    except Exception as e:
                                        self.logger.debug(f"Error converting path: {e}")
                                        path_info = f"Path: {out_path} ({out_path_len} hops)"
                                    break
                                elif out_path_len == 0:
                                    path_info = "Direct"
                                    self.logger.debug(f"Direct connection: {path_info}")
                                    break
                                else:
                                    path_info = "Unknown path"
                                    self.logger.debug(f"No path info available: {path_info}")
                                    break
            
            # Create a clean routing description that combines hops and path
            if hops == 0:
                routing_info = "Direct"
            elif hops == 255:
                routing_info = "? hops"
            else:
                # Use the discovered path string if available, otherwise just show hop count
                if 'path_string' in locals() and path_string and path_string not in ["Unknown", "Error", "Timeout", "Exception"]:
                    routing_info = f"{path_string} ({hops} hops)"
                else:
                    routing_info = f"{hops} hops"
            
            # If we have RF data with routing information, use that instead
            if recent_rf_data and recent_rf_data.get('routing_info'):
                rf_routing = recent_rf_data['routing_info']
                if rf_routing.get('path_length', 0) > 0:
                    path_nodes = rf_routing.get('path_nodes', [])
                    if path_nodes:
                        routing_info = f"{','.join(path_nodes)} ({len(path_nodes)} hops)"
                        self.logger.info(f"🛣️  USING RF ROUTING: {routing_info}")
                    else:
                        routing_info = f"{rf_routing.get('path_hex', 'Unknown')} ({rf_routing.get('path_length', 0)} hops)"
                        self.logger.info(f"🛣️  USING RF ROUTING: {routing_info}")
                else:
                    routing_info = "Direct"
                    self.logger.info(f"📡 USING RF ROUTING: {routing_info}")
            
            message.path = routing_info
            self.logger.debug(f"Message routing info: hops={message.hops}, routing={message.path}")
            
            # Always decode and log packet information for debugging (regardless of keywords)
            await self._debug_decode_message_path(message, sender_id, recent_rf_data)
            
            # Always attempt packet decoding and log the results for debugging
            await self._debug_decode_packet_for_message(message, sender_id, recent_rf_data)
            
            # Process the message
            await self.process_message(message)
            
        except Exception as e:
            self.logger.error(f"Error handling channel message: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    async def discover_message_path(self, sender_id: str, rf_data: dict) -> tuple[int, str]:
        """
        Discover the actual routing path for a message using CLI commands.
        This is more reliable than trying to decode packet fragments.
        
        Args:
            sender_id: The name or ID of the sender
            rf_data: The RF data containing pubkey information
            
        Returns:
            tuple[int, str]: (Number of hops, formatted path string)
        """
        try:
            # First try to find the contact by name
            if hasattr(self.bot.meshcore, 'contacts') and self.bot.meshcore.contacts:
                contact = None
                pubkey_prefix = rf_data.get('pubkey_prefix', '')
                
                # Look for contact by name first
                for contact_key, contact_data in self.bot.meshcore.contacts.items():
                    if contact_data.get('adv_name') == sender_id:
                        contact = contact_data
                        break
                
                # If not found by name, try by pubkey prefix
                if not contact and pubkey_prefix:
                    for contact_key, contact_data in self.bot.meshcore.contacts.items():
                        if contact_data.get('public_key', '').startswith(pubkey_prefix):
                            contact = contact_data
                            break
                
                if contact:
                    # Use the stored path information if available
                    out_path = contact.get('out_path', '')
                    out_path_len = contact.get('out_path_len', -1)
                    
                    if out_path_len == 0:
                        self.logger.debug(f"Direct connection to {sender_id}")
                        return 0, "Direct"
                    elif out_path_len > 0:
                        # Format the path string with two-character node prefixes
                        path_string = self._format_path_string(out_path)
                        self.logger.debug(f"Stored path to {sender_id}: {out_path_len} hops via {path_string}")
                        return out_path_len, path_string
                    else:
                        # Path not set - use basic info
                        self.logger.debug(f"No stored path for {sender_id}, using basic info")
                        return 255, "No stored path"
                else:
                    self.logger.debug(f"Contact {sender_id} not found in contacts")
                    return 255, "Unknown"  # Unknown path
            
            return 255, "Unknown"  # Fallback to unknown
            
        except Exception as e:
            self.logger.error(f"Error discovering message path: {e}")
            return 255
    
    # CLI path discovery removed - focusing only on packet decoding
    
    async def _debug_decode_message_path(self, message: MeshMessage, sender_id: str, rf_data: dict):
        """
        Debug method to decode and log path information for ALL incoming messages.
        This runs regardless of whether the message matches keywords, helping with
        network topology debugging.
        
        Args:
            message: The received message
            sender_id: The name or ID of the sender
            rf_data: The RF data containing pubkey information
        """
        try:
            if not rf_data:
                self.logger.debug(f"🔍 DEBUG PATH: No RF data available for {sender_id}")
                return
            
            pubkey_prefix = rf_data.get('pubkey_prefix', '')
            if not pubkey_prefix:
                self.logger.debug(f"🔍 DEBUG PATH: No pubkey prefix for {sender_id}")
                return
            
            # Try to find the contact to get stored path information
            if hasattr(self.bot.meshcore, 'contacts') and self.bot.meshcore.contacts:
                contact = None
                
                # Look for contact by name first
                for contact_key, contact_data in self.bot.meshcore.contacts.items():
                    if contact_data.get('adv_name') == sender_id:
                        contact = contact_data
                        break
                
                # If not found by name, try by pubkey prefix
                if not contact:
                    for contact_key, contact_data in self.bot.meshcore.contacts.items():
                        if contact_data.get('public_key', '').startswith(pubkey_prefix):
                            contact = contact_data
                            break
                
                if contact:
                    out_path = contact.get('out_path', '')
                    out_path_len = contact.get('out_path_len', -1)
                    
                    if out_path_len == 0:
                        self.logger.info(f"🔍 DEBUG PATH: {sender_id} → Direct connection")
                    elif out_path_len > 0:
                        path_string = self._format_path_string(out_path)
                        self.logger.info(f"🔍 DEBUG PATH: {sender_id} → {path_string} ({out_path_len} hops)")
                    else:
                        self.logger.info(f"🔍 DEBUG PATH: {sender_id} → Path not set (no stored path)")
                else:
                    self.logger.info(f"🔍 DEBUG PATH: {sender_id} → Contact not found in contacts list")
            else:
                self.logger.debug(f"🔍 DEBUG PATH: No contacts available for {sender_id}")
                
        except Exception as e:
            self.logger.error(f"Error in debug path decoding: {e}")
    
    async def _debug_decode_packet_for_message(self, message: MeshMessage, sender_id: str, rf_data: dict):
        """
        Debug method to decode and log packet information for ALL incoming messages.
        This provides comprehensive packet analysis for debugging purposes.
        
        Args:
            message: The received message
            sender_id: The name or ID of the sender
            rf_data: The RF data containing raw packet information
        """
        try:
            if not rf_data:
                self.logger.debug(f"🔍 DEBUG PACKET: No RF data available for {sender_id}")
                return
            
            raw_hex = rf_data.get('raw_hex', '')
            if not raw_hex:
                self.logger.debug(f"🔍 DEBUG PACKET: No raw_hex in RF data for {sender_id}")
                return
            
            self.logger.debug(f"🔍 DEBUG PACKET: Attempting to decode packet for {sender_id}")
            self.logger.debug(f"🔍 DEBUG PACKET: Raw hex length: {len(raw_hex)} chars")
            self.logger.debug(f"🔍 DEBUG PACKET: Raw hex start: {raw_hex[:32]}...")
            
            # Log the extracted payload information from RX_LOG_DATA
            extracted_payload = rf_data.get('payload', '')
            payload_length = rf_data.get('payload_length', 0)
            
            if extracted_payload:
                self.logger.debug(f"🔍 DEBUG PACKET: Extracted payload length: {payload_length}")
                self.logger.debug(f"🔍 DEBUG PACKET: Extracted payload: {extracted_payload[:64]}...")
                
                # Try to decode the extracted payload directly
                try:
                    payload_bytes = bytes.fromhex(extracted_payload)
                    self.logger.debug(f"🔍 DEBUG PACKET: Payload bytes: {len(payload_bytes)} bytes")
                    
                    # Analyze payload structure based on MeshCore documentation
                    if len(payload_bytes) >= 1:
                        # First byte might be payload type or flags
                        first_byte = payload_bytes[0]
                        self.logger.debug(f"🔍 DEBUG PACKET: First payload byte: 0x{first_byte:02x}")
                        
                        # Try to extract readable text from payload
                        try:
                            text_content = payload_bytes.decode('utf-8', errors='ignore')
                            if text_content and len(text_content) > 1:
                                self.logger.debug(f"🔍 DEBUG PACKET: Payload text content: '{text_content[:100]}...'")
                        except:
                            self.logger.debug(f"🔍 DEBUG PACKET: Payload not UTF-8 text")
                    
                except Exception as e:
                    self.logger.debug(f"🔍 DEBUG PACKET: Error analyzing extracted payload: {e}")
            else:
                self.logger.debug(f"🔍 DEBUG PACKET: No extracted payload available")
            
            # NOTE: Raw packet decoding is fundamentally flawed
            # The raw hex data does NOT follow the documented MeshCore packet structure
            # Even mctomqtt.py has the same issue when trying to decode raw data
            # 
            # Instead, we should use the structured event data which already provides:
            # - path_len from channel message events
            # - SNR/RSSI from RX_LOG_DATA events
            # - message content from the event payload
            #
            # The raw hex appears to be encrypted/encoded data that cannot be decoded
            # without the proper keys or understanding of the actual packet format
            self.logger.debug(f"🔍 DEBUG PACKET: Raw hex length: {len(raw_hex)} chars")
            self.logger.debug(f"🔍 DEBUG PACKET: Raw hex start: {raw_hex[:32]}...")
            self.logger.debug(f"🔍 DEBUG PACKET: Raw hex appears to be encrypted/encoded data")
            self.logger.debug(f"🔍 DEBUG PACKET: Cannot decode without proper packet format understanding")
            self.logger.debug(f"🔍 DEBUG PACKET: Using structured event data instead (path_len, SNR, RSSI)")
            
            # Log the extracted payload information from RX_LOG_DATA
            extracted_payload = rf_data.get('payload', '')
            payload_length = rf_data.get('payload_length', 0)
            
            if extracted_payload:
                self.logger.debug(f"🔍 DEBUG PACKET: Extracted payload length: {payload_length}")
                self.logger.debug(f"🔍 DEBUG PACKET: Extracted payload: {extracted_payload[:64]}...")
                
                # Try to decode the extracted payload directly
                try:
                    payload_bytes = bytes.fromhex(extracted_payload)
                    self.logger.debug(f"🔍 DEBUG PACKET: Payload bytes: {len(payload_bytes)} bytes")
                    
                    # Analyze payload structure based on MeshCore documentation
                    if len(payload_bytes) >= 1:
                        # First byte might be payload type or flags
                        first_byte = payload_bytes[0]
                        self.logger.debug(f"🔍 DEBUG PACKET: First payload byte: 0x{first_byte:02x}")
                        
                        # Try to extract readable text from payload
                        try:
                            text_content = payload_bytes.decode('utf-8', errors='ignore')
                            if text_content and len(text_content) > 1:
                                self.logger.debug(f"🔍 DEBUG PACKET: Payload text content: '{text_content[:100]}...'")
                        except:
                            self.logger.debug(f"🔍 DEBUG PACKET: Payload not UTF-8 text")
                    
                except Exception as e:
                    self.logger.debug(f"🔍 DEBUG PACKET: Error analyzing extracted payload: {e}")
            else:
                self.logger.debug(f"🔍 DEBUG PACKET: No extracted payload available")
                
        except Exception as e:
            self.logger.error(f"Error in debug packet decoding: {e}")
    
    def _format_path_string(self, hex_path: str) -> str:
        """
        Convert a hex path string to the two-character node prefix format.
        
        Args:
            hex_path: Hex string representing the path (e.g., "01025f7e")
            
        Returns:
            str: Formatted path string (e.g., "01,02,5f,7e")
        """
        try:
            if not hex_path:
                return "Direct"
            
            # Convert hex to bytes and extract one-byte chunks for two-character format
            path_bytes = bytes.fromhex(hex_path)
            path_nodes = []
            
            for i in range(len(path_bytes)):
                # Extract each byte and convert to two-character hex
                node_id = path_bytes[i]
                path_nodes.append(f"{node_id:02x}")
            
            if path_nodes:
                return ",".join(path_nodes)
            else:
                return "Direct"
                
        except Exception as e:
            self.logger.debug(f"Error formatting path string: {e}")
            return f"Raw: {hex_path[:16]}..."  # Fallback to showing raw hex
    
    async def process_message(self, message: MeshMessage):
        """Process a received message"""
        if not self.should_process_message(message):
            return
        
        self.logger.info(f"Processing message: {message.content}")
        
        # Check for advert command (DM only)
        if message.is_dm and message.content.strip().lower() == "advert":
            await self.bot.command_manager.handle_advert_command(message)
            return
        
        # Check for keywords and custom syntax
        keyword_matches = self.bot.command_manager.check_keywords(message)
        
        if keyword_matches:
            for keyword, response in keyword_matches:
                self.logger.info(f"Keyword '{keyword}' matched, responding")
                
                # Send response
                if message.is_dm:
                    await self.bot.command_manager.send_dm(message.sender_id, response)
                else:
                    await self.bot.command_manager.send_channel_message(message.channel, response)
        else:
            # Check for command objects if no keywords matched
            await self.bot.command_manager.execute_commands(message)
    
    def should_process_message(self, message: MeshMessage) -> bool:
        """Check if message should be processed by the bot"""
        # Check if bot is enabled
        if not self.bot.config.getboolean('Bot', 'enabled'):
            return False
        
        # Check if sender is banned
        if message.sender_id and message.sender_id in self.bot.command_manager.banned_users:
            self.logger.debug(f"Ignoring message from banned user: {message.sender_id}")
            return False
        
        # Check if channel is monitored
        if not message.is_dm and message.channel and message.channel not in self.bot.command_manager.monitor_channels:
            self.logger.debug(f"Channel {message.channel} not in monitored channels: {self.bot.command_manager.monitor_channels}")
            return False
        
        # Check if DMs are enabled
        if message.is_dm and not self.bot.config.getboolean('Channels', 'respond_to_dms'):
            self.logger.debug("DMs are disabled")
            return False
        
        return True
