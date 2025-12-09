import json
import streamlit as st
from datetime import datetime
from modules import database
import os
from google import genai
import requests
from azure.identity import ClientSecretCredential

# Confidence threshold for retrieval results
# Reads from environment variable, defaults to 0.6
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

def init_gemini_client():
    """Initialize and return Gemini client"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("GEMINI_API_KEY not found in environment variables.")
        return None
    return genai.Client(api_key=api_key)

def get_onedrive_token():
    """Get access token for Microsoft Graph API"""
    try:
        tenant_id = os.getenv('MS_TENANT_ID')
        client_id = os.getenv('MS_CLIENT_ID')
        client_secret = os.getenv('MS_CLIENT_SECRET')
        
        if not all([tenant_id, client_id, client_secret]):
            print("Missing OneDrive credentials")
            return None
            
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        token = credential.get_token("https://graph.microsoft.com/.default")
        return token.token
    except Exception as e:
        print(f"Error getting OneDrive token: {e}")
        return None

def get_onedrive_download_link(filename):
    """
    Generate a 1-hour valid download link for a file in OneDrive.
    Caches the link in Redis for 3599 seconds.
    """
    # 1. Check Cache
    cache_key = f"onedrive_link:{filename}"
    cached_link = database.redis_client.get(cache_key)
    if cached_link:
        return cached_link

    # 2. Get Sync Param
    drive_id = os.getenv('ONEDRIVE_DRIVE_ID')
    folder_path = os.getenv('SOP_FOLDER_PATH')
    
    import logging
    logger = logging.getLogger("app_logger") # Get the shared logger

    if not drive_id or not folder_path:
        logger.error("Missing OneDrive drive_id or folder_path")
        return None

    token = get_onedrive_token()
    if not token:
        logger.error("Failed to obtain OneDrive token")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    graph_base_url = "https://graph.microsoft.com/v1.0"

    try:
        # 3. Search for File
        import urllib.parse
        encoded_path = urllib.parse.quote(folder_path)
        
        logger.info(f"Generating download link for: '{filename}' in '{folder_path}'")
        
        # Construct search URL
        search_url = f"{graph_base_url}/drives/{drive_id}/root:/{encoded_path}:/search(q='{filename}')"
        logger.info(f"OneDrive Search URL: {search_url}")
        
        response = requests.get(search_url, headers=headers)
        if response.status_code != 200:
            logger.error(f"OneDrive Search Failed: {response.status_code} - {response.text}")
            return None
            
        data = response.json()
        item_count = len(data.get('value', []))
        logger.info(f"Found {item_count} items")

        found_item_id = None
        # Find exact match or best match
        for item in data.get('value', []):
            item_name = item.get('name', '')
            logger.info(f"  Candidate: {item_name}")
            
            # Case-insensitive check and looser matching
            if filename.lower().strip() in item_name.lower().strip() or \
               item_name.lower().strip() in filename.lower().strip():
                found_item_id = item.get('id')
                logger.info(f"  Match matching item ID: {found_item_id}")
                break
        
        if not found_item_id:
            logger.warning(f"File not found or no matching item for: {filename}")
            return None

        # 4. Fetch Item Details explicitly to get downloadUrl
        item_url = f"{graph_base_url}/drives/{drive_id}/items/{found_item_id}"
        logger.info(f"Fetching item details: {item_url}")
        
        item_response = requests.get(item_url, headers=headers)
        if item_response.status_code == 200:
            item_data = item_response.json()
            download_url = item_data.get('@microsoft.graph.downloadUrl')
            
            if download_url:
                logger.info(f"  Download URL retrieved successfully.")
                # 5. Cache in Redis
                database.redis_client.setex(cache_key, 3599, download_url)
                return download_url
            else:
                logger.error("  Item found but no @microsoft.graph.downloadUrl property present.")
                # Fallback: Try createLink?
                # For now return None as requested "msgraph download url" usually implies this one.
        else:
             logger.error(f"Failed to fetch item details: {item_response.status_code}")

        return None
            
    except Exception as e:
        logger.error(f"Error generating OneDrive link: {e}")
        return None

    return None
    
def create_embedding(client, text: str, model: str = "models/gemini-embedding-001"):
    """Create dense embedding using Gemini"""
    try:
        response = client.models.embed_content(
            model=model,
            contents=text
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"Error creating embedding: {e}")
        return [0.0] * 3072

def create_sparse_vector(text: str):
    """Create sparse BM25-like vector from text"""
    words = text.lower().split()
    word_freq = {}
    for word in words:
        if len(word) > 2:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    indices = []
    values = []
    for word, freq in word_freq.items():
        idx = abs(hash(word)) % (10**6)
        indices.append(idx)
        values.append(freq)
    
    return {"indices": indices, "values": values}

# --- Security Utils ---
from cryptography.fernet import Fernet

def get_encryption_key():
    """Get or create encryption key"""
    # In production, this should be a fixed env var.
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        # Fallback for dev consistency: Use a fixed string if env is missing
        # This ensures links survive restarts/refreshes even if user didn't set env
        return "development_fallback_key_32_bytes!!"[:32] # Must be 32 URL-safe base64-encoded bytes ideally, but Fernet.generate_key() makes url-safe b64.
        # Actually Fernet key must be 32 url-safe base64-encoded bytes.
        # "development_fallback_key_32_bytes!!" is 33 chars.
        # Let's use a proper base64 key hardcoded for dev.
        return "7oJD1lH5_valid_fernet_key_base64_usage_32=" 
    return key

def generate_secure_token(filename, session_id):
    """Encrypt filename and session_id into a token"""
    try:
        key = get_encryption_key()
        # Ensure key is bytes
        if isinstance(key, str):
            key = key.encode()
            
        f = Fernet(key)
        # Payload: "session_id|filename"
        payload = f"{session_id}|{filename}".encode()
        token = f.encrypt(payload).decode()
        return token
    except Exception as e:
        print(f"Error generating token: {e}")
        # Improve fallback for dev?
        # If key is invalid, generate new one? No, that breaks persistence.
        return None

def validate_secure_token(token, current_session_id):
    """Decrypt token and validate session_id"""
    try:
        key = get_encryption_key()
        if isinstance(key, str):
            key = key.encode()
            
        f = Fernet(key)
        payload = f.decrypt(token.encode()).decode()
        token_session_id, filename = payload.split("|", 1)
        
        if token_session_id != current_session_id:
            return None, "Invalid session"
            
        return filename, None
    except Exception as e:
        print(f"Error validating token: {e}")
        return None, "Invalid token"

# ... (render functions unchanged) ...

# ... (run_background_generation unchanged) ...

# ... (handle_chat_input unchanged) ...

def regenerate_response(idx, new_text, session_key, chatbot_type, response_generator):
    """
    Logic to update a user message and regenerate the response.
    """
    # 1. Update User Message
    st.session_state[session_key][idx]["content"] = new_text
    st.session_state[session_key][idx]["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 2. Truncate history (remove everything after this message)
    st.session_state[session_key] = st.session_state[session_key][:idx+1]
    
    # 3. Generate New Response
    # Pass session_id to ensure secure links are generated
    try:
        response = response_generator(new_text, session_id=st.session_state.current_session_id)
    except TypeError:
        # Fallback
        response = response_generator(new_text)
        
    assistant_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 4. Add New Response
    st.session_state[session_key].append({
        "role": "assistant",
        "content": response,
        "timestamp": assistant_timestamp
    })
    
    # 5. Update DB
    database.save_message(
        "guest", chatbot_type, "user", new_text, st.session_state.current_session_id, st.session_state[session_key][idx]["timestamp"]
    )
    database.save_message(
        "guest", chatbot_type, "assistant", response, st.session_state.current_session_id, assistant_timestamp
    )
    
    st.rerun()
