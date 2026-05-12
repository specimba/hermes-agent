$script = @'
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

def test_connection(uri, token, cluster_name):
    """Test Zilliz connection using pymilvus"""
    try:
        from pymilvus import connections, utility
        print(f"Testing {cluster_name}...")
        print(f"URI: {uri}")
        
        # Connect to the cluster
        connections.connect(
            alias=cluster_name,
            uri=uri,
            token=token
        )
        
        # List collections to verify connection
        collections = utility.list_collections(using=cluster_name)
        print(f"✅ SUCCESS: Connected to {cluster_name}")
        print(f"   Collections found: {collections}")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {cluster_name}")
        print(f"   Error: {str(e)}")
        return False

def main():
    print("=" * 60)
    print("NEXUS OS - Zilliz Cluster Reconfiguration Test")
    print("=" * 60)
    
    # Get credentials from .env
    serverless_uri = os.getenv('ZILLIZ_Serverless-01_URI')
    serverless_token = os.getenv('ZILLIZ_Serverless-01_TOKEN')
    free_uri = os.getenv('ZILLIZ_Free-01_TOKEN_URI')
    free_token = os.getenv('ZILLIZ_Free-01_TOKEN')
    
    if not all([serverless_uri, serverless_token, free_uri, free_token]):
        print("❌ ERROR: Missing Zilliz credentials in .env file")
        print("   Please check your .env file contains:")
        print("   - ZILLIZ_Serverless-01_URI")
        print("   - ZILLIZ_Serverless-01_TOKEN")
        print("   - ZILLIZ_Free-01_TOKEN_URI")
        print("   - ZILLIZ_Free-01_TOKEN")
        sys.exit(1)
    
    # Test both clusters
    results = []
    results.append(test_connection(serverless_uri, serverless_token, "Serverless-01"))
    results.append(test_connection(free_uri, free_token, "Free-01"))
    
    # Create beacon file
    docs_dir = Path(__file__).parent.parent / 'docs'
    docs_dir.mkdir(exist_ok=True)
    beacon_path = docs_dir / 'ZILLIZ_BEACON.md'
    
    if all(results):
        status = "READY"
        print("\n" + "=" * 60)
        print("✅ ALL CLUSTERS OPERATIONAL - BEACON SET TO READY")
        print("=" * 60)
    else:
        status = "FAILED"
        print("\n" + "=" * 60)
        print("❌ CLUSTER CONNECTION FAILED - CHECK .env CREDENTIALS")
        print("=" * 60)
    
    beacon_content = f"""# Zilliz Cluster Beacon
Status: {status}
Timestamp: {Path(__file__).parent.parent.name}
Cluster A (Serverless-01): {'✅' if results[0] else '❌'}
Cluster B (Free-01): {'✅' if results[1] else '❌'}

Agents: Check this file before any Zilliz operation.
If status != READY, run: python boot/reconfigure_zilliz.py
"""
    
    with open(beacon_path, 'w', encoding='utf-8') as f:
        f.write(beacon_content)
    
    print(f"\nBeacon file created: {beacon_path}")
    print(f"Status: {status}")
    
    if status == "READY":
        print("\n🚀 Submit this task to Gastown:")
        print("gt_sling [rig_id=32c6c066-3630-409b-9f13-9c84dec5f780, title=\"Zilliz Beacon Active\", body=\"Check docs/ZILLIZ_BEACON.md (status=READY). Proceed with operations.\"]")
    
    return 0 if status == "READY" else 1

if __name__ == "__main__":
    sys.exit(main())
'@

Set-Content -Path "boot\reconfigure_zilliz.py" -Value $script -Encoding UTF8