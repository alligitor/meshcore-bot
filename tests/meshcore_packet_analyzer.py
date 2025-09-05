#!/usr/bin/env python3
"""
MeshCore Packet Analyzer
This script helps analyze and decode MeshCore binary packets
"""

import struct
from datetime import datetime
from typing import Dict, Any, Optional


class MeshCorePacketAnalyzer:
    """Analyzes MeshCore binary packets"""
    
    def __init__(self):
        self.packet_count = 0
    
    def analyze_packet(self, raw_data: bytes) -> Dict[str, Any]:
        """Analyze a binary packet and extract information"""
        self.packet_count += 1
        
        analysis = {
            'packet_number': self.packet_count,
            'raw_hex': raw_data.hex(),
            'length': len(raw_data),
            'timestamp': datetime.now(),
            'analysis': {}
        }
        
        if len(raw_data) < 4:
            analysis['analysis']['error'] = 'Packet too short'
            return analysis
        
        # Extract basic packet structure
        # This is speculative - adapt based on actual MeshCore protocol
        
        # First byte might be packet type/header
        header = raw_data[0]
        analysis['analysis']['header'] = f"0x{header:02x}"
        
        # Second byte might be length or flags
        second_byte = raw_data[1]
        analysis['analysis']['second_byte'] = f"0x{second_byte:02x}"
        
        # Look for patterns
        analysis['analysis']['patterns'] = self._find_patterns(raw_data)
        
        # Try to extract potential fields
        analysis['analysis']['potential_fields'] = self._extract_potential_fields(raw_data)
        
        # Check for common MeshCore patterns
        analysis['analysis']['meshcore_patterns'] = self._check_meshcore_patterns(raw_data)
        
        return analysis
    
    def _find_patterns(self, data: bytes) -> Dict[str, Any]:
        """Find patterns in the binary data"""
        patterns = {}
        
        # Check for repeated bytes
        byte_counts = {}
        for byte in data:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1
        
        # Find most common bytes
        common_bytes = sorted(byte_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        patterns['common_bytes'] = [(f"0x{b:02x}", count) for b, count in common_bytes]
        
        # Check for sequences
        sequences = []
        for i in range(len(data) - 2):
            seq = data[i:i+3]
            if seq.count(seq[0]) == len(seq):  # All same byte
                sequences.append(f"0x{seq[0]:02x} repeated {len(seq)} times at position {i}")
        
        patterns['sequences'] = sequences
        
        return patterns
    
    def _extract_potential_fields(self, data: bytes) -> Dict[str, Any]:
        """Extract potential packet fields"""
        fields = {}
        
        if len(data) >= 4:
            # First 4 bytes might be a header
            fields['header_4bytes'] = data[:4].hex()
            
            # Next 4 bytes might be length or timestamp
            if len(data) >= 8:
                fields['next_4bytes'] = data[4:8].hex()
                
                # Try to interpret as length
                try:
                    length = struct.unpack('<I', data[4:8])[0]
                    fields['length_interpretation'] = length
                except:
                    pass
        
        # Look for text-like data
        text_candidates = []
        for i in range(len(data)):
            if 32 <= data[i] <= 126:  # Printable ASCII
                text_candidates.append(chr(data[i]))
            else:
                if text_candidates:
                    text = ''.join(text_candidates)
                    if len(text) >= 3:  # Only meaningful text
                        fields[f'text_at_{i-len(text)}'] = text
                    text_candidates = []
        
        # Check for any remaining text
        if text_candidates:
            text = ''.join(text_candidates)
            if len(text) >= 3:
                fields['text_at_end'] = text
        
        return fields
    
    def _check_meshcore_patterns(self, data: bytes) -> Dict[str, Any]:
        """Check for common MeshCore protocol patterns"""
        patterns = {}
        
        # Check for common MeshCore packet types
        if len(data) > 0:
            header = data[0]
            
            # These are speculative based on common packet protocols
            if header == 0x88:
                patterns['packet_type'] = 'Possible MeshCore data packet'
            elif header == 0x83:
                patterns['packet_type'] = 'Possible MeshCore control packet'
            elif header == 0x81:
                patterns['packet_type'] = 'Possible MeshCore acknowledgment'
            else:
                patterns['packet_type'] = f'Unknown packet type: 0x{header:02x}'
        
        # Check for potential node IDs or addresses
        if len(data) >= 8:
            # Look for potential 4-byte node ID
            potential_node_id = data[4:8]
            patterns['potential_node_id'] = potential_node_id.hex()
        
        # Check for potential message content
        if len(data) > 8:
            content_start = 8
            content = data[content_start:]
            
            # Try to find text content
            text_content = ""
            for byte in content:
                if 32 <= byte <= 126:  # Printable ASCII
                    text_content += chr(byte)
                else:
                    break
            
            if text_content:
                patterns['text_content'] = text_content
        
        return patterns
    
    def print_analysis(self, analysis: Dict[str, Any]):
        """Print packet analysis in a readable format"""
        print(f"\n=== Packet Analysis #{analysis['packet_number']} ===")
        print(f"Timestamp: {analysis['timestamp']}")
        print(f"Length: {analysis['length']} bytes")
        print(f"Raw Hex: {analysis['raw_hex']}")
        
        print("\n--- Header Analysis ---")
        if 'header' in analysis['analysis']:
            print(f"Header: {analysis['analysis']['header']}")
        if 'second_byte' in analysis['analysis']:
            print(f"Second Byte: {analysis['analysis']['second_byte']}")
        
        print("\n--- Patterns ---")
        patterns = analysis['analysis'].get('patterns', {})
        if 'common_bytes' in patterns:
            print("Most common bytes:")
            for byte, count in patterns['common_bytes']:
                print(f"  {byte}: {count} times")
        
        print("\n--- Potential Fields ---")
        fields = analysis['analysis'].get('potential_fields', {})
        for field, value in fields.items():
            print(f"  {field}: {value}")
        
        print("\n--- MeshCore Patterns ---")
        meshcore = analysis['analysis'].get('meshcore_patterns', {})
        for pattern, value in meshcore.items():
            print(f"  {pattern}: {value}")


def test_packet_analyzer():
    """Test the packet analyzer with sample data"""
    analyzer = MeshCorePacketAnalyzer()
    
    # Test with the packets we've seen
    test_packets = [
        bytes.fromhex('8830d405037e5fbd54c559a4df32702e'),
        bytes.fromhex('8830e505037e5f0154c559a4df32702e'),
        bytes.fromhex('882ef70a00f54621da57be35db1e5108'),
        # Add the packet from your DM
        bytes.fromhex('888388888188888388888188888388')
    ]
    
    print("MeshCore Packet Analyzer")
    print("=" * 50)
    
    for packet in test_packets:
        analysis = analyzer.analyze_packet(packet)
        analyzer.print_analysis(analysis)


if __name__ == "__main__":
    test_packet_analyzer()
