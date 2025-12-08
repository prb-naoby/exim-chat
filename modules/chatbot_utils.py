import json

# ... (existing imports)

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
