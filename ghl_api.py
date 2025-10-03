#!/usr/bin/env python3

import requests
import json
import sys
from typing import Dict, List, Optional

class GHLAPI:
    def __init__(self, api_key: str, location_id: str = None):
        self.api_key = api_key
        self.location_id = location_id
        self.base_url = "https://rest.gohighlevel.com/v1"
        
    def get_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def test_connection(self) -> bool:
        try:
            url = f"{self.base_url}/locations"
            response = requests.get(url, headers=self.get_headers())
            
            if response.status_code == 200:
                print("✅ Successfully connected to GHL API")
                return True
            else:
                print(f"❌ GHL API connection failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error testing GHL connection: {e}")
            return False
    
    def get_locations(self) -> List[Dict]:
        try:
            url = f"{self.base_url}/locations"
            response = requests.get(url, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                locations = data.get('locations', [])
                print(f"✅ Found {len(locations)} locations")
                return locations
            else:
                print(f"❌ Failed to get locations: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            print(f"❌ Error getting locations: {e}")
            return []
    
    def create_contact(self, contact_data: Dict) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/contacts"
            
            payload = {
                "firstName": contact_data.get('first_name', ''),
                "lastName": contact_data.get('last_name', ''),
                "email": contact_data.get('email', ''),
                "phone": contact_data.get('phone', ''),
                "source": "Zoom Integration"
            }
            
            response = requests.post(url, headers=self.get_headers(), json=payload)
            
            if response.status_code in [200, 201]:
                contact = response.json().get('contact', {})
                print(f"✅ Contact created: {contact.get('id')}")
                return contact
            else:
                print(f"❌ Failed to create contact: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error creating contact: {e}")
            return None
    
    def search_contact_by_email(self, email: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/contacts/search"
            params = {'email': email}
            
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            if response.status_code == 200:
                data = response.json()
                contacts = data.get('contacts', [])
                if contacts:
                    return contacts[0]
            return None
        except Exception as e:
            print(f"❌ Error searching contact: {e}")
            return None
    
    def log_communication(self, contact_id: str, communication_data: Dict) -> bool:
        try:
            url = f"{self.base_url}/activities"
            
            payload = {
                "contactId": contact_id,
                "type": communication_data.get('type', 'call'),
                "title": communication_data.get('subject', ''),
                "body": communication_data.get('body', ''),
                "direction": communication_data.get('direction', 'inbound'),
                "date": communication_data.get('date', ''),
                "source": "Zoom Integration"
            }
            
            response = requests.post(url, headers=self.get_headers(), json=payload)
            
            if response.status_code in [200, 201]:
                print(f"✅ Communication logged for contact {contact_id}")
                return True
            else:
                print(f"❌ Failed to log communication: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error logging communication: {e}")
            return False

def load_ghl_credentials(filename: str = "client_credentials.txt") -> Dict[str, str]:
    credentials = {}
    
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()
        
        required_keys = ['ghl-api-key']
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
    print("🚀 GHL API Setup Script")
    print("=" * 50)
    
    try:
        creds = load_ghl_credentials()
        
        ghl_api = GHLAPI(api_key=creds['ghl-api-key'])
        
        print("🔐 Testing GHL API connection...")
        if ghl_api.test_connection():
            print("📋 Getting locations...")
            locations = ghl_api.get_locations()
            
            for i, location in enumerate(locations, 1):
                print(f"{i}. {location.get('name', 'N/A')} (ID: {location.get('id', 'N/A')})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
