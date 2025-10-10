#!/usr/bin/env python3
"""
GoHighLevel API Client
Handles contact management and communication logging
"""

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
    
    def is_contact_active(self, contact: Dict) -> bool:
        """
        Check if a contact is active (not deleted or archived)
        
        Args:
            contact: Contact dictionary from GHL API
            
        Returns:
            True if contact is active, False if deleted/archived
        """
        contact_id = contact.get('id', 'unknown')
        status = contact.get('status', '').lower()
        deleted_at = contact.get('deletedAt')
        archived_at = contact.get('archivedAt')
        dnd = contact.get('dnd', False)
        
        print(f"🔍 Checking contact {contact_id} - Status: '{status}', DeletedAt: {deleted_at}, ArchivedAt: {archived_at}, DND: {dnd}")
        
        if status in ['deleted', 'archived', 'inactive']:
            print(f"❌ Contact {contact_id} has inactive status: {status}")
            return False
        
        if deleted_at:
            print(f"❌ Contact {contact_id} has deletedAt: {deleted_at}")
            return False
            
        if archived_at:
            print(f"❌ Contact {contact_id} has archivedAt: {archived_at}")
            return False
        
        print(f"✅ Contact {contact_id} is active")
        return True
    
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
            email = contact_data.get('email', '')
            phone = contact_data.get('phone', '')
            first_name = contact_data.get('first_name', '')
            
            if email and '@placeholder.com' not in email:
                existing_contact = self.search_contact_by_email(email)
                if existing_contact:
                    if self.is_contact_active(existing_contact):
                        print(f"⚠️ Active contact with email {email} already exists, updating instead of creating new")
                        return self.update_contact(existing_contact.get('id'), contact_data)
                    else:
                        print(f"⚠️ Deleted contact with email {email} exists, generating unique email to avoid restoration")
                        import time
                        unique_email = f"{email.split('@')[0]}_{int(time.time())}@{email.split('@')[1]}"
                        contact_data['email'] = unique_email
                        print(f"🔍 Using unique email: {unique_email}")
            
            if phone:
                existing_contact = self.search_contact_by_phone(phone)
                if existing_contact:
                    if self.is_contact_active(existing_contact):
                        print(f"⚠️ Active contact with phone {phone} already exists, updating instead of creating new")
                        return self.update_contact(existing_contact.get('id'), contact_data)
                    else:
                        print(f"⚠️ Deleted contact with phone {phone} exists, generating unique email to avoid restoration")
                        import time
                        if email and '@placeholder.com' not in email:
                            unique_email = f"{email.split('@')[0]}_{int(time.time())}@{email.split('@')[1]}"
                        else:
                            unique_email = f"phone_{phone.replace('+', '').replace('-', '').replace(' ', '')}_{int(time.time())}@placeholder.com"
                        contact_data['email'] = unique_email
                        print(f"🔍 Using unique email for deleted phone contact: {unique_email}")
            
            if first_name:
                existing_contact = self.search_contact_by_name(first_name)
                if existing_contact:
                    if self.is_contact_active(existing_contact):
                        print(f"⚠️ Active contact with name {first_name} already exists, updating instead of creating new")
                        return self.update_contact(existing_contact.get('id'), contact_data)
                    else:
                        print(f"⚠️ Deleted contact with name {first_name} exists, generating unique email to avoid restoration")
                        import time
                        if email and '@placeholder.com' not in email:
                            unique_email = f"{email.split('@')[0]}_{int(time.time())}@{email.split('@')[1]}"
                        else:
                            unique_email = f"name_{first_name.replace(' ', '_').lower()}_{int(time.time())}@placeholder.com"
                        contact_data['email'] = unique_email
                        print(f"🔍 Using unique email for deleted name contact: {unique_email}")
            
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
    
    def update_contact(self, contact_id: str, contact_data: Dict) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/contacts/{contact_id}"
            
            payload = {
                "firstName": contact_data.get('first_name', ''),
                "lastName": contact_data.get('last_name', ''),
                "email": contact_data.get('email', ''),
                "phone": contact_data.get('phone', ''),
                "source": "Zoom Integration"
            }
            
            response = requests.put(url, headers=self.get_headers(), json=payload)
            
            if response.status_code in [200, 201]:
                contact = response.json().get('contact', {})
                print(f"✅ Contact updated: {contact.get('id')}")
                return contact
            else:
                print(f"❌ Failed to update contact: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error updating contact: {e}")
            return None
    
    def search_contact_by_email(self, email: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/contacts/search"
            params = {'email': email}
            
            print(f"🔍 GHL API search request - URL: {url}, params: {params}")
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            print(f"🔍 GHL API search response - Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                contacts = data.get('contacts', [])
                print(f"🔍 GHL API search found {len(contacts)} contacts")
                
                for contact in contacts:
                    if self.is_contact_active(contact):
                        print(f"🔍 Found active contact: {contact}")
                        return contact
                    else:
                        print(f"⚠️ Found deleted/inactive contact, skipping: {contact.get('id')}")
            else:
                print(f"🔍 GHL API search failed: {response.text}")
            
            return self.search_contact_general(email)
        except Exception as e:
            print(f"❌ Error searching contact: {e}")
            return self.search_contact_general(email)
    
    def search_contact_general(self, query: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/contacts"
            params = {'query': query, 'limit': 20}
            
            print(f"🔍 GHL API general search request - URL: {url}, params: {params}")
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            print(f"🔍 GHL API general search response - Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                contacts = data.get('contacts', [])
                print(f"🔍 GHL API general search found {len(contacts)} contacts")
                
                query_lower = query.lower().strip()
                
                for contact in contacts:
                    if not self.is_contact_active(contact):
                        print(f"⚠️ Skipping deleted/inactive contact: {contact.get('id')} - Status: {contact.get('status', 'unknown')}")
                        continue
                    
                    contact_email = (contact.get('email') or '').lower().strip()
                    contact_name = ((contact.get('firstName') or '') + ' ' + (contact.get('lastName') or '')).lower().strip()
                    contact_phone = (contact.get('phone') or '').replace('+', '').replace('-', '').replace(' ', '').strip()
                    query_clean = query_lower.replace('+', '').replace('-', '').replace(' ', '').strip()
                    
                    print(f"🔍 Matching contact: {contact.get('firstName')} {contact.get('lastName')} | Email: {contact_email} | Phone: {contact_phone}")
                    print(f"🔍 Query: '{query_lower}' | Clean query: '{query_clean}'")
                    print(f"🔍 Match checks - Email: {query_lower in contact_email}, Name: {query_lower in contact_name}, Phone: {query_clean in contact_phone}")
                    
                    if (query_lower in contact_email or 
                        query_lower in contact_name or 
                        query_clean in contact_phone):
                        print(f"🔍 Found matching active contact: {contact}")
                        return contact
            else:
                print(f"🔍 GHL API general search failed: {response.text}")
            return None
        except Exception as e:
            print(f"❌ Error in general contact search: {e}")
            return None
    
    def search_contact_by_phone(self, phone: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/contacts/search"
            params = {'phone': phone}
            
            print(f"🔍 GHL API phone search request - URL: {url}, params: {params}")
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            print(f"🔍 GHL API phone search response - Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                contacts = data.get('contacts', [])
                print(f"🔍 GHL API phone search found {len(contacts)} contacts")
                
                for contact in contacts:
                    if self.is_contact_active(contact):
                        print(f"🔍 Found active contact: {contact}")
                        return contact
                    else:
                        print(f"⚠️ Found deleted/inactive contact, skipping: {contact.get('id')}")
            else:
                print(f"🔍 GHL API phone search failed: {response.text}")
            
            return self.search_contact_general(phone)
        except Exception as e:
            print(f"❌ Error searching contact by phone: {e}")
            return self.search_contact_general(phone)
    
    def search_contact_by_name(self, name: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/contacts/search"
            params = {'name': name}
            
            print(f"🔍 GHL API name search request - URL: {url}, params: {params}")
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            print(f"🔍 GHL API name search response - Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                contacts = data.get('contacts', [])
                print(f"🔍 GHL API name search found {len(contacts)} contacts")
                
                for contact in contacts:
                    if self.is_contact_active(contact):
                        print(f"🔍 Found active contact: {contact}")
                        return contact
                    else:
                        print(f"⚠️ Found deleted/inactive contact, skipping: {contact.get('id')}")
            else:
                print(f"🔍 GHL API name search failed: {response.text}")
            
            return self.search_contact_general(name)
        except Exception as e:
            print(f"❌ Error searching contact by name: {e}")
            return self.search_contact_general(name)
    
    def search_contact_by_custom_field(self, field_key: str, field_value: str) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/contacts"
            params = {'query': f"{field_key}:{field_value}"}
            
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            if response.status_code == 200:
                data = response.json()
                contacts = data.get('contacts', [])
                if contacts:
                    return contacts[0]
            return None
        except Exception as e:
            print(f"❌ Error searching contact by custom field: {e}")
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
