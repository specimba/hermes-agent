#!/usr/bin/env python3
"""
Zilliz Connection Test Script (Updated for Serverless Auth)
Tests connectivity to both Zilliz clusters (Serverless & Town)
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_zilliz_connection():
    """Test Zilliz cluster connections"""
    
    print("🔍 Zilliz Connection Test")
    print("=" * 60)
    
    try:
        from pymilvus import connections, utility
    except ImportError:
        print("❌ ERROR: pymilvus not installed. Run: pip install pymilvus")
        return False

    # Configuration
    clusters = {
        "nexus-serverless (Events/Failures)": {
            "uri": os.getenv("ZILLIZ_SERVERLESS_URI"),
            "token": os.getenv("ZILLIZ_SERVERLESS_TOKEN"),
            "user": os.getenv("ZILLIZ_SERVERLESS_USER"),
            "password": os.getenv("ZILLIZ_SERVERLESS_PASSWORD")
        },
        "nexus-os-town (Trust/Governance)": {
            "uri": os.getenv("ZILLIZ_TOWN_URI"),
            "token": os.getenv("ZILLIZ_TOWN_TOKEN"),
            "user": os.getenv("ZILLIZ_TOWN_USER"),
            "password": os.getenv("ZILLIZ_TOWN_PASSWORD")
        }
    }

    all_success = True

    for name, config in clusters.items():
        print(f"\n📡 Testing: {name}")
        print("-" * 40)
        
        uri = config["uri"]
        token = config["token"]
        user = config["user"]
        password = config["password"]

        if not uri:
            print(f"⚠️  SKIP: Missing URI in .env")
            all_success = False
            continue

        # Handle Serverless User:Pass format
        if not token and user and password:
            token = f"{user}:{password}"
        
        # If token is still missing or looks like a placeholder
        if not token or "YourActualPassword" in str(token):
            print(f"⚠️  SKIP: Missing or placeholder Token/User:Pass in .env")
            print(f"   Check: ZILLIZ_{'SERVERLESS' if 'serverless' in name.lower() else 'TOWN'}_TOKEN")
            print(f"   OR set ZILLIZ_..._USER and ZILLIZ_..._PASSWORD")
            all_success = False
            continue

        try:
            alias = name.replace(" ", "_").replace("-", "_")
            
            # Disconnect if already connected
            try:
                connections.disconnect(alias=alias)
            except:
                pass

            # Connect using token (works for both API Key and User:Pass)
            connections.connect(
                alias=alias,
                uri=uri,
                token=token
            )
            print(f"✅ Connection Successful (Token Auth)")
            
            # List Collections
            collections = utility.list_collections(using=alias)
            print(f"📦 Collections Found: {len(collections)}")
            for col in collections:
                print(f"   - {col}")
                
            # Disconnect
            connections.disconnect(alias=alias)
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Connection Failed: {type(e).__name__}")
            
            # Try alternative: explicit user/pass if token failed
            if "UNAUTHENTICATED" in error_msg and user and password:
                print("   🔄 Retrying with explicit user/password...")
                try:
                    connections.connect(
                        alias=alias,
                        uri=uri,
                        user=user,
                        password=password
                    )
                    print(f"   ✅ Connection Successful (User/Pass Auth)")
                    
                    collections = utility.list_collections(using=alias)
                    print(f"   📦 Collections Found: {len(collections)}")
                    for col in collections:
                        print(f"      - {col}")
                    
                    connections.disconnect(alias=alias)
                    continue # Success on retry
                except Exception as e2:
                    print(f"   ❌ Retry Failed: {str(e2)}")
            
            all_success = False

    print("\n" + "=" * 60)
    if all_success:
        print("🎉 All Zilliz clusters connected successfully!")
        return True
    else:
        print("⚠️  Some connections failed. Check .env and credentials.")
        return False

if __name__ == "__main__":
    success = test_zilliz_connection()
    sys.exit(0 if success else 1)
