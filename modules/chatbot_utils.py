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
    
    if not drive_id or not folder_path:
        return None

    token = get_onedrive_token()
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}
    graph_base_url = "https://graph.microsoft.com/v1.0"

    try:
        # 3. Search for File
        # We search specifically in the SOP folder
        search_url = f"{graph_base_url}/drives/{drive_id}/root:/{folder_path}:/search(q='{filename}')"
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        data = response.json()

        download_url = None
        # Find exact match or best match
        for item in data.get('value', []):
            if filename in item['name']:
                # Get the temporary download URL directly
                download_url = item.get('@microsoft.graph.downloadUrl')
                break
        
        if not download_url:
            print(f"File not found or no download URL: {filename}")
            return None

        # 5. Cache in Redis
        database.redis_client.setex(cache_key, 3599, download_url)
        return download_url
            
    except Exception as e:
        print(f"Error generating OneDrive link: {e}")
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

def render_message_content(content):
    """
    Render message content, handling special <CASE_DATA> blocks.
    """
    if "<CASE_DATA>" in content:
        parts = content.split("<CASE_DATA>")
        text_content = parts[0].strip()
        case_json = parts[1].strip()
        
        # Render text content
        st.markdown(text_content)
        
        # Render cases as table
        try:
            cases = json.loads(case_json)
            if cases:
                st.markdown("### Studi Kasus Terkait")
                
                # Build Markdown Table
                table_md = "| Case No | Pertanyaan | Jawaban |\n| :--- | :--- | :--- |\n"
                for case in cases:
                    # Escape pipes in content to avoid breaking table
                    q = case.get('question', '').replace('|', '\|').replace('\n', '<br>')
                    a = case.get('answer', '').replace('|', '\|').replace('\n', '<br>')
                    no = case.get('case_no', '')
                    table_md += f"| #{no} | {q} | {a} |\n"
                
                st.markdown(table_md, unsafe_allow_html=True)
        except Exception as e:
            print(f"Error rendering case data: {e}")
    else:
        st.markdown(content)

def render_chat_message(message, idx, session_key, edit_key, regen_callback):
    """
    Render a single chat message.
    
    Args:
        message (dict): Message object {role, content, timestamp}
        idx (int): Index in the message list
        session_key (str): Session state key for messages (e.g., 'messages_sop')
        edit_key (str): Session state key for edit index (e.g., 'edit_message_index')
        regen_callback (func): Function to call for regeneration/saving
    """
    with st.chat_message(message["role"]):
        # Header with timestamp
        if "timestamp" in message:
            st.markdown(
                f"<div style='font-size: 0.75rem; color: #888; margin-bottom: 0.2rem;'>{message['timestamp']}</div>", 
                unsafe_allow_html=True
            )
        
        # Display Content
        render_message_content(message["content"])

import threading
import time

def run_background_generation(prompt, session_key, chatbot_type, response_generator, session_id):
    """Background worker to generate response and update Redis"""
    try:
        # Generate Response
        response = response_generator(prompt)
        assistant_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Save to Redis
        database.save_message(
            "guest", 
            chatbot_type, 
            "assistant", 
            response,
            session_id,
            assistant_timestamp
        )
        
        # Update status to idle (done)
        database.set_session_status(session_id, "idle")
        
    except Exception as e:
        print(f"Error in background generation: {e}")
        database.set_session_status(session_id, "error")

def handle_chat_input(prompt, session_key, chatbot_type, response_generator):
    """
    Handle new user input: add to state, save to db, start background generation.
    """
    session_id = st.session_state.current_session_id
    user_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Add User Message to Local State (Optimistic UI)
    st.session_state[session_key].append({
        "role": "user", 
        "content": prompt, 
        "timestamp": user_timestamp
    })
    
    # 2. Save User Message to Redis
    database.save_message(
        "guest", 
        chatbot_type, 
        "user", 
        prompt,
        session_id,
        user_timestamp
    )
    
    # 3. Update Title if first message
    if len(st.session_state[session_key]) == 1:
         database.update_session_title("guest", chatbot_type, session_id)
    
    # 4. Set Status to Processing
    database.set_session_status(session_id, "processing")
    
    # 5. Start Background Thread
    thread = threading.Thread(
        target=run_background_generation,
        args=(prompt, session_key, chatbot_type, response_generator, session_id)
    )
    thread.start()
    
    # 6. Rerun to show the user message and enter polling mode
    st.rerun()

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
