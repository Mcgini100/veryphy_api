import requests
import os
import json
from datetime import datetime

# API Base URL
BASE_URL = "http://localhost:8000/api/v1"

def test_health_check():
    """Test health check endpoint."""
    print("\n1. Testing Health Check...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_upload_certificate(file_path):
    """Test certificate upload."""
    print("\n2. Testing Certificate Upload...")
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'image/png')}
        data = {
            'embed_hash': True,
            'add_watermark': True,
            'watermark_text': 'BSc-12700'
        }
        response = requests.post(f"{BASE_URL}/certificates/upload", files=files, data=data)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json() if response.status_code == 200 else None

def test_verify_certificate(file_path, expected_hash=None):
    """Test certificate verification."""
    print("\n3. Testing Certificate Verification...")
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'image/png')}
        data = {
            'expected_hash': expected_hash,
            'use_enhanced_extraction': True,
            'check_database': True
        }
        response = requests.post(f"{BASE_URL}/verify/", files=files, data=data)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json() if response.status_code == 200 else None

def test_list_certificates():
    """Test listing certificates."""
    print("\n4. Testing List Certificates...")
    response = requests.get(f"{BASE_URL}/certificates/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json() if response.status_code == 200 else []

def test_get_certificate(certificate_number):
    """Test getting specific certificate."""
    print(f"\n5. Testing Get Certificate: {certificate_number}")
    response = requests.get(f"{BASE_URL}/certificates/{certificate_number}")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json() if response.status_code == 200 else None

def test_extract_hash(file_path):
    """Test hash extraction."""
    print("\n6. Testing Hash Extraction...")
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'image/png')}
        data = {'use_enhanced': True}
        response = requests.post(f"{BASE_URL}/verify/extract-hash", files=files, data=data)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json() if response.status_code == 200 else None

def test_batch_verification(file_paths):
    """Test batch verification."""
    print("\n7. Testing Batch Verification...")
    files = []
    for file_path in file_paths:
        with open(file_path, 'rb') as f:
            files.append(('files', (os.path.basename(file_path), f.read(), 'image/png')))
    
    response = requests.post(f"{BASE_URL}/verify/batch", files=files)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json() if response.status_code == 200 else None

def test_statistics():
    """Test statistics endpoint."""
    print("\n8. Testing Statistics...")
    response = requests.get(f"{BASE_URL}/certificates/stats/summary")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json() if response.status_code == 200 else None

def create_test_certificates():
    """Create test certificate images."""
    print("\nCreating test certificates...")
    
    # Create a simple test certificate
    from PIL import Image, ImageDraw, ImageFont
    
    # Create test certificate 1
    img1 = Image.new('RGB', (1200, 800), color='white')
    draw1 = ImageDraw.Draw(img1)
    
    # Add certificate content
    draw1.text((600, 100), "SOUTHERN ACADEMY OF ARTS AND SCIENCES", anchor="mm", fill="black")
    draw1.text((600, 150), "FACULTY OF HEALTH SCIENCES AND MEDICAL RESEARCH", anchor="mm", fill="black")
    draw1.text((600, 250), "Bachelor of Science Honours in Data Science and Analytics", anchor="mm", fill="black")
    draw1.text((600, 350), "WE HEREBY CERTIFY THAT", anchor="mm", fill="black")
    draw1.text((600, 400), "Test Student Name", anchor="mm", fill="black")
    draw1.text((200, 600), "Date: 15 June 2025", fill="black")
    draw1.text((1000, 600), "BSc-TEST001", fill="black")
    
    img1.save("test_certificate_1.png")
    
    # Create test certificate 2 with embedded hash pattern
    img2 = img1.copy()
    draw2 = ImageDraw.Draw(img2)
    
    # Add hash pattern on left margin
    hash_test = "a" * 64  # Simple test hash
    start_x, start_y = 100, 300
    for i, char in enumerate(hash_test):
        y = start_y + (i * 18)
        gray = 240 - (int(char, 16) * 8)
        draw2.rectangle([start_x, y, start_x + 9, y + 9], fill=(gray, gray, gray))
    
    img2.save("test_certificate_2.png")
    
    print("Created test_certificate_1.png and test_certificate_2.png")
    return ["test_certificate_1.png", "test_certificate_2.png"]

def run_all_tests():
    """Run all API tests."""
    print("="*60)
    print("Certificate Verification API Test Suite")
    print("="*60)
    
    # Create test certificates if they don't exist
    test_files = []
    if not os.path.exists("test_certificate_1.png"):
        test_files = create_test_certificates()
    else:
        test_files = ["test_certificate_1.png", "test_certificate_2.png"]
    
    # Expected hash for testing
    expected_hash = "b7f069b63ad42d547a116fea8d49f878bb792beaa1fe07f2dfc3cd64f10c8801"
    
    try:
        # 1. Health Check
        health_ok = test_health_check()
        if not health_ok:
            print("\n❌ Health check failed. Is the API running?")
            return
        
        # 2. Upload Certificate
        upload_result = test_upload_certificate(test_files[0])
        if upload_result:
            print("\n✅ Upload successful")
        
        # 3. Verify Certificate
        verify_result = test_verify_certificate(test_files[0], expected_hash)
        if verify_result:
            print(f"\n✅ Verification completed: {verify_result['verification_status']}")
        
        # 4. List Certificates
        certificates = test_list_certificates()
        print(f"\n✅ Found {len(certificates)} certificates")
        
        # 5. Get Specific Certificate
        if certificates:
            cert_number = certificates[0]['certificate_number']
            cert_details = test_get_certificate(cert_number)
            if cert_details:
                print("\n✅ Retrieved certificate details")
        
        # 6. Extract Hash
        hash_result = test_extract_hash(test_files[1])
        if hash_result:
            print(f"\n✅ Hash extraction completed: {hash_result['hash'][:16]}...")
        
        # 7. Batch Verification
        batch_result = test_batch_verification(test_files)
        if batch_result:
            print(f"\n✅ Batch verification completed: {batch_result['successful']}/{batch_result['total_processed']} successful")
        
        # 8. Statistics
        stats = test_statistics()
        if stats:
            print("\n✅ Statistics retrieved")
        
        print("\n" + "="*60)
        print("All tests completed!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        print("\nMake sure the API is running on http://localhost:8000")

if __name__ == "__main__":
    run_all_tests()