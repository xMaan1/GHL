#!/usr/bin/env python3

from fastapi import FastAPI, Request, HTTPException
import requests
import json
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Optional
from zoom_users_api import ZoomAPI, load_credentials
from ghl_api import GHLAPI, load_ghl_credentials

app = FastAPI(title="Zoom-GHL Integration", version="1.0.0")

class ZoomGHLBot:
    def __init__(self):
        self.zoom_api = None
        self.ghl_api = None
        self.setup_apis()
        
    def setup_apis(self):
        try:
            zoom_creds = load_credentials()
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
    
    def verify_webhook(self, payload: str, signature: str) -> bool:
        zoom_creds = load_credentials()
        secret_token = zoom_creds.get('secret-token', '')
        
        expected_signature = hmac.new(
            secret_token.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def handle_contact(self, user_data: Dict) -> Optional[str]:
        email = user_data.get('email', '')
        if not email:
            return None
            
        existing_contact = self.ghl_api.search_contact_by_email(email)
        
        if existing_contact:
            contact_id = existing_contact.get('id')
            print(f"✅ Contact already exists: {email}")
            return contact_id
        
        contact_data = {
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
            'email': email,
            'phone': user_data.get('phone', '')
        }
        
        new_contact = self.ghl_api.create_contact(contact_data)
        if new_contact:
            contact_id = new_contact.get('id')
            print(f"✅ New contact created: {email}")
            return contact_id
        
        return None
    
    def log_activity(self, contact_id: str, activity_type: str, data: Dict) -> bool:
        try:
            note_content = f"""
Zoom {activity_type.title()} Activity:
- Topic: {data.get('topic', 'N/A')}
- Duration: {data.get('duration', 'N/A')} minutes
- Start Time: {data.get('start_time', 'N/A')}
- Meeting ID: {data.get('uuid', 'N/A')}
- Participants: {data.get('participant_count', 'N/A')}
- Source: Zoom Integration
- Logged: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            url = f"{self.ghl_api.base_url}/contacts/{contact_id}/notes"
            payload = {"body": note_content}
            
            response = requests.post(url, headers=self.ghl_api.get_headers(), json=payload)
            
            if response.status_code in [200, 201]:
                print(f"✅ Activity logged for contact {contact_id}")
                return True
            else:
                print(f"❌ Failed to log activity: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error logging activity: {e}")
            return False
    
    def process_webhook(self, event_data: Dict) -> bool:
        try:
            event_type = event_data.get('event', '')
            
            if 'sms' in event_type.lower() or 'message' in event_type.lower():
                return self.process_sms_event(event_data)
            else:
                return self.process_meeting_event(event_data)
            
        except Exception as e:
            print(f"❌ Error processing webhook: {e}")
            return False
    
    def process_meeting_event(self, event_data: Dict) -> bool:
        try:
            event_type = event_data.get('event', '')
            meeting_data = event_data.get('payload', {}).get('object', {})
            
            print(f"🔔 Processing {event_type} event")
            
            participants = meeting_data.get('participant', [])
            if not participants:
                host_data = meeting_data.get('host', {})
                if host_data:
                    participants = [host_data]
            
            for participant in participants:
                user_data = {
                    'email': participant.get('email', ''),
                    'first_name': participant.get('first_name', ''),
                    'last_name': participant.get('last_name', ''),
                    'phone': participant.get('phone', '')
                }
                
                contact_id = self.handle_contact(user_data)
                if contact_id:
                    self.log_activity(contact_id, event_type, meeting_data)
            
            return True
            
        except Exception as e:
            print(f"❌ Error processing meeting event: {e}")
            return False
    
    def process_sms_event(self, event_data: Dict) -> bool:
        try:
            event_type = event_data.get('event', '')
            sms_data = event_data.get('payload', {}).get('object', {})
            
            print(f"📱 Processing {event_type} event")
            
            sender_data = sms_data.get('sender', {})
            recipient_data = sms_data.get('recipient', {})
            
            contacts_to_process = []
            
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
            
            for contact_info in contacts_to_process:
                user_data = {
                    'email': contact_info['data'].get('email', ''),
                    'first_name': contact_info['data'].get('first_name', ''),
                    'last_name': contact_info['data'].get('last_name', ''),
                    'phone': contact_info['data'].get('phone', '')
                }
                
                contact_id = self.handle_contact(user_data)
                if contact_id:
                    self.log_sms_activity(contact_id, sms_data, event_type, contact_info['role'])
            
            return True
            
        except Exception as e:
            print(f"❌ Error processing SMS event: {e}")
            return False
    
    def log_sms_activity(self, contact_id: str, sms_data: Dict, event_type: str, role: str) -> bool:
        try:
            note_content = f"""
Zoom SMS Activity - {event_type.upper()}:
- Message Content: {sms_data.get('content', 'N/A')}
- Message Type: {sms_data.get('message_type', 'N/A')}
- Direction: {role}
- Timestamp: {sms_data.get('timestamp', 'N/A')}
- Message ID: {sms_data.get('message_id', 'N/A')}
- Event Type: {event_type}
- Source: Zoom Integration
- Logged: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            url = f"{self.ghl_api.base_url}/contacts/{contact_id}/notes"
            payload = {"body": note_content}
            
            response = requests.post(url, headers=self.ghl_api.get_headers(), json=payload)
            
            if response.status_code in [200, 201]:
                print(f"✅ SMS activity logged for contact {contact_id} ({role})")
                return True
            else:
                print(f"❌ Failed to log SMS activity: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error logging SMS activity: {e}")
            return False

bot = ZoomGHLBot()

@app.post("/zoom-webhook")
async def zoom_webhook(request: Request):
    try:
        payload = await request.body()
        signature = request.headers.get('X-Zm-Signature', '')
        
        if not bot.verify_webhook(payload.decode(), signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        event_data = await request.json()
        success = bot.process_webhook(event_data)
        
        if success:
            return {"status": "success", "message": "Event processed"}
        else:
            raise HTTPException(status_code=500, detail="Failed to process event")
            
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/test-sms")
async def test_sms():
    try:
        test_sms_data = {
            'event': 'sms.message.sent',
            'payload': {
                'object': {
                    'content': 'Test SMS message from Zoom integration',
                    'message_type': 'sms',
                    'timestamp': datetime.now().isoformat(),
                    'message_id': 'test-sms-123',
                    'sender': {
                        'email': 'test@example.com',
                        'first_name': 'Test',
                        'last_name': 'Sender',
                        'phone': '+1234567890'
                    },
                    'recipient': {
                        'email': 'recipient@example.com',
                        'first_name': 'Test',
                        'last_name': 'Recipient',
                        'phone': '+0987654321'
                    }
                }
            }
        }
        
        success = bot.process_sms_event(test_sms_data)
        
        if success:
            return {"status": "success", "message": "SMS test completed"}
        else:
            raise HTTPException(status_code=500, detail="SMS test failed")
            
    except Exception as e:
        print(f"❌ SMS test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Zoom-GHL Integration Server")
    print("=" * 50)
    print("📡 Webhook: http://localhost:8000/zoom-webhook")
    print("❤️ Health: http://localhost:8000/health")
    print("🔄 Sync: POST http://localhost:8000/sync-users")
    print("📱 SMS Test: POST http://localhost:8000/test-sms")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
