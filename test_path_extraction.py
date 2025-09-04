#!/usr/bin/env python3
"""
Test script to verify path extraction logic
"""

def test_path_extraction():
    """Test the path extraction logic with sample contact data"""
    
    # Sample contact data from the debug output
    sample_contacts = {
        '460728508c17ef336412a223144d3a623215162682045c44fef7241af0161923': {
            'public_key': '460728508c17ef336412a223144d3a623215162682045c44fef7241af0161923',
            'out_path': '5f',
            'out_path_len': 1,
            'adv_name': 'HOWL'
        },
        '5fbfb6c8937581fa427082a7ae60fa57aa59798ea39836c7e0aeccfc5f0274c3': {
            'public_key': '5fbfb6c8937581fa427082a7ae60fa57aa59798ea39836c7e0aeccfc5f0274c3',
            'out_path': '01',
            'out_path_len': 1,
            'adv_name': 'N7JMV-PAINE-RP'
        },
        '7e7662676f7f0850a8a355baafbfc1eb7b4174c340442d7d7161c9474a2c9400': {
            'public_key': '7e7662676f7f0850a8a355baafbfc1eb7b4174c340442d7d7161c9474a2c9400',
            'out_path': '015f',
            'out_path_len': 2,
            'adv_name': 'WW7STR/PugetMesh Cougar'
        },
        '15a24fcbc0dd2d2a4f80c7930cbb1de2139883bdd42b678afb19a4fa1ee1a6c8': {
            'public_key': '15a24fcbc0dd2d2a4f80c7930cbb1de2139883bdd42b678afb19a4fa1ee1a6c8',
            'out_path': '015f',
            'out_path_len': 2,
            'adv_name': 'Hillcrest Repeater'
        },
        '2c3d703f6649e613639c12ba97a399d16ec9f112a16089eedaca3ad450566dc8': {
            'public_key': '2c3d703f6649e613639c12ba97a399d16ec9f112a16089eedaca3ad450566dc8',
            'out_path': '015fd0',
            'out_path_len': 3,
            'adv_name': 'Lower Capitol Hill'
        },
        '1ffbd69aa03faadc0f40b2146665f2435fc8915b21e910e7125dfeba547646d9': {
            'public_key': '1ffbd69aa03faadc0f40b2146665f2435fc8915b21e910e7125dfeba547646d9',
            'out_path': '015f7e',
            'out_path_len': 3,
            'adv_name': 'First Hill Skyline'
        },
        'eaf3a101c6b2ff28b21f60439bfacbbfb7b24ad46c65761dc0ac0d76bcf888d3': {
            'public_key': 'eaf3a101c6b2ff28b21f60439bfacbbfb7b24ad46c65761dc0ac0d76bcf888d3',
            'out_path': '015f4a8094',
            'out_path_len': 5,
            'adv_name': 'Cowen West'
        }
    }
    
    def extract_path_info(pubkey_prefix, contacts):
        """Extract path information from contacts using pubkey_prefix"""
        path_info = "Unknown"
        
        for contact_key, contact_data in contacts.items():
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
                        print(f"Found path info: {path_info}")
                    except Exception as e:
                        print(f"Error converting path: {e}")
                        path_info = f"Path: {out_path} ({out_path_len} hops)"
                    break
                elif out_path_len == 0:
                    path_info = "Direct"
                    print(f"Direct connection: {path_info}")
                    break
                else:
                    path_info = "Unknown path"
                    print(f"No path info available: {path_info}")
                    break
        
        return path_info
    
    # Test with different pubkey prefixes
    test_cases = [
        ('460728508c17', 'HOWL'),
        ('5fbfb6c89375', 'N7JMV-PAINE-RP'),
        ('7e7662676f7f', 'WW7STR/PugetMesh Cougar'),
        ('15a24fcbc0dd', 'Hillcrest Repeater'),
        ('2c3d703f6649', 'Lower Capitol Hill'),
        ('1ffbd69aa03f', 'First Hill Skyline'),
        ('eaf3a101c6b2', 'Cowen West'),
        ('nonexistent', 'Non-existent contact')
    ]
    
    print("Testing path extraction logic:")
    print("=" * 50)
    
    for pubkey_prefix, expected_name in test_cases:
        print(f"\nTesting {expected_name} (prefix: {pubkey_prefix}):")
        path_info = extract_path_info(pubkey_prefix, sample_contacts)
        print(f"Result: {path_info}")

if __name__ == "__main__":
    test_path_extraction()
