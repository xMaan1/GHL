#!/usr/bin/env python3
"""
Zoom API Script to get all users using Server-to-Server OAuth
Based on the PowerShell script provided
"""

import requests
import json
import sys
from typing import Dict, List, Optional

class ZoomAPI:
    def __init__(self, account_id: str, client_id: str, client_secret: str):
        """
        Initialize Zoom API client with server-to-server credentials
        
        Args:
            account_id: Zoom account ID
            client_id: Zoom app client ID
            client_secret: Zoom app client secret
        """
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.base_url = "https://api.zoom.us/v2"
        
    def get_access_token(self) -> str:
        """
        Get access token using client credentials flow
        
        Returns:
            Access token string
            
        Raises:
            Exception: If authentication fails
        """
        token_url = f"https://zoom.us/oauth/token"
        
        # Prepare the request data
        data = {
            'grant_type': 'account_credentials',
            'account_id': self.account_id
        }
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Make the request with basic auth
        response = requests.post(
            token_url,
            data=data,
            headers=headers,
            auth=(self.client_id, self.client_secret)
        )
        
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data['access_token']
            print(f"✅ Successfully authenticated with Zoom API")
            return self.access_token
        else:
            error_msg = f"Authentication failed: {response.status_code} - {response.text}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    def get_all_users(self, page_size: int = 300) -> List[Dict]:
        """
        Get all users from Zoom account
        
        Args:
            page_size: Number of users per page (max 300)
            
        Returns:
            List of user dictionaries
            
        Raises:
            Exception: If API call fails
        """
        if not self.access_token:
            self.get_access_token()
        
        all_users = []
        next_page_token = None
        page = 1
        
        while True:
            # Prepare URL with pagination
            url = f"{self.base_url}/users"
            params = {
                'page_size': page_size,
                'status': 'active'  # Get active users
            }
            
            if next_page_token:
                params['next_page_token'] = next_page_token
            
            # Prepare headers with Bearer token
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            print(f"📄 Fetching page {page}...")
            
            # Make the API request
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                all_users.extend(users)
                
                print(f"   Found {len(users)} users on page {page}")
                
                # Check if there are more pages
                next_page_token = data.get('next_page_token')
                if not next_page_token:
                    break
                    
                page += 1
            else:
                error_msg = f"Failed to get users: {response.status_code} - {response.text}"
                print(f"❌ {error_msg}")
                raise Exception(error_msg)
        
        print(f"✅ Total users retrieved: {len(all_users)}")
        return all_users
    
    def get_user_details(self, user_id: str) -> Dict:
        """
        Get detailed information for a specific user
        
        Args:
            user_id: Zoom user ID
            
        Returns:
            User details dictionary
        """
        if not self.access_token:
            self.get_access_token()
        
        url = f"{self.base_url}/users/{user_id}"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Failed to get user details for {user_id}: {response.status_code}")
            return {}

def load_credentials(filename: str = "client_credentials.txt") -> Dict[str, str]:
    """
    Load Zoom credentials from file
    
    Args:
        filename: Path to credentials file
        
    Returns:
        Dictionary with credentials
    """
    credentials = {}
    
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()
        
        required_keys = ['account-id', 'client-id', 'client-secret']
        for key in required_keys:
            if key not in credentials:
                raise ValueError(f"Missing required credential: {key}")
        
        return credentials
        
    except FileNotFoundError:
        print(f"❌ Credentials file '{filename}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading credentials: {e}")
        sys.exit(1)

def main():
    """Main function to demonstrate the Zoom API usage"""
    print("🚀 Zoom Users API Script")
    print("=" * 50)
    
    try:
        # Load credentials
        print("📋 Loading credentials...")
        creds = load_credentials()
        
        # Initialize Zoom API client
        zoom_api = ZoomAPI(
            account_id=creds['account-id'],
            client_id=creds['client-id'],
            client_secret=creds['client-secret']
        )
        
        # Get access token
        print("🔐 Authenticating with Zoom API...")
        zoom_api.get_access_token()
        
        # Get all users
        print("👥 Fetching all users...")
        users = zoom_api.get_all_users()
        
        # Display results
        print("\n📊 User Summary:")
        print("-" * 30)
        
        for i, user in enumerate(users, 1):
            print(f"{i:3d}. {user.get('first_name', '')} {user.get('last_name', '')} ({user.get('email', '')})")
            print(f"     ID: {user.get('id', 'N/A')}")
            print(f"     Status: {user.get('status', 'N/A')}")
            print(f"     Type: {user.get('type', 'N/A')}")
            print()
        
        # Save to JSON file
        output_file = "zoom_users.json"
        with open(output_file, 'w') as f:
            json.dump(users, f, indent=2)
        
        print(f"💾 User data saved to '{output_file}'")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
