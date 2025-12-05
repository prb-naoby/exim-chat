import json

import streamlit as st
from datetime import datetime
from modules import database
import os
from google import genai

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
                table_md = "| Case | Resolution |\n| :--- | :--- |\n"
                for case in cases:
                    # Escape pipes in content to avoid breaking table
                    q = case.get('question', '').replace('|', '\|').replace('\n', '<br>')
                    a = case.get('answer', '').replace('|', '\|').replace('\n', '<br>')
                    table_md += f"| {q} | {a} |\n"
                
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
                f"<div style='font-size: 0.75rem; color: var(--text-color); opacity: 0.6; margin-bottom: 0.2rem;'>{message['timestamp']}</div>", 
                unsafe_allow_html=True
            )
        
        # Display Content
        render_message_content(message["content"])

def handle_chat_input(prompt, session_key, chatbot_type, response_generator):
    """
    Handle new user input: add to state, save to db, generate response.
    """
    # 1. Add User Message
    user_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state[session_key].append({
        "role": "user", 
        "content": prompt, 
        "timestamp": user_timestamp
    })
    
    # 2. Save to DB
    database.save_message(
        "guest", 
        chatbot_type, 
        "user", 
        prompt,
        st.session_state.current_session_id,
        user_timestamp
    )
    
    # 3. Update Title if first message
    if len([m for m in st.session_state[session_key] if m["role"] == "user"]) == 1:
        database.update_session_title("guest", chatbot_type, st.session_state.current_session_id)
    
    # 4. Show User Message immediately
    with st.chat_message("user"):
        st.markdown(f"<div style='font-size: 0.75rem; color: var(--text-color); opacity: 0.6; margin-bottom: 0.2rem;'>{user_timestamp}</div>", unsafe_allow_html=True)
        st.markdown(prompt)
    
    # 5. Generate Response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = response_generator(prompt)
            assistant_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            st.markdown(f"<div style='font-size: 0.75rem; color: var(--text-color); opacity: 0.6; margin-bottom: 0.2rem;'>{assistant_timestamp}</div>", unsafe_allow_html=True)
            render_message_content(response)
    
    # 6. Add Assistant Message to State
    st.session_state[session_key].append({
        "role": "assistant", 
        "content": response, 
        "timestamp": assistant_timestamp
    })
    
    # 7. Save to DB
    database.save_message(
        "guest", 
        chatbot_type, 
        "assistant", 
        response,
        st.session_state.current_session_id,
        assistant_timestamp
    )

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
