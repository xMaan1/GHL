#!/usr/bin/env python3
"""
Main FastAPI application for Zoom-GHL Integration
"""

from fastapi import FastAPI, Request, HTTPException
import requests
import json
import hmac
import hashlib
import base64
from datetime import datetime
from typing import Dict

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.webhook_handler import ZoomGHLBot
from utils.credentials import load_zoom_credentials

app = FastAPI(title="Zoom-GHL Integration", version="1.0.0")

# Initialize the bot
bot = ZoomGHLBot()

@app.post("/zoom-webhook")
async def zoom_webhook(request: Request):
    try:
        payload_bytes = await request.body()
        signature = request.headers.get('X-Zm-Signature', '')
        print(f"🔍 Webhook received - Signature: {signature}")
        print(f"🔍 Payload: {payload_bytes.decode()}")

        event_data = await request.json()
        print(f"🔍 Event data: {event_data}")

        # ✅ Handle Zoom URL Validation Challenge
        if event_data.get("event") == "endpoint.url_validation":
            plain_token = event_data.get("payload", {}).get("plainToken", "")
            print(f"🔍 Verification challenge - Plain token: {plain_token}")

            if plain_token:
                zoom_creds = load_zoom_credentials()
                secret_token = zoom_creds.get("secret-token", "")  # ✅ FIX HERE

                # Encrypt using HMAC-SHA256 with the Secret Token
                encrypted_token = base64.b64encode(
                    hmac.new(secret_token.encode(), plain_token.encode(), hashlib.sha256).digest()
                ).decode("utf-8")

                response = {
                    "plainToken": plain_token,
                    "encryptedToken": encrypted_token,
                }
                print(f"🔍 Sending verification response: {response}")
                return response

        # Normal event flow (after validation)
        print(f"🔍 Skipping signature verification for testing")
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

@app.get("/download-recording")
async def download_recording(download_url: str, filename: str = None):
    try:
        success = bot.download_recording_with_auth(download_url, filename)
        if success:
            return {"status": "success", "message": "Recording downloaded successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to download recording")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/recording/{recording_id}")
async def get_recording_download(recording_id: str):
    try:
        print(f"🔍 Attempting to download meeting recording: {recording_id}")
        
        if not bot.zoom_api:
            print(f"❌ Zoom API not initialized")
            raise HTTPException(status_code=500, detail="Zoom API not initialized")
        
        print(f"🔍 Getting fresh access token...")
        bot.zoom_api.get_access_token()
        
        if not bot.zoom_api.access_token:
            print(f"❌ Failed to get access token")
            raise HTTPException(status_code=401, detail="Unable to authenticate with Zoom")
        
        download_urls = [
            f"https://api.zoom.us/v2/meetings/{recording_id}/recordings/download",
            f"https://api.zoom.us/v2/recordings/{recording_id}/download"
        ]
        
        headers = {
            'Authorization': f'Bearer {bot.zoom_api.access_token}',
            'Accept': 'application/octet-stream, audio/mpeg, audio/mp3, */*',
            'User-Agent': 'Zoom-GHL-Integration/1.0'
        }
        
        response = None
        successful_url = None
        
        for download_url in download_urls:
            print(f"🔍 Trying URL: {download_url}")
            print(f"🔍 Using token: {bot.zoom_api.access_token[:20]}...")
            
            try:
                response = requests.get(download_url, headers=headers, stream=True, timeout=30)
                print(f"🔍 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    successful_url = download_url
                    print(f"✅ Success with URL: {download_url}")
                    break
                elif response.status_code == 404:
                    print(f"⚠️ 404 with URL: {download_url}, trying next...")
                    continue
                else:
                    print(f"⚠️ {response.status_code} with URL: {download_url}")
                    print(f"🔍 Error response: {response.text}")
                    continue
            except Exception as e:
                print(f"❌ Error with URL {download_url}: {e}")
                continue
        
        if not response or response.status_code != 200:
            print(f"❌ All download URLs failed")
            raise HTTPException(status_code=404, detail=f"Recording not found or inaccessible. Tried {len(download_urls)} different endpoints.")
        
        print(f"🔍 Response status: {response.status_code}")
        print(f"🔍 Response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            from fastapi.responses import StreamingResponse
            import io
            
            content_type = response.headers.get('content-type', 'application/octet-stream')
            content_length = response.headers.get('content-length', 'unknown')
            
            print(f"🔍 Content type: {content_type}, Length: {content_length}")
            
            def generate():
                try:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                except Exception as e:
                    print(f"❌ Error in stream generation: {e}")
                    raise
            
            return StreamingResponse(
                generate(),
                media_type=content_type,
                headers={
                    "Content-Disposition": f"attachment; filename=recording_{recording_id}.mp3",
                    "Content-Length": content_length
                }
            )
        else:
            error_detail = f"Download failed: {response.status_code} - {response.text}"
            print(f"❌ {error_detail}")
            raise HTTPException(status_code=response.status_code, detail=error_detail)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error downloading recording: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.get("/download/{uuid}")
async def download_phone_recording_by_uuid(uuid: str):
    """
    Download phone recording using UUID for maximum cache-busting
    """
    try:
        print(f"🔍 Downloading phone recording by UUID: {uuid}")
        
        # Extract account_id and file_id from UUID (we'll store this mapping)
        # For now, let's use a simple approach - decode from base64
        import base64
        try:
            decoded = base64.b64decode(uuid.encode()).decode()
            account_id, file_id = decoded.split('|')
        except:
            raise HTTPException(status_code=400, detail="Invalid UUID")
        
        print(f"🔍 Decoded - Account: {account_id}, File: {file_id}")

        if not bot.zoom_api:
            print(f"❌ Zoom API not initialized")
            raise HTTPException(status_code=500, detail="Zoom API not initialized")

        print(f"🔍 Getting fresh access token...")
        bot.zoom_api.get_access_token()

        if not bot.zoom_api.access_token:
            print(f"❌ Failed to get access token")
            raise HTTPException(status_code=401, detail="Unable to authenticate with Zoom")

        # Use the webhook's download URL directly
        webhook_download_url = f"https://zoom.us/v2/phone/recording/download/{file_id}"
        print(f"🔍 Using webhook download URL: {webhook_download_url}")
        
        headers = {
            'Authorization': f'Bearer {bot.zoom_api.access_token}',
            'Accept': 'application/octet-stream'
        }
        
        session = requests.Session()
        response = session.get(webhook_download_url, headers=headers, stream=True)
        
        if response.status_code == 200:
            print(f"✅ Download successful - serving HTML with JS download trigger")
            from fastapi.responses import HTMLResponse
            
            # Get the file content to create a blob URL
            file_content = response.content
            import base64
            file_base64 = base64.b64encode(file_content).decode()
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Download Recording</title>
                <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
                <meta http-equiv="Pragma" content="no-cache">
                <meta http-equiv="Expires" content="0">
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                    .download-btn {{ 
                        background: #007bff; 
                        color: white; 
                        padding: 15px 30px; 
                        border: none; 
                        border-radius: 5px; 
                        cursor: pointer; 
                        font-size: 16px;
                        margin: 20px;
                    }}
                    .download-btn:hover {{ background: #0056b3; }}
                </style>
            </head>
            <body>
                <h2>Phone Recording Download</h2>
                <p>Click the button below to download the recording:</p>
                <button class="download-btn" onclick="downloadFile()">Download Recording</button>
                <p><small>If download doesn't work, try right-clicking the button and "Save link as..."</small></p>
                
                <script>
                    function downloadFile() {{
                        try {{
                            // Create blob from base64 data
                            const byteCharacters = atob('{file_base64}');
                            const byteNumbers = new Array(byteCharacters.length);
                            for (let i = 0; i < byteCharacters.length; i++) {{
                                byteNumbers[i] = byteCharacters.charCodeAt(i);
                            }}
                            const byteArray = new Uint8Array(byteNumbers);
                            const blob = new Blob([byteArray], {{ type: 'audio/mpeg' }});
                            
                            // Create download link
                            const url = window.URL.createObjectURL(blob);
                            const link = document.createElement('a');
                            link.href = url;
                            link.download = 'phone_recording_{file_id}.mp3';
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);
                            window.URL.revokeObjectURL(url);
                            
                            // Update button text
                            document.querySelector('.download-btn').textContent = 'Download Complete!';
                            document.querySelector('.download-btn').style.background = '#28a745';
                        }} catch (error) {{
                            console.error('Download failed:', error);
                            alert('Download failed. Please try again.');
                        }}
                    }}
                    
                    // Auto-trigger download after 1 second
                    window.onload = function() {{
                        setTimeout(downloadFile, 1000);
                    }};
                </script>
            </body>
            </html>
            """
            
            return HTMLResponse(
                content=html_content,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        else:
            print(f"❌ Download failed: {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail="Failed to download recording")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error downloading phone recording: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.get("/phone-recording/{account_id}/{file_id}")
async def download_phone_recording_proxy(account_id: str, file_id: str, t: str = None):
    """
    Proxy endpoint for downloading Zoom phone recordings
    Uses the webhook's download URL directly (this is what worked in our local script)
    """
    try:
        print(f"🔍 Downloading phone recording - Account: {account_id}, File: {file_id}")

        if not bot.zoom_api:
            print(f"❌ Zoom API not initialized")
            raise HTTPException(status_code=500, detail="Zoom API not initialized")

        print(f"🔍 Getting fresh access token...")
        bot.zoom_api.get_access_token()

        if not bot.zoom_api.access_token:
            print(f"❌ Failed to get access token")
            raise HTTPException(status_code=401, detail="Unable to authenticate with Zoom")

        # Use the webhook's download URL directly (this is what worked in our local script)
        # The file_id parameter is actually the download file ID from the webhook
        webhook_download_url = f"https://zoom.us/v2/phone/recording/download/{file_id}"
        print(f"🔍 Using webhook download URL: {webhook_download_url}")
        
        headers = {
            'Authorization': f'Bearer {bot.zoom_api.access_token}',
            'Accept': 'application/octet-stream'
        }
        
        session = requests.Session()
        response = session.get(webhook_download_url, headers=headers, stream=True)
        
        if response.status_code == 200:
            print(f"✅ Download successful - streaming file")
            from fastapi.responses import StreamingResponse
            
            content_type = response.headers.get('content-type', 'audio/mpeg')
            content_length = response.headers.get('content-length', 'unknown')
            
            def generate():
                try:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                except Exception as e:
                    print(f"❌ Error in stream generation: {e}")
                    raise
            
            import time
            timestamp = int(time.time())
            unique_filename = f"phone_recording_{file_id}_{timestamp}.mp3"
            
            return StreamingResponse(
                generate(),
                media_type=content_type,
                headers={
                    "Content-Disposition": f"attachment; filename={unique_filename}",
                    "Content-Length": content_length,
                    "Cache-Control": "no-cache, no-store, must-revalidate, private",
                    "Pragma": "no-cache",
                    "Expires": "0",
                    "Last-Modified": "Thu, 01 Jan 1970 00:00:00 GMT",
                    "ETag": f'"{timestamp}"',
                    "X-Accel-Buffering": "no"  # Disable nginx buffering
                }
            )
        else:
            print(f"❌ Download failed: {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail="Failed to download recording")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error downloading phone recording: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Zoom-GHL Integration Server")
    print("=" * 50)
    print("📡 Webhook: http://localhost:8000/zoom-webhook")
    print("❤️ Health: http://localhost:8000/health")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
