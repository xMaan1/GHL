#!/usr/bin/env python3
"""
Zoom API Client for Server-to-Server OAuth
Handles authentication and API calls to Zoom
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
        self.base_url = "https://api.zoom.us/v2"
        self.access_token = None
        
    def get_access_token(self) -> str:
        """
        Get access token using client credentials flow
        
        Returns:
            Access token string
            
        Raises:
            Exception: If authentication fails
        """
        token_url = f"https://zoom.us/oauth/token"
        
        data = {
            'grant_type': 'account_credentials',
            'account_id': self.account_id
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(
            token_url,
            data=data,
            headers=headers,
            auth=(self.client_id, self.client_secret)
        )
        
        if response.status_code == 200:
            token_data = response.json()
            # Always return a fresh token; also update in-memory copy for convenience
            self.access_token = token_data['access_token']
            print(f"✅ Successfully authenticated with Zoom API")
            return self.access_token
        else:
            error_msg = f"Authentication failed: {response.status_code} - {response.text}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)

    def _auth_headers(self, content_type: str = 'application/json') -> Dict[str, str]:
        access_token = self.get_access_token()
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        if content_type:
            headers['Content-Type'] = content_type
        return headers
    
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
        all_users = []
        next_page_token = None
        page = 1
        
        while True:
            url = f"{self.base_url}/users"
            params = {
                'page_size': page_size,
                'status': 'active'  
            }
            
            if next_page_token:
                params['next_page_token'] = next_page_token
            
            headers = self._auth_headers()
            
            print(f"📄 Fetching page {page}...")
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                all_users.extend(users)
                
                print(f"   Found {len(users)} users on page {page}")
                
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
        url = f"{self.base_url}/users/{user_id}"
        headers = self._auth_headers()
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Failed to get user details for {user_id}: {response.status_code}")
            return {}
    
    def get_phone_recordings(self, page_size: int = 30, from_date: str = None, to_date: str = None) -> List[Dict]:
        """
        Get call recordings from Zoom Phone API
        
        Args:
            page_size: Number of records per page (max 300)
            from_date: Start date in yyyy-mm-dd format
            to_date: End date in yyyy-mm-dd format
            
        Returns:
            List of recording dictionaries
        """
        url = f"{self.base_url}/phone/recordings"
        params = {
            'page_size': min(page_size, 300)
        }
        
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        
        headers = self._auth_headers()
        
        print(f"🔍 Fetching phone recordings with params: {params}")
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            recordings = data.get('recordings', [])
            print(f"✅ Found {len(recordings)} phone recordings")
            return recordings
        else:
            print(f"❌ Failed to get phone recordings: {response.status_code} - {response.text}")
            return []
    
    def download_phone_recording(self, file_id: str, download_url: str = None) -> bytes:
        """
        Download a phone recording using the file ID or direct download URL
        
        Args:
            file_id: File ID from Zoom Phone API
            download_url: Direct download URL (optional)
            
        Returns:
            Recording file bytes
        """
        if download_url:
            url = download_url
        else:
            url = f"{self.base_url}/phone/recording/download/{file_id}"
        
        headers = self._auth_headers(content_type=None)
        headers['Accept'] = 'application/octet-stream'
        
        print(f"🔍 Downloading phone recording from: {url}")
        
        response = requests.get(url, headers=headers, stream=True)
        
        if response.status_code == 200:
            recording_data = b''
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    recording_data += chunk
            print(f"✅ Successfully downloaded recording {file_id}")
            return recording_data
        else:
            print(f"❌ Failed to download recording: {response.status_code} - {response.text}")
            return b''
    
    def get_phone_recording_download_url(self, file_id: str) -> str:
        """
        Get the correct download URL for a phone recording
        
        Args:
            file_id: File ID from Zoom Phone API
            
        Returns:
            Download URL string
        """
        return f"{self.base_url}/phone/recording/download/{file_id}"
    
    def get_phone_recording_by_call_id(self, call_id: str) -> Dict:
        """
        Get phone recording by call ID
        
        Args:
            call_id: Phone call ID
            
        Returns:
            Recording details dictionary
        """
        url = f"{self.base_url}/phone/recordings/call_logs/{call_id}"
        headers = self._auth_headers()
        
        print(f"🔍 Fetching recording for call ID: {call_id}")
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found recording for call {call_id}")
            return data
        else:
            print(f"❌ Failed to get recording for call {call_id}: {response.status_code} - {response.text}")
            return {}