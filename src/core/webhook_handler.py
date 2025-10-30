#!/usr/bin/env python3
"""
Webhook handler for Zoom events
Processes incoming webhooks and manages contact creation/updates
"""

import requests
import json
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Optional, List

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apis.zoom_api import ZoomAPI
from apis.ghl_api import GHLAPI
from utils.credentials import load_zoom_credentials, load_ghl_credentials, load_app_config

class ZoomGHLBot:
    def __init__(self):
        self.zoom_api = None
        self.ghl_api = None
        self.processed_events = set()
        self.processed_notes = set()
        self.setup_apis()
        
    def setup_apis(self):
        try:
            zoom_creds = load_zoom_credentials()
            ghl_creds = load_ghl_credentials()
            
            self.zoom_api = ZoomAPI(
                account_id=zoom_creds['account-id'],
                client_id=zoom_creds['client-id'],
                client_secret=zoom_creds['client-secret']
            )
            
            self.ghl_api = GHLAPI(
                api_key=ghl_creds['ghl-api-key'],
                location_id=ghl_creds.get('ghl-location-id')
            )
            
            print("✅ Zoom-GHL Bot initialized successfully")
            
        except Exception as e:
            print(f"❌ Error setting up APIs: {e}")
            raise e
    
    def generate_event_id(self, event_data: Dict) -> str:
        event_type = event_data.get('event', '')
        payload = event_data.get('payload', {}).get('object', {})
        event_ts = event_data.get('event_ts', '')
        
        if 'phone.call' in event_type.lower():
            caller = payload.get('caller_number', '')
            callee = payload.get('callee_number', '')
            call_id = payload.get('call_id', '')
            return f"{event_type}_{caller}_{callee}_{call_id}_{event_ts}"
        elif 'phone.recording' in event_type.lower():
            caller = payload.get('caller_number', '')
            callee = payload.get('callee_number', '')
            file_id = payload.get('id', '')
            return f"{event_type}_{caller}_{callee}_{file_id}_{event_ts}"
        elif 'sms' in event_type.lower():
            sender = payload.get('sender', {}).get('phone_number', '')
            message_id = payload.get('message_id', '')
            return f"{event_type}_{sender}_{message_id}_{event_ts}"
        elif 'meeting' in event_type.lower():
            meeting_id = payload.get('uuid', '')
            host_id = payload.get('host_id', '')
            return f"{event_type}_{meeting_id}_{host_id}_{event_ts}"
        else:
            return f"{event_type}_{event_ts}_{hash(str(payload)) % 10000}"
    
    def is_event_processed(self, event_id: str) -> bool:
        if event_id in self.processed_events:
            print(f"⚠️ Event already processed: {event_id}")
            return True
        return False
    
    def mark_event_processed(self, event_id: str):
        self.processed_events.add(event_id)
        if len(self.processed_events) > 1000:
            self.processed_events.clear()
    
    def generate_note_id(self, contact_id: str, note_content: str) -> str:
        import hashlib
        content_hash = hashlib.md5(note_content.encode()).hexdigest()[:8]
        return f"{contact_id}_{content_hash}"
    
    def is_note_processed(self, note_id: str) -> bool:
        if note_id in self.processed_notes:
            print(f"⚠️ Note already processed: {note_id}")
            return True
        return False
    
    def mark_note_processed(self, note_id: str):
        self.processed_notes.add(note_id)
        if len(self.processed_notes) > 1000:
            self.processed_notes.clear()

    def verify_webhook(self, payload: str, signature: str) -> bool:
        zoom_creds = load_zoom_credentials()
        verification_token = zoom_creds.get('verification-token', '')
        
        print(f"🔍 Verifying signature: {signature}")
        print(f"🔍 Using verification token: {verification_token[:10]}...")
        
        if signature.startswith('v0='):
            signature = signature[3:]  
        elif signature.startswith('sha256='):
            signature = signature[7:] 
        
        expected_signature = hmac.new(
            verification_token.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        print(f"🔍 Expected signature: {expected_signature}")
        print(f"🔍 Received signature: {signature}")
        
        is_valid = hmac.compare_digest(signature, expected_signature)
        print(f"🔍 Signature valid: {is_valid}")
        
        return is_valid
    
    def handle_contact(self, user_data: Dict) -> Optional[str]:
        email = user_data.get('email', '')
        user_id = user_data.get('user_id', '')
        phone = user_data.get('phone', '')
        first_name = user_data.get('first_name', '')
        user_name = user_data.get('user_name', '')
        name_field = user_data.get('name', '')
        
        name = first_name or user_name or name_field
        
        def is_phone_number(text):
            if not text:
                return False
            clean_text = text.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
            return clean_text.isdigit() and len(clean_text) >= 10
        
        if is_phone_number(name):
            print(f"🔍 Detected phone number as name: '{name}', using generic name instead")
            name = "Meeting Participant"
        
        print(f"🔍 handle_contact - email: '{email}', user_id: '{user_id}', phone: '{phone}'")
        print(f"🔍 handle_contact - first_name: '{first_name}', user_name: '{user_name}', name_field: '{name_field}', final_name: '{name}'")
        print(f"🔍 handle_contact - full user_data: {user_data}")
        
        if not email and not user_id and not phone and not name:
            print(f"⚠️ No identifying information provided, skipping contact creation")
            return None
        
        existing_contact = None
        
        if email:
            print(f"🔍 Searching for existing contact with email: {email}")
            existing_contact = self.ghl_api.search_contact_by_email(email)
            if existing_contact:
                contact_id = existing_contact.get('id')
                print(f"✅ Contact already exists: {email} (ID: {contact_id})")
                return contact_id
        
        if phone and not existing_contact:
            print(f"🔍 Searching for existing contact with phone: {phone}")
            existing_contact = self.ghl_api.search_contact_by_phone(phone)
            if existing_contact:
                contact_id = existing_contact.get('id')
                print(f"✅ Contact already exists: {phone} (ID: {contact_id})")
                return contact_id
        
        if name and not existing_contact:
            print(f"🔍 Searching for existing contact with name: {name}")
            existing_contact = self.ghl_api.search_contact_by_name(name)
            if existing_contact:
                contact_id = existing_contact.get('id')
                print(f"✅ Contact already exists by name: {name} (ID: {contact_id})")
                return contact_id
        
        if not existing_contact and (email or phone or name):
            print(f"🔍 FINAL CHECK: Searching for any existing contact with: {email or phone or name}")
            existing_contact = self.ghl_api.search_contact_general(email or phone or name)
            if existing_contact:
                contact_id = existing_contact.get('id')
                print(f"✅ FINAL CHECK: Found existing contact: {email or phone or name} (ID: {contact_id})")
                return contact_id
        
        if existing_contact:
            contact_id = existing_contact.get('id')
            print(f"✅ Using existing contact: {contact_id}")
            return contact_id
        
        participant_uuid = user_data.get('participant_uuid', '')
        contact_data = {
            'first_name': name,
            'last_name': user_data.get('last_name', ''),
            'email': email if email else (
                f"phone_{phone.replace('+', '').replace('-', '').replace(' ', '')}@placeholder.com" if phone else (
                    f"zoom_participant_{participant_uuid}@placeholder.com" if participant_uuid else (
                        f"zoom_user_{user_id}@placeholder.com" if user_id else "zoom_unknown@placeholder.com"
                    )
                )
            ),
            'phone': phone
        }
        
        if not email and user_id:
            contact_data['customFields'] = [
                {
                    'key': 'zoom_user_id',
                    'value': user_id
                }
            ]
        
        if phone and not email and not user_id:
            contact_data['customFields'] = [
                {
                    'key': 'phone_source',
                    'value': 'zoom_phone'
                }
            ]
        
        new_contact = self.ghl_api.create_contact(contact_data)
        if new_contact:
            contact_id = new_contact.get('id')
            if email:
                identifier = email
            elif phone:
                identifier = f"{name} ({phone})" if name else phone
            else:
                identifier = f"{name} (ID: {user_id})"
            print(f"✅ New contact created: {identifier}")
            return contact_id
        
        return None
    
    def handle_phone_contact(self, user_data: Dict) -> Optional[str]:
        """
        Handle contact creation specifically for phone calls - phone number only logic
        """
        phone = user_data.get('phone', '')
        
        print(f"🔍 handle_phone_contact - phone: '{phone}'")
        print(f"🔍 handle_phone_contact - full user_data: {user_data}")
        
        if not phone:
            print(f"⚠️ No phone number provided for phone contact, skipping contact creation")
            return None
        
        # Search for existing contact by phone number only
        print(f"🔍 Searching for existing contact with phone: {phone}")
        existing_contact = self.ghl_api.search_contact_by_phone(phone)
        if existing_contact:
            contact_id = existing_contact.get('id')
            print(f"✅ Phone contact already exists: {phone} (ID: {contact_id})")
            return contact_id
        
        # If no contact found by phone, do a general search to catch any contact with this phone
        print(f"🔍 FINAL CHECK: Searching for any existing contact with phone: {phone}")
        existing_contact = self.ghl_api.search_contact_general(phone)
        if existing_contact:
            contact_id = existing_contact.get('id')
            print(f"✅ FINAL CHECK: Found existing contact with phone: {phone} (ID: {contact_id})")
            return contact_id
        
        # Create new contact with phone number as the name
        contact_data = {
            'first_name': phone,  # Use phone number as the name
            'last_name': '',
            'email': f"phone_{phone.replace('+', '').replace('-', '').replace(' ', '')}@placeholder.com",
            'phone': phone
        }
        
        contact_data['customFields'] = [
            {
                'key': 'phone_source',
                'value': 'zoom_phone'
            }
        ]
        
        new_contact = self.ghl_api.create_contact(contact_data)
        if new_contact:
            contact_id = new_contact.get('id')
            print(f"✅ New phone contact created: {phone} (ID: {contact_id})")
            return contact_id
        
        return None
    
    def log_activity(self, contact_id: str, activity_type: str, data: Dict) -> bool:
        try:
            meeting_id = data.get('uuid', 'N/A')
            topic = data.get('topic', 'N/A')
            start_time = data.get('start_time', 'N/A')
            
            meeting_url = f"https://zoom.us/j/{meeting_id}" if meeting_id != 'N/A' else 'N/A'
            
            note_content = f"""
Zoom {activity_type.title()} Activity:
- Topic: {topic}
- Start Time: {start_time}
- Meeting ID: {meeting_id}
- Meeting URL: {meeting_url}
- Source: Zoom Integration
- Logged: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            note_id = self.generate_note_id(contact_id, note_content)
            if self.is_note_processed(note_id):
                print(f"⚠️ Skipping duplicate note for contact {contact_id}")
                return True
            
            url = f"{self.ghl_api.base_url}/contacts/{contact_id}/notes"
            payload = {"body": note_content}
            
            response = requests.post(url, headers=self.ghl_api.get_headers(), json=payload)
            
            if response.status_code in [200, 201]:
                self.mark_note_processed(note_id)
                print(f"✅ Activity logged for contact {contact_id}")
                return True
            else:
                print(f"❌ Failed to log activity: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error logging activity: {e}")
            return False
    
    def log_recording_activity(self, contact_id: str, recording_data: Dict, participant_info: str = "") -> bool:
        try:
            meeting_id = recording_data.get('uuid', 'N/A')
            topic = recording_data.get('topic', 'N/A')
            recording_files = recording_data.get('recording_files', [])
            share_url = recording_data.get('share_url', 'N/A')
            
            meeting_url = f"https://zoom.us/j/{meeting_id}" if meeting_id != 'N/A' else 'N/A'
            
            recording_links = []
            for file in recording_files:
                file_type = file.get('file_type', 'unknown')
                play_url = file.get('play_url', '')
                file_size = file.get('file_size', 0)
                
                if play_url:
                    recording_links.append(f"- {file_type.upper()}: {play_url} ({file_size} bytes)")
            
            recording_links_text = '\n'.join(recording_links) if recording_links else '- No recording files available'
            
            participant_note = f"- Participant: {participant_info}\n" if participant_info else ""
            
            note_content = f"""
Zoom Meeting Recording Completed:
- Topic: {topic}
- Meeting ID: {meeting_id}
- Meeting URL: {meeting_url}
- Public Share URL: {share_url}
{participant_note}- Recording Files:
{recording_links_text}
- Source: Zoom Integration
- Logged: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            note_id = self.generate_note_id(contact_id, note_content)
            if self.is_note_processed(note_id):
                print(f"⚠️ Skipping duplicate recording note for contact {contact_id}")
                return True
            
            url = f"{self.ghl_api.base_url}/contacts/{contact_id}/notes"
            payload = {"body": note_content}
            
            response = requests.post(url, headers=self.ghl_api.get_headers(), json=payload)
            
            if response.status_code in [200, 201]:
                self.mark_note_processed(note_id)
                print(f"✅ Recording activity logged for contact {contact_id}")
                return True
            else:
                print(f"❌ Failed to log recording activity: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error logging recording activity: {e}")
            return False
    
    def process_webhook(self, event_data: Dict) -> bool:
        try:
            event_type = event_data.get('event', '')
            
            print(f"🔍 Received event type: {event_type}")
            
            event_id = self.generate_event_id(event_data)
            print(f"🔍 Generated event ID: {event_id}")
            
            if self.is_event_processed(event_id):
                print(f"⚠️ Skipping duplicate event: {event_id}")
                return True
            
            success = False
            if 'sms' in event_type.lower() or 'message' in event_type.lower():
                success = self.process_sms_event(event_data)
            elif 'phone.call.caller' in event_type.lower() or 'phone.call.callee' in event_type.lower():
                success = self.process_phone_call_event(event_data)
            elif 'phone.recording' in event_type.lower() or 'call.recording' in event_type.lower():
                success = self.process_phone_recording_event(event_data)
            elif 'recording' in event_type.lower():
                success = self.process_recording_event(event_data)
            else:
                success = self.process_meeting_event(event_data)
            
            if success:
                self.mark_event_processed(event_id)
                print(f"✅ Event processed successfully: {event_id}")
            
            return success
            
        except Exception as e:
            print(f"❌ Error processing webhook: {e}")
            return False
    
    def get_meeting_participants(self, meeting_id: str) -> List[Dict]:
        """
        Get all participants from a past meeting using Zoom API
        
        Args:
            meeting_id: Zoom meeting UUID
            
        Returns:
            List of participant dictionaries
        """
        try:
            print(f"🔍 Starting participant fetch for meeting: {meeting_id}")
            
            if not self.zoom_api:
                print(f"❌ Zoom API not initialized")
                return []
                
            import urllib.parse
            token = self.zoom_api.get_access_token()
            encoded = urllib.parse.quote(meeting_id, safe='')
            double_encoded = urllib.parse.quote(encoded, safe='')
            url = f"{self.zoom_api.base_url}/past_meetings/{double_encoded}/participants"
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            print(f"🔍 Making API request to: {url}")
            print(f"🔍 Using token: {token[:20]}...")
            
            response = requests.get(url, headers=headers)
            
            print(f"🔍 API Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                participants = data.get('participants', [])
                print(f"✅ Found {len(participants)} participants")
                if participants:
                    print(f"🔍 First participant: {participants[0]}")
                return participants
            else:
                print(f"❌ Failed to get participants: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"❌ Error getting meeting participants: {e}")
            import traceback
            print(f"❌ Full error traceback: {traceback.format_exc()}")
            return []
    

    def download_recording_with_auth(self, download_url: str, filename: str = None) -> bool:
        try:
            if not self.zoom_api or not self.zoom_api.access_token:
                print(f"🔍 Getting access token for download...")
                self.zoom_api.get_access_token()
            
            if not self.zoom_api.access_token:
                print(f"❌ Failed to get access token for download")
                return False
            
            headers = {
                'Authorization': f'Bearer {self.zoom_api.access_token}',
                'Accept': 'application/octet-stream'
            }
            
            print(f"🔍 Downloading recording with authenticated headers...")
            response = requests.get(download_url, headers=headers, stream=True)
            
            if response.status_code == 200:
                if filename:
                    with open(filename, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"✅ Recording downloaded successfully: {filename}")
                else:
                    print(f"✅ Recording accessible with authentication")
                return True
            else:
                print(f"❌ Download failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error downloading recording: {e}")
            return False

    def process_recording_event(self, event_data: Dict) -> bool:
        try:
            event_type = event_data.get('event', '')
            recording_data = event_data.get('payload', {}).get('object', {})
            
            print(f"🎥 Processing {event_type} event")
            
            meeting_id = recording_data.get('uuid', '')
            host_id = recording_data.get('host_id', '')
            host_email = recording_data.get('host_email', '')
            
            print(f"🔍 Meeting ID: {meeting_id}, Host ID: {host_id}, Host Email: {host_email}")
            
            processed_contacts = set()
            
            print(f"🔍 Attempting to fetch participants...")
            participants = self.get_meeting_participants(meeting_id)
            print(f"🔍 Participants result: {len(participants) if participants else 0} participants found")
            
            if not participants:
                print(f"⚠️ No participants found, falling back to host only")
                user_data = {
                    'email': host_email,
                    'first_name': 'Host',  
                    'last_name': '',
                    'user_name': '',
                    'phone': '',
                    'user_id': host_id,
                    'participant_user_id': ''
                }
                
                contact_id = self.handle_contact(user_data)
                if contact_id and contact_id not in processed_contacts:
                    processed_contacts.add(contact_id)
                    self.log_recording_activity(contact_id, recording_data, "Host")
                    print(f"✅ Recording logged for host contact {contact_id}")
                else:
                    print(f"❌ No contact found for host {host_email} or already processed")
            else:
                print(f"👥 Found {len(participants)} participants, logging recording for all")
                
                for participant in participants:
                    email = participant.get('email', '') or participant.get('email_address', '')
                    user_id = participant.get('user_id', '')
                    participant_name = participant.get('name', '')
                    
                    first_name = participant.get('first_name', '')
                    last_name = participant.get('last_name', '')
                    
                    if not first_name and participant_name:
                        name_parts = participant_name.split()
                        first_name = name_parts[0] if name_parts else ''
                        last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    
                    def is_phone_number(text):
                        if not text:
                            return False
                        clean_text = text.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
                        return clean_text.isdigit() and len(clean_text) >= 10
                    
                    if is_phone_number(first_name):
                        print(f"🔍 Detected phone number as first_name: '{first_name}', using generic name instead")
                        first_name = "Meeting Participant"
                    
                    print(f"🔍 Recording participant - name: '{participant_name}', first_name: '{first_name}', last_name: '{last_name}', user_id: '{user_id}'")
                    
                    user_data = {
                        'email': email,
                        'first_name': first_name,
                        'last_name': last_name,
                        'user_name': participant.get('user_name', ''),
                        'phone': participant.get('phone', ''),
                        'user_id': user_id,
                        'participant_user_id': participant.get('participant_user_id', '')
                    }
                    
                    contact_id = self.handle_contact(user_data)
                    if contact_id and contact_id not in processed_contacts:
                        processed_contacts.add(contact_id)
                        identifier = email if email else f"{first_name} {last_name}".strip() or f"User {user_id}"
                        self.log_recording_activity(contact_id, recording_data, identifier)
                        print(f"✅ Recording logged for participant: {identifier} (Contact: {contact_id})")
                    else:
                        identifier = email if email else f"{first_name} {last_name}".strip() or f"User {user_id}"
                        if contact_id in processed_contacts:
                            print(f"⚠️ Contact {contact_id} already processed for participant: {identifier}")
                        else:
                            print(f"❌ No contact found for participant: {identifier}")
            
            print(f"📊 Total contacts processed for recording: {len(processed_contacts)}")
            return True
            
        except Exception as e:
            print(f"❌ Error processing recording event: {e}")
            return False
    
    def process_meeting_event(self, event_data: Dict) -> bool:
        try:
            event_type = event_data.get('event', '')
            meeting_data = event_data.get('payload', {}).get('object', {})
            
            print(f"🔔 Processing {event_type} event")
            print(f"🔍 Meeting data keys: {list(meeting_data.keys())}")
            
            if 'recording_files' in meeting_data:
                print(f"🎥 Found recording files in meeting data!")
                recording_files = meeting_data.get('recording_files', [])
                print(f"🔍 Recording files: {recording_files}")
            
            participants = meeting_data.get('participant', [])
            if not participants:
                host_data = meeting_data.get('host', {})
                if host_data:
                    participants = [host_data]
            else:
                if isinstance(participants, dict):
                    participants = [participants]
            
            processed_contacts = set()
            
            for participant in participants:
                email = participant.get('email', '') or participant.get('email_address', '')
                user_id = participant.get('user_id', '')
                participant_user_id = participant.get('participant_user_id', '')
                participant_uuid = participant.get('participant_uuid', '')
                first_name = participant.get('first_name', '')
                last_name = participant.get('last_name', '')
                user_name = participant.get('user_name', '')
                phone = participant.get('phone', '')
                
                print(f"🔍 Participant data - user_id: {user_id}, participant_user_id: {participant_user_id}")
                print(f"🔍 Participant name: {first_name} {last_name} | user_name: {user_name} | phone: {phone}")
                
                if not email:
                    if participant_uuid:
                        email = f"zoom_participant_{participant_uuid}@placeholder.com"
                    elif participant_user_id:
                        email = f"zoom_participant_{participant_user_id}@placeholder.com"
                    elif user_id:
                        email = f"zoom_user_{user_id}@placeholder.com"
                    elif first_name or last_name:
                        name_part = f"{first_name}_{last_name}".replace(' ', '_').lower()
                        email = f"zoom_participant_{name_part}@placeholder.com"
                    elif user_name:
                        email = f"zoom_participant_{user_name.replace(' ', '_').lower()}@placeholder.com"
                    elif phone:
                        email = f"zoom_participant_{phone.replace('+', '').replace('-', '').replace(' ', '')}@placeholder.com"
                    else:
                        email = f"zoom_unknown_{hash(str(participant)) % 10000}@placeholder.com"
                
                print(f"🔍 Generated email for participant: {email}")
                
                user_data = {
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'user_name': user_name,
                    'phone': phone,
                    'user_id': user_id,
                    'participant_user_id': participant_user_id,
                    'participant_uuid': participant_uuid
                }
                
                contact_id = self.handle_contact(user_data)
                if contact_id and contact_id not in processed_contacts:
                    processed_contacts.add(contact_id)
                    self.log_activity(contact_id, event_type, meeting_data)
                    print(f"✅ Meeting activity logged for contact {contact_id}")
                else:
                    if contact_id in processed_contacts:
                        print(f"⚠️ Contact {contact_id} already processed for this meeting")
                    else:
                        print(f"❌ No contact found for participant")
            
            print(f"📊 Total contacts processed for meeting: {len(processed_contacts)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error processing meeting event: {e}")
            return False
    
    def process_sms_event(self, event_data: Dict) -> bool:
        try:
            event_type = event_data.get('event', '')
            sms_data = event_data.get('payload', {}).get('object', {})
            
            print(f"📱 Processing {event_type} event")
            
            contacts_to_process = []
            
            if event_type == 'phone.sms_sent':
                sender_data = sms_data.get('sender', {})
                to_members = sms_data.get('to_members', [])
                
                if sender_data:
                    user_data = {
                        'email': '', 
                        'first_name': sender_data.get('display_name', '').split()[0] if sender_data.get('display_name') else '',
                        'last_name': ' '.join(sender_data.get('display_name', '').split()[1:]) if sender_data.get('display_name') and len(sender_data.get('display_name', '').split()) > 1 else '',
                        'phone': sender_data.get('phone_number', ''),
                        'user_id': sender_data.get('id', '')
                    }
                    contacts_to_process.append({
                        'data': user_data,
                        'role': 'sender'
                    })
                
                for recipient in to_members:
                    user_data = {
                        'email': '',
                        'first_name': 'SMS',
                        'last_name': 'Recipient',
                        'phone': recipient.get('phone_number', ''),
                        'user_id': ''
                    }
                    contacts_to_process.append({
                        'data': user_data,
                        'role': 'recipient'
                    })
            
            else:
                sender_data = sms_data.get('sender', {})
                recipient_data = sms_data.get('recipient', {})
                
                if sender_data:
                    contacts_to_process.append({
                        'data': sender_data,
                        'role': 'sender'
                    })
                
                if recipient_data:
                    contacts_to_process.append({
                        'data': recipient_data,
                        'role': 'recipient'
                    })
            
            processed_contacts = set()
            
            for contact_info in contacts_to_process:
                user_data = contact_info['data']
                
                contact_id = self.handle_contact(user_data)
                if contact_id and contact_id not in processed_contacts:
                    processed_contacts.add(contact_id)
                    self.log_sms_activity(contact_id, sms_data, event_type, contact_info['role'])
                    print(f"✅ SMS activity logged for contact {contact_id} ({contact_info['role']})")
                else:
                    if contact_id in processed_contacts:
                        print(f"⚠️ Contact {contact_id} already processed for SMS event")
                    else:
                        print(f"❌ No contact found for SMS participant")
            
            print(f"📊 Total contacts processed for SMS: {len(processed_contacts)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error processing SMS event: {e}")
            return False
    
    def process_phone_call_event(self, event_data: Dict) -> bool:
        try:
            event_type = event_data.get('event', '')
            call_data = event_data.get('payload', {}).get('object', {})
            
            print(f"📞 Processing {event_type} event")
            print(f"🔍 Call data keys: {list(call_data.keys())}")
            
            caller_number = call_data.get('caller_number', '')
            callee_number = call_data.get('callee_number', '')
            call_id = call_data.get('call_id', '')
            duration = call_data.get('duration', 0)
            start_time = call_data.get('start_time', '')
            end_time = call_data.get('end_time', '')
            
            print(f"🔍 Caller: {caller_number}, Callee: {callee_number}")
            print(f"🔍 Duration: {duration} seconds, Call ID: {call_id}")
            
            contacts_to_process = []
            
            if 'caller' in event_type.lower():
                if caller_number:
                    caller_data = {
                        'email': '',
                        'first_name': 'Caller',
                        'last_name': '',
                        'phone': caller_number,
                        'user_id': ''
                    }
                    contacts_to_process.append({
                        'data': caller_data,
                        'role': 'caller',
                        'phone': caller_number
                    })
            
            if 'callee' in event_type.lower():
                if callee_number:
                    callee_data = {
                        'email': '',
                        'first_name': 'Callee',
                        'last_name': '',
                        'phone': callee_number,
                        'user_id': ''
                    }
                    contacts_to_process.append({
                        'data': callee_data,
                        'role': 'callee',
                        'phone': callee_number
                    })
            
            processed_contacts = set()
            
            for contact_info in contacts_to_process:
                user_data = contact_info['data']
                contact_id = self.handle_phone_contact(user_data)
                
                if contact_id and contact_id not in processed_contacts:
                    processed_contacts.add(contact_id)
                    self.log_phone_call_activity(contact_id, call_data, event_type, contact_info['role'])
                    print(f"✅ Phone call activity logged for contact {contact_id} ({contact_info['role']})")
                else:
                    if contact_id in processed_contacts:
                        print(f"⚠️ Contact {contact_id} already processed for phone call event")
                    else:
                        print(f"❌ No contact found for phone call participant")
            
            print(f"📊 Total contacts processed for phone call: {len(processed_contacts)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error processing phone call event: {e}")
            return False
    
    def process_phone_recording_event(self, event_data: Dict) -> bool:
        try:
            event_type = event_data.get('event', '')
            recording_data = event_data.get('payload', {}).get('object', {})
            
            print(f"🎙️ Processing {event_type} event")
            print(f"🔍 Recording data keys: {list(recording_data.keys())}")
            
            recordings = recording_data.get('recordings', [])
            if not recordings:
                if recording_data.get('id'):
                    recordings = [recording_data]
                    print(f"🔍 Using single recording object as array")
                else:
                    print(f"⚠️ No recordings found in event data")
                    return False
            
            for recording in recordings:
                caller_number = recording.get('caller_number', '')
                callee_number = recording.get('callee_number', '')
                download_url = recording.get('download_url', '')
                file_id = recording.get('id', '')
                call_id = recording.get('call_id', '')
                duration = recording.get('duration', 0)
                start_time = recording.get('date_time', '')
                caller_name = recording.get('caller_name', '')
                callee_name = recording.get('callee_name', '')
                
                print(f"🔍 Caller: {caller_number} ({caller_name}), Callee: {callee_number} ({callee_name})")
                print(f"🔍 Recording URL: {download_url}")
                print(f"🔍 File ID: {file_id}")
                
                contacts_to_process = []
                
                direction = recording.get('direction', '')
                print(f"🔍 Call direction: {direction}")
                
                if direction == 'inbound':
                    if caller_number:
                        caller_data = {
                            'email': '',
                            'first_name': caller_name if caller_name else 'Caller',
                            'last_name': '',
                            'phone': caller_number,
                            'user_id': ''
                        }
                        contacts_to_process.append({
                            'data': caller_data,
                            'role': 'caller',
                            'phone': caller_number
                        })
                    print(f"🔍 Inbound call - only processing caller: {caller_number} ({caller_name})")
                else:
                    if caller_number:
                        caller_data = {
                            'email': '',
                            'first_name': caller_name if caller_name else 'Caller',
                            'last_name': '',
                            'phone': caller_number,
                            'user_id': ''
                        }
                        contacts_to_process.append({
                            'data': caller_data,
                            'role': 'caller',
                            'phone': caller_number
                        })
                    
                    if callee_number:
                        callee_data = {
                            'email': '',
                            'first_name': callee_name if callee_name else 'Callee',
                            'last_name': '',
                            'phone': callee_number,
                            'user_id': ''
                        }
                        contacts_to_process.append({
                            'data': callee_data,
                            'role': 'callee',
                            'phone': callee_number
                        })
                    print(f"🔍 Outbound call - processing both caller and callee")
                
                processed_contacts = set()
                
                for contact_info in contacts_to_process:
                    user_data = contact_info['data']
                    print(f"🔍 Processing contact data: {user_data}")
                    contact_id = self.handle_phone_contact(user_data)
                    
                    if contact_id and contact_id not in processed_contacts:
                        processed_contacts.add(contact_id)
                        self.log_phone_recording_activity(contact_id, recording, event_type, contact_info['role'])
                        print(f"✅ Phone recording activity logged for contact {contact_id} ({contact_info['role']})")
                    else:
                        if contact_id in processed_contacts:
                            print(f"⚠️ Contact {contact_id} already processed for phone recording event")
                        else:
                            print(f"❌ Failed to create contact for {contact_info['role']}: {user_data}")
                
                print(f"📊 Total contacts processed for phone recording: {len(processed_contacts)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error processing phone recording event: {e}")
            return False
    
    def log_sms_activity(self, contact_id: str, sms_data: Dict, event_type: str, role: str) -> bool:
        try:
            message_content = sms_data.get('message', '') or sms_data.get('content', '') or 'N/A'
            
            note_content = f"""
Zoom SMS Activity - {event_type.upper()}:
- Message Content: {message_content}
- Message Type: {sms_data.get('message_type', 'N/A')}
- Direction: {role}
- Timestamp: {sms_data.get('date_time', '') or sms_data.get('timestamp', 'N/A')}
- Message ID: {sms_data.get('message_id', 'N/A')}
- Phone Number: {sms_data.get('sender', {}).get('phone_number', 'N/A') if role == 'sender' else 'N/A'}
- Event Type: {event_type}
- Source: Zoom Integration
- Logged: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            note_id = self.generate_note_id(contact_id, note_content)
            if self.is_note_processed(note_id):
                print(f"⚠️ Skipping duplicate SMS note for contact {contact_id}")
                return True
            
            url = f"{self.ghl_api.base_url}/contacts/{contact_id}/notes"
            payload = {"body": note_content}
            
            response = requests.post(url, headers=self.ghl_api.get_headers(), json=payload)
            
            if response.status_code in [200, 201]:
                self.mark_note_processed(note_id)
                print(f"✅ SMS activity logged for contact {contact_id} ({role})")
                return True
            else:
                print(f"❌ Failed to log SMS activity: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error logging SMS activity: {e}")
            return False
    
    def log_phone_call_activity(self, contact_id: str, call_data: Dict, event_type: str, role: str) -> bool:
        try:
            caller_number = call_data.get('caller_number', 'N/A')
            callee_number = call_data.get('callee_number', 'N/A')
            call_id = call_data.get('call_id', 'N/A')
            duration = call_data.get('duration', 0)
            start_time = call_data.get('start_time', 'N/A')
            end_time = call_data.get('end_time', 'N/A')
            
            duration_minutes = duration // 60 if duration else 0
            duration_seconds = duration % 60 if duration else 0
            
            note_content = f"""
Zoom Phone Call Activity - {event_type.upper()}:
- Caller Number: {caller_number}
- Callee Number: {callee_number}
- Call ID: {call_id}
- Duration: {duration_minutes}m {duration_seconds}s
- Start Time: {start_time}
- End Time: {end_time}
- Role: {role}
- Event Type: {event_type}
- Source: Zoom Phone Integration
- Logged: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            note_id = self.generate_note_id(contact_id, note_content)
            if self.is_note_processed(note_id):
                print(f"⚠️ Skipping duplicate phone call note for contact {contact_id}")
                return True
            
            url = f"{self.ghl_api.base_url}/contacts/{contact_id}/notes"
            payload = {"body": note_content}
            
            response = requests.post(url, headers=self.ghl_api.get_headers(), json=payload)
            
            if response.status_code in [200, 201]:
                self.mark_note_processed(note_id)
                print(f"✅ Phone call activity logged for contact {contact_id} ({role})")
                return True
            else:
                print(f"❌ Failed to log phone call activity: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error logging phone call activity: {e}")
            return False
    
    def log_phone_recording_activity(self, contact_id: str, recording_data: Dict, event_type: str, role: str) -> bool:
        try:
            caller_number = recording_data.get('caller_number', 'N/A')
            callee_number = recording_data.get('callee_number', 'N/A')
            download_url = recording_data.get('download_url', 'N/A')
            file_id = recording_data.get('id', 'N/A')
            call_id = recording_data.get('call_id', 'N/A')
            
            actual_file_id = file_id
            if download_url and download_url != 'N/A' and 'download/' in download_url:
                actual_file_id = download_url.split('download/')[-1]
                print(f"🔍 Extracted download file ID: {actual_file_id} from URL: {download_url}")
            duration = recording_data.get('duration', 0)
            start_time = recording_data.get('date_time', 'N/A')
            caller_name = recording_data.get('caller_name', 'N/A')
            callee_name = recording_data.get('callee_name', 'N/A')
            call_log_id = recording_data.get('call_log_id', 'N/A')
            
            print(f"🔍 Recording data validation:")
            print(f"   File ID: {file_id}")
            print(f"   Actual Download File ID: {actual_file_id}")
            print(f"   Download URL: {download_url}")
            print(f"   Event Type: {event_type}")
            
            duration_minutes = duration // 60 if duration else 0
            duration_seconds = duration % 60 if duration else 0
            
            has_valid_recording = False
            proxy_download_url = "No recording available"
            
            if actual_file_id and actual_file_id != 'N/A' and len(actual_file_id) > 5:
                has_valid_recording = True
                zoom_creds = load_zoom_credentials()
                app_config = load_app_config()
                account_id = zoom_creds.get('account-id', 'N/A')
                ec2_domain = app_config.get('ec2-domain', 'https://your-ec2-domain.com')
                import time
                import base64
                import uuid
                
                unique_uuid = str(uuid.uuid4())
                encoded_data = base64.b64encode(f"{account_id}|{actual_file_id}".encode()).decode()
                proxy_download_url = f"{ec2_domain}/download/{encoded_data}"
                print(f"✅ Valid recording found - Download File ID: {actual_file_id}")
            else:
                print(f"⚠️ No valid recording found - Download File ID: {actual_file_id}")
            
            recording_section = f"- 📥 Download Recording: {proxy_download_url}" if has_valid_recording else "- ⚠️ No recording available for this call"
            
            note_content = f"""
Zoom Phone Call Recording Completed - {event_type.upper()}:
- Caller Number: {caller_number} ({caller_name})
- Callee Number: {callee_number} ({callee_name})
- Call ID: {call_id}
- File ID: {file_id}
- Call Log ID: {call_log_id}
- Duration: {duration_minutes}m {duration_seconds}s
- Start Time: {start_time}
{recording_section}
- Role: {role}
- Event Type: {event_type}
- Source: Zoom Phone Integration
- Logged: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            note_id = self.generate_note_id(contact_id, note_content)
            if self.is_note_processed(note_id):
                print(f"⚠️ Skipping duplicate phone recording note for contact {contact_id}")
                return True
            
            url = f"{self.ghl_api.base_url}/contacts/{contact_id}/notes"
            payload = {"body": note_content}
            
            response = requests.post(url, headers=self.ghl_api.get_headers(), json=payload)
            
            if response.status_code in [200, 201]:
                self.mark_note_processed(note_id)
                print(f"✅ Phone recording activity logged for contact {contact_id} ({role})")
                print(f"🔗 Recording download link added: {proxy_download_url}")
                return True
            else:
                print(f"❌ Failed to log phone recording activity: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error logging phone recording activity: {e}")
            return False
    
