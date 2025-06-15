import requests
import json
import os

# API Base URL
BASE_URL = "http://localhost:8000/api/v1"

# The expected hash you provided
EXPECTED_HASH = "b7f069b63ad42d547a116fea8d49f878bb792beaa1fe07f2dfc3cd64f10c8801"

def test_original_certificates():
    """Test API with your original certificate images."""
    
    print("="*60)
    print("Testing API with Original Certificate Images")
    print("="*60)
    
    # Check if files exist
    if not os.path.exists("input_file_0.png") or not os.path.exists("input_file_1.jpg"):
        print("\nError: Original test images not found!")
        print("Please ensure input_file_0.png and input_file_1.jpg are in the current directory.")
        return
    
    # Test 1: Verify the digital certificate (should pass hash verification)
    print("\n1. Testing Digital Certificate (input_file_0.png)")
    print("-" * 40)
    with open("input_file_0.png", 'rb') as f:
        files = {'file': ('input_file_0.png', f, 'image/png')}
        data = {
            'expected_hash': EXPECTED_HASH,
            'use_enhanced_extraction': 'true',
            'check_database': 'true'
        }
        response = requests.post(f"{BASE_URL}/verify/", files=files, data=data)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Verification Status: {result['verification_status']}")
        print(f"Confidence: {result['confidence']:.2%}")
        print(f"Hash Match: {'✅ YES' if result['verification_status'] == 'VERIFIED' else '❌ NO'}")
        
        if result['certificate_data']:
            print("\nExtracted Certificate Data:")
            for key, value in result['certificate_data'].items():
                if value:
                    print(f"  {key}: {value}")
    
    # Test 2: Verify the scanned certificate (should verify by data)
    print("\n\n2. Testing Scanned Certificate (input_file_1.jpg)")
    print("-" * 40)
    with open("input_file_1.jpg", 'rb') as f:
        files = {'file': ('input_file_1.jpg', f, 'image/jpeg')}
        data = {
            'expected_hash': EXPECTED_HASH,
            'use_enhanced_extraction': 'true',
            'check_database': 'true'
        }
        response = requests.post(f"{BASE_URL}/verify/", files=files, data=data)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Verification Status: {result['verification_status']}")
        print(f"Confidence: {result['confidence']:.2%}")
        
        if result['verification_status'] == 'VERIFIED_BY_DATA':
            print("✅ Certificate verified through data matching (hash was corrupted by scanning)")
        elif result['verification_status'] == 'CORRUPTED_HASH':
            print("⚠️ Hash corrupted by print/scan cycle")
        
        if result['certificate_data']:
            print("\nExtracted Certificate Data:")
            for key, value in result['certificate_data'].items():
                if value:
                    print(f"  {key}: {value}")
    
    # Test 3: Extract hash from digital certificate
    print("\n\n3. Extracting Hash from Digital Certificate")
    print("-" * 40)
    with open("input_file_0.png", 'rb') as f:
        files = {'file': ('input_file_0.png', f, 'image/png')}
        data = {'use_enhanced': 'true'}
        response = requests.post(f"{BASE_URL}/verify/extract-hash", files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Extracted Hash: {result['hash']}")
        print(f"Confidence: {result['confidence']:.2%}")
        print(f"Matches Expected: {'✅ YES' if result['hash'] == EXPECTED_HASH else '❌ NO'}")
    
    # Test 4: Extract hash from scanned certificate (should show corruption)
    print("\n\n4. Extracting Hash from Scanned Certificate")
    print("-" * 40)
    with open("input_file_1.jpg", 'rb') as f:
        files = {'file': ('input_file_1.jpg', f, 'image/jpeg')}
        data = {'use_enhanced': 'true'}
        response = requests.post(f"{BASE_URL}/verify/extract-hash", files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Extracted Hash: {result['hash'][:32]}...")
        print(f"Confidence: {result['confidence']:.2%}")
        print(f"Unique Characters: {result['unique_characters']}")
        print(f"Is Corrupted: {'❌ YES' if result['is_corrupted'] else '✅ NO'}")
    
    # Test 5: Upload certificates to database
    print("\n\n5. Uploading Certificates to Database")
    print("-" * 40)
    
    for filename in ["input_file_0.png", "input_file_1.jpg"]:
        print(f"\nUploading {filename}...")
        with open(filename, 'rb') as f:
            files = {'file': (filename, f, 'image/png' if filename.endswith('.png') else 'image/jpeg')}
            data = {
                'embed_hash': 'false',  # Don't re-embed since it already has hash
                'add_watermark': 'false'
            }
            response = requests.post(f"{BASE_URL}/certificates/upload", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Upload successful: {result['filename']}")
            print(f"   Hash: {result['hash']}")
    
    # Test 6: List all certificates
    print("\n\n6. Listing All Certificates in Database")
    print("-" * 40)
    response = requests.get(f"{BASE_URL}/certificates/")
    
    if response.status_code == 200:
        certificates = response.json()
        print(f"Found {len(certificates)} certificates:")
        for cert in certificates:
            print(f"\n  Certificate: {cert['certificate_number']}")
            print(f"  Status: {cert['verification_status']}")
            print(f"  Confidence: {cert['confidence']:.2%}")
            print(f"  Source: {cert.get('source_image', 'Unknown')}")
    
    # Test 7: Get specific certificate details
    print("\n\n7. Getting Details for BSc-12700")
    print("-" * 40)
    response = requests.get(f"{BASE_URL}/certificates/BSc-12700")
    
    if response.status_code == 200:
        cert = response.json()
        print("Certificate Details:")
        data = cert.get('certificate_data', {})
        for key, value in data.items():
            if value and key not in ['hash', 'verification_history']:
                print(f"  {key}: {value}")
    
    # Test 8: Check verification history
    print("\n\n8. Checking Verification History")
    print("-" * 40)
    response = requests.get(f"{BASE_URL}/certificates/BSc-12700/history")
    
    if response.status_code == 200:
        history = response.json()
        print(f"Total verifications: {history['total_verifications']}")
        if history['history']:
            print("\nRecent verifications:")
            for record in history['history'][-3:]:  # Show last 3
                print(f"  - {record['timestamp']}: {record['status']} (confidence: {record['confidence']:.2%})")
    
    # Test 9: Batch verification
    print("\n\n9. Batch Verification of Both Certificates")
    print("-" * 40)
    files = []
    for filename in ["input_file_0.png", "input_file_1.jpg"]:
        with open(filename, 'rb') as f:
            content_type = 'image/png' if filename.endswith('.png') else 'image/jpeg'
            files.append(('files', (filename, f.read(), content_type)))
    
    # Provide expected hashes for both files
    batch_data = {
        'expected_hashes': json.dumps({
            'input_file_0.png': EXPECTED_HASH,
            'input_file_1.jpg': EXPECTED_HASH
        })
    }
    
    response = requests.post(f"{BASE_URL}/verify/batch", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Total Processed: {result['total_processed']}")
        print(f"Successful: {result['successful']}")
        print(f"Failed: {result['failed']}")
        print(f"Processing Time: {result['processing_time']:.2f}s")
        
        print("\nIndividual Results:")
        for i, verification in enumerate(result['results']):
            print(f"\n  File {i+1}:")
            print(f"    Status: {verification['verification_status']}")
            print(f"    Confidence: {verification['confidence']:.2%}")
    
    # Test 10: Database statistics
    print("\n\n10. Database Statistics")
    print("-" * 40)
    response = requests.get(f"{BASE_URL}/certificates/stats/summary")
    
    if response.status_code == 200:
        stats = response.json()
        print(f"Total Certificates: {stats['total_certificates']}")
        print(f"Total Verifications: {stats['total_verifications']}")
        print(f"Database Size: {stats['database_size_bytes']} bytes")
        print("\nStatus Distribution:")
        for status, count in stats['status_distribution'].items():
            print(f"  {status}: {count}")
    
    print("\n" + "="*60)
    print("Testing completed!")
    print("="*60)
    print("\nSummary:")
    print("- Digital certificate (input_file_0.png): Should verify successfully via hash")
    print("- Scanned certificate (input_file_1.jpg): Should verify via data matching")
    print("- Both certificates contain the same data for BSc-12700")

if __name__ == "__main__":
    test_original_certificates()