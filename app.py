import streamlit as st
from modules import database, chatbot_utils, app_logger
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logger
logger = app_logger.setup_logger()
logger.info("Application started")

# Initialize database on startup
database.init_database()

# Configure the page
st.set_page_config(
    page_title="EXIM Assistant",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_page" not in st.session_state:
    st.session_state.current_page = "SOP"
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "delete_confirm" not in st.session_state:
    st.session_state.delete_confirm = None

def check_password():
    """Returns `True` if the user had the correct password."""
    if st.session_state.get("authenticated", False):
        return True

    # Custom CSS for the login page
    st.markdown("""
        <style>
        /* Target the login form container */
        [data-testid="stForm"] {
            background-color: var(--secondary-background-color);
            padding: 2rem;
            border-radius: 10px;
            border: 1px solid rgba(128, 128, 128, 0.2);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        /* Input field styling */
        .stTextInput input {
            background-color: var(--background-color) !important;
            color: var(--text-color) !important;
            border: 1px solid rgba(128, 128, 128, 0.2) !important;
        }
        
        /* Submit button styling - Red color */
        .stButton button {
            background-color: #FF4B4B !important;
            color: white !important;
            border: none !important;
            width: 100%;
        }
        .stButton button:hover {
            background-color: #FF3333 !important;
            opacity: 1 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Centering layout
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("<br>" * 5, unsafe_allow_html=True) # Vertical spacer
        
        # Login Form
        with st.form("login_form"):
            # Header Content inside the form for visual grouping
            st.markdown("""
                <div style='text-align: center; margin-bottom: 2rem;'>
                    <div style='font-size: 3rem; margin-bottom: 1rem;'>🔐</div>
                    <h2 style='font-weight: 600; margin-bottom: 0.5rem;'>EXIM Chat<br>Assistant</h2>
                    <p style='color: #888; font-size: 0.9rem;'>Silakan login untuk melanjutkan</p>
                </div>
            """, unsafe_allow_html=True)
            
            password = st.text_input("Password", type="password", placeholder="Masukkan password...", label_visibility="collapsed")
            st.markdown("<br>", unsafe_allow_html=True)
            submit = st.form_submit_button("Login")
            
            if submit:
                correct_password = os.getenv("APP_PASSWORD")
                if password == correct_password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Password salah")

    return False

def start_new_chat():
    """Start a new chat session, or reuse empty one if exists"""
    import uuid
    
    # Check if there's an empty session to reuse
    empty_session = database.get_last_empty_session(
        "guest", # Single user mode
        st.session_state.current_page
    )
    
    if empty_session:
        # Reuse the empty session
        st.session_state.current_session_id = empty_session
    else:
        # Create a new session
        st.session_state.current_session_id = str(uuid.uuid4())
        database.create_empty_session(
            "guest",
            st.session_state.current_page,
            st.session_state.current_session_id
        )
    
    # Clear current messages
    if st.session_state.current_page == "INSW":
        st.session_state.messages_insw = []
    else:
        st.session_state.messages_sop = []
    
    st.rerun()

def load_session(session_id, chatbot_type):
    """Load a specific chat session"""
    st.session_state.current_session_id = session_id
    st.session_state.current_page = chatbot_type
    
    # Load messages for this session
    messages = database.load_chat_history(
        "guest", 
        chatbot_type, 
        session_id
    )
    
    if chatbot_type == "INSW":
        st.session_state.messages_insw = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in messages
        ]
    else:
        st.session_state.messages_sop = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in messages
        ]
    
    st.rerun()

def delete_session_with_confirm(session_id, chatbot_type):
    """Delete a session after confirmation"""
    database.delete_session("guest", chatbot_type, session_id)
    if st.session_state.current_session_id == session_id:
        start_new_chat()
    st.session_state.delete_confirm = None
    st.rerun()

def main():
    """Main application"""
    
    # 1. Authentication Check
    if not check_password():
        return


    # Initialize messages if not exists
    if "messages_insw" not in st.session_state:
        st.session_state.messages_insw = []
    if "messages_sop" not in st.session_state:
        st.session_state.messages_sop = []
    
    # Initialize session ID if not exists
    if st.session_state.current_session_id is None:
        import uuid
        st.session_state.current_session_id = str(uuid.uuid4())
    
    # Custom CSS for minimal, elegant design (supports dark and light mode)
    st.markdown("""
            <style>
            /* Reserve space at top for the fixed header */
            .block-container {
                padding-top: 2rem;
                padding-bottom: 0rem;
                max-width: 1200px;
            }
            
            /* Hide default streamlit elements except sidebar toggle */
            #MainMenu {visibility: hidden;}
            .stAppDeployButton {visibility: hidden;}
            footer {visibility: hidden;}
            
            /* Chat container - adapts to theme */
            .stChatMessage {
                border: 1px solid rgba(128, 128, 128, 0.2);
                border-radius: 8px;
                padding: 1rem;
                margin-bottom: 0.5rem;
            }
            
            /* Input styling */
            .stChatInputContainer {
                border-top: 1px solid rgba(128, 128, 128, 0.2);
                padding-top: 1rem;
            }
            
            /* Button styling - adapts to theme */
            .stButton button {
                border-radius: 6px;
                border: 1px solid rgba(128, 128, 128, 0.2);
                font-weight: 400;
                padding: 0.5rem 1.5rem;
                transition: all 0.2s;
            }
            
            .stButton button:hover {
                border-color: rgba(128, 128, 128, 0.4);
                opacity: 0.8;
            }
            
            /* Remove extra spacing */
            .element-container {
                margin-bottom: 0.5rem;
            }
            
            h1 {
                font-weight: 300;
                font-size: 2rem;
                margin-bottom: 0.5rem;
            }
            
            /* Divider line - adapts to theme */
            hr {
                border: none;
                border-top: 1px solid rgba(128, 128, 128, 0.2);
                margin: 1.5rem 0;
            }
            
            .stAlert {
                border-radius: 6px;
                padding: 0.75rem;
            }
            
            /* Sidebar styling */
            [data-testid="stSidebar"] {
                padding-top: 1.5rem;
            }
            
            /* Make sidebar buttons more compact and list-like */
            [data-testid="stSidebar"] .stButton button {
                padding: 0.5rem 0.75rem;
                font-size: 0.875rem;
                min-height: auto;
                height: auto;
                border-radius: 8px;
                text-align: left;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            
            /* Remove all gaps between buttons */
            [data-testid="stSidebar"] .element-container {
                margin-bottom: 0;
                padding-bottom: 0;
            }
            
            /* Reduce spacing in columns */
            [data-testid="stSidebar"] [data-testid="column"] {
                padding: 0 0.15rem;
                gap: 0;
            }
            
            /* Remove vertical spacing between rows */
            [data-testid="stSidebar"] .row-widget {
                margin-bottom: 0.25rem;
            }
            </style>
        """, unsafe_allow_html=True)

    # Sidebar for user info
    with st.sidebar:
        st.title("EXIM Chatbot")
        st.markdown("")
        
        if st.button("📖 SOP", key="nav_sop", use_container_width=True, type="primary" if st.session_state.current_page == "SOP" else "secondary"):
            if st.session_state.current_page != "SOP":
                st.session_state.current_page = "SOP"
                if st.session_state.current_session_id is None:
                    import uuid
                    st.session_state.current_session_id = str(uuid.uuid4())
                st.rerun()
        
        if st.button("📋 HS Code", key="nav_insw", use_container_width=True, type="primary" if st.session_state.current_page == "INSW" else "secondary"):
            if st.session_state.current_page != "INSW":
                st.session_state.current_page = "INSW"
                if st.session_state.current_session_id is None:
                    import uuid
                    st.session_state.current_session_id = str(uuid.uuid4())
                st.rerun()
        
        st.divider()

        
        # Clear chat button
        if st.button("🗑️ Clear Chat History", use_container_width=True, key="clear_chat_btn"):
            chatbot_type = st.session_state.current_page
            # Clear chat history for current session
            if st.session_state.current_session_id:
                # Using 'guest' as default username since authentication is removed
                database.clear_chat_history(
                    "guest", 
                    chatbot_type, 
                    st.session_state.current_session_id
                )
            
            # Clear session state messages
            if chatbot_type == "INSW":
                st.session_state.messages_insw = []
            else:
                st.session_state.messages_sop = []
            
            st.rerun()
        
        # Spacer
        st.markdown("<br>" * 2, unsafe_allow_html=True)
    
    # Display selected page
    if st.session_state.current_page == "INSW":
        import modules.insw_chatbot as insw_chatbot
        insw_chatbot.show()
    elif st.session_state.current_page == "SOP":
        import modules.sop_chatbot as sop_chatbot
        sop_chatbot.show()

if __name__ == "__main__":
    main()
