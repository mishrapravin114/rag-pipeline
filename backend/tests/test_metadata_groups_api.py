"""
Test script for metadata groups CRUD API endpoints
"""
import pytest
import httpx
from typing import Dict, Any
import asyncio

# Configuration
BASE_URL = "http://localhost:8090"
AUTH_ENDPOINT = f"{BASE_URL}/api/auth/login"
GROUPS_ENDPOINT = f"{BASE_URL}/api/metadata-groups"

# Test credentials (update as needed)
TEST_USERNAME = "admin"
TEST_PASSWORD = "admin123"


async def get_auth_token() -> str:
    """Get authentication token"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            AUTH_ENDPOINT,
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            raise Exception(f"Failed to authenticate: {response.text}")


async def test_metadata_groups_crud():
    """Test basic CRUD operations for metadata groups"""
    token = await get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        print("\n1. Testing LIST metadata groups...")
        response = await client.get(f"{GROUPS_ENDPOINT}/", headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Found {data['total']} groups")
            print(f"Groups: {[g['name'] for g in data['groups']]}")
        else:
            print(f"Error: {response.text}")
        
        print("\n2. Testing CREATE metadata group...")
        new_group = {
            "name": "Test Clinical Data",
            "description": "Group for clinical trial metadata",
            "color": "#10B981",
            "tags": ["clinical", "trials", "test"]
        }
        response = await client.post(f"{GROUPS_ENDPOINT}/", json=new_group, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 201:
            created_group = response.json()
            group_id = created_group["id"]
            print(f"Created group: {created_group['name']} (ID: {group_id})")
        else:
            print(f"Error: {response.text}")
            return
        
        print("\n3. Testing GET single metadata group...")
        response = await client.get(f"{GROUPS_ENDPOINT}/{group_id}", headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            group = response.json()
            print(f"Retrieved group: {group['name']}")
            print(f"  - Color: {group['color']}")
            print(f"  - Tags: {group['tags']}")
            print(f"  - Configurations: {group['configuration_count']}")
        else:
            print(f"Error: {response.text}")
        
        print("\n4. Testing UPDATE metadata group...")
        update_data = {
            "name": "Updated Clinical Data",
            "description": "Updated description for clinical trial metadata",
            "color": "#EF4444",
            "tags": ["clinical", "trials", "updated"]
        }
        response = await client.put(f"{GROUPS_ENDPOINT}/{group_id}", json=update_data, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            updated_group = response.json()
            print(f"Updated group: {updated_group['name']}")
            print(f"  - New color: {updated_group['color']}")
        else:
            print(f"Error: {response.text}")
        
        print("\n5. Testing DELETE metadata group...")
        response = await client.delete(f"{GROUPS_ENDPOINT}/{group_id}", headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 204:
            print("Group successfully deleted")
        else:
            print(f"Error: {response.text}")
        
        print("\n6. Testing orphaned configurations endpoint...")
        response = await client.get(f"{GROUPS_ENDPOINT}/configurations/orphaned", headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            orphaned = response.json()
            print(f"Found {len(orphaned)} orphaned configurations")
        else:
            print(f"Error: {response.text}")
        
        print("\n7. Testing assign orphaned to default...")
        response = await client.post(f"{GROUPS_ENDPOINT}/assign-orphaned-to-default", headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Result: {result['message']}")
        else:
            print(f"Error: {response.text}")


if __name__ == "__main__":
    print("Testing Metadata Groups CRUD API Endpoints")
    print("==========================================")
    asyncio.run(test_metadata_groups_crud())