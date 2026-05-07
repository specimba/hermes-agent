import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def test_connection(uri, token, cluster_name):
    try:
        from pymilvus import connections, utility
        print(f"Testing {cluster_name}...")
        connections.connect(alias=cluster_name, uri=uri, token=token)
        collections = utility.list_collections(using=cluster_name)
        print(f"SUCCESS: Connected to {cluster_name}")
        print(f"Collections: {collections}")
        return True
    except Exception as e:
        print(f"FAILED: {cluster_name} - {str(e)}")
        return False

def main():
    print("NEXUS OS - Zilliz Reconfiguration")
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
    
    s_uri = os.getenv('ZILLIZ_Serverless-01_URI')
    s_token = os.getenv('ZILLIZ_Serverless-01_TOKEN')
    f_uri = os.getenv('ZILLIZ_Free-01_TOKEN_URI')
    f_token = os.getenv('ZILLIZ_Free-01_TOKEN')
    
    if not all([s_uri, s_token, f_uri, f_token]):
        print("ERROR: Missing credentials in .env")
        sys.exit(1)
    
    r1 = test_connection(s_uri, s_token, "Serverless-01")
    r2 = test_connection(f_uri, f_token, "Free-01")
    
    docs_dir = Path(__file__).parent.parent / 'docs'
    docs_dir.mkdir(exist_ok=True)
    status = "READY" if (r1 and r2) else "FAILED"
    
    beacon = f"# Zilliz Beacon\nStatus: {status}\nClusters: Serverless-01 ({r1}), Free-01 ({r2})\nAgents: Check status before operations."
    (docs_dir / 'ZILLIZ_BEACON.md').write_text(beacon)
    
    print(f"BEACON STATUS: {status}")
    if status == "READY":
        print("Gastown Task: gt_sling [rig_id=32c6c066-3630-409b-9f13-9c84dec5f780, title='Zilliz Beacon Active', body='Status READY']")

if __name__ == "__main__":
    main()
