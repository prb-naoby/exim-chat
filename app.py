import streamlit as st
from modules import database, chatbot_utils, app_logger
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import uuid
import extra_streamlit_components as stx

# Load environment variables
load_dotenv()

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

# Initialize cookie manager (must be at top level)
# Use a fixed key to maintain component identity without caching (which fails with widgets)
cookie_manager = stx.CookieManager(key="system_cookie_manager")

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_page" not in st.session_state:
    st.session_state.current_page = "SOP"
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "delete_confirm" not in st.session_state:
    st.session_state.delete_confirm = None
if "browser_id" not in st.session_state:
    st.session_state.browser_id = None

# Initialize Browser ID (for private history)
# Try to get from cookie first
if st.session_state.browser_id is None:
    # Use get_all() to check if manager is ready first implicitly
    all_cookies = cookie_manager.get_all()
    browser_id = cookie_manager.get("browser_id")
    
    if not browser_id:
        if all_cookies is not None: # Manager is ready but cookie missing
            browser_id = str(uuid.uuid4())
            cookie_manager.set("browser_id", browser_id, expires_at=datetime.now() + timedelta(days=365))
            st.session_state.browser_id = browser_id
    else:
        st.session_state.browser_id = browser_id
        
# If still None (manager loading), we might need to wait or use a temp fallback?
# Usually extra_streamlit_components will trigger rerun once loaded.
# Fallback for now to prevent NoneType errors if accessed
if not st.session_state.browser_id:
   st.session_state.browser_id = "guest" 

def check_password():
    """Returns `True` if the user had the correct password."""
    # 1. Check Session State
    if st.session_state.get("authenticated", False):
        return True

    # 2. Check Cookies (Persistence)
    # 2. Check Cookies (Persistence)
    # Note: cookie_manager.get() might return None on first render while syncing
    # We can try to use get_all() to check if manager is ready
    cookies = cookie_manager.get_all()
    logger.info(f"DEBUG: Cookie Manager get_all(): {cookies}")
    
    auth_cookie = cookie_manager.get("auth_token")
    logger.info(f"DEBUG: auth_token cookie: {auth_cookie}")
    
    if auth_cookie == "valid": 
        st.session_state.authenticated = True
        saved_session = cookie_manager.get("session_id")
        logger.info(f"DEBUG: session_id cookie: {saved_session}")
        
        if saved_session:
             st.session_state.current_session_id = saved_session
             logger.info(f"Session restored from cookie: {saved_session}")
        else:
             logger.warning("Auth valid but session_id cookie missing/None. Attempting restoration.")
             # Auto-recover: Try to restore last session first
             username = st.session_state.get("browser_id", "guest")
             last_sid = database.get_last_session_id(username, "SOP")
             if last_sid:
                 st.session_state.current_session_id = last_sid
                 logger.info(f"Auto-recovered last session for {username}: {last_sid}")
             else:
                 # Generate new session ID
                 import uuid
                 new_sid = str(uuid.uuid4())
                 st.session_state.current_session_id = new_sid
                 # Also ensure empty chat session exists in DB
                 database.create_empty_session(username, "SOP", new_sid)
                 logger.info(f"Created new session during recovery for {username}: {new_sid}")
                 
             cookie_manager.set("session_id", st.session_state.current_session_id, expires_at=datetime.now() + timedelta(days=7))
             
        return True
    elif auth_cookie is None:
        logger.info("Auth cookie is None (loading or missing)")
        # Could be loading or actually missing. 
        # If we barely started, we might want to wait?
        pass
    else:
        logger.info(f"Auth cookie invalid value: {auth_cookie}")

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
            border: none !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Centering layout
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("<br>" * 5, unsafe_allow_html=True) # Vertical spacer
        
        # Login Form
        # Use a container to avoid re-rendering issues?
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
                    # Set Cookies with Expiry to prevent logout on refresh
                    expires = datetime.now() + timedelta(days=7)
                    cookie_manager.set("auth_token", "valid", expires_at=expires, key="set_auth")
                    
                    # Session Restoration Logic: Persist history until cleared
                    if not st.session_state.current_session_id:
                        # Try to restore last active session for this browser
                        username = st.session_state.get("browser_id", "guest")
                        last_sid = database.get_last_session_id(username, "SOP")
                        if last_sid:
                            st.session_state.current_session_id = last_sid
                            logger.info(f"Restoring last active session on login for {username}: {last_sid}")
                        else:
                            # Create new if none exists
                            import uuid
                            new_sid = str(uuid.uuid4())
                            st.session_state.current_session_id = new_sid
                            database.create_empty_session(username, "SOP", new_sid)
                            logger.info(f"Creating new session on login for {username}: {new_sid}")

                    cookie_manager.set("session_id", st.session_state.current_session_id, expires_at=expires, key="set_sid")
                        
                    logger.info("User logged in successfully")
                    st.rerun()
                else:
                    st.error("Password salah")

    return False

# ... (rest of Start/Load/Delete functions) ...

def main():
    """Main application"""
    
    # 1. Check for download request (Redirection)
    query_params = st.query_params
    
    # A. Secure Token Link
    if "token" in query_params:
        # We process this AFTER auth to ensure session context is loaded from cookies
        pass 
        
    # B. Legacy Direct Link
    # If the user clicked a legacy link, we still want to authenticate them first.
    if "download_file" in query_params:
        pass

    # 2. Authentication Check (Restores Session)
    if not check_password():
        return
        
    # 3. Handle Token/Download AFTER Auth (Authenticated Zone)
    # Now st.session_state.current_session_id should be restored if a cookie existed
    
    # A. Secure Token Handling
    if "token" in query_params:
        token = query_params["token"]
        current_sid = st.session_state.current_session_id
        
        if not current_sid:
            # Try to restore from cookie one last time if check_password didn't catch it for some reason?
            # Or just create a new one?
            # Creating a new session means the session ID won't match the token (if the token was made for a previous session).
            # But if the user is just opening a link sent to them, they might not HAVE a session.
            # Secure links are strict: "Only the session that created it".
            st.error("Session mismatch or expired. This download link is tied to a specific chat session.")
            st.stop()
            
        filename, error = chatbot_utils.validate_secure_token(token, current_sid)
        
        if error:
            logger.warning(f"Token validation failed: {error}")
            st.error(f"Download link invalid or expired: {error}")
            st.stop()
            
        if filename:
            logger.info(f"Token verified for file: {filename}")
            with st.spinner(f"Generating download link for {filename}..."):
                download_url = chatbot_utils.get_onedrive_download_link(filename)
                
                if download_url:
                    logger.info(f"Redirecting user to download URL: {download_url}")
                    st.markdown(f'<meta http-equiv="refresh" content="0; url={download_url}">', unsafe_allow_html=True)
                    st.stop()
                else:
                    st.error("Failed to generate download link. File might not exist.")
                    st.stop()

    # B. Legacy Link Handling (Backwards Compatibility)
    if "download_file" in query_params:
        filename = query_params["download_file"]
        logger.info(f"Received LEGACY download request for file: {filename}")
        
        with st.spinner(f"Generating download link for {filename}..."):
            download_url = chatbot_utils.get_onedrive_download_link(filename)
            
            if download_url:
                logger.info(f"Redirecting user to legacy download URL: {download_url}")
                st.markdown(f'<meta http-equiv="refresh" content="0; url={download_url}">', unsafe_allow_html=True)
                st.stop()
            else:
                st.error("Failed to generate download link.")


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
