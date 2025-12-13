import sqlite3
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from dotenv import load_dotenv
import uuid

load_dotenv()

# SQLite Configuration
DB_NAME = "chat_history.db"
# Store in 'data' directory for docker persistence
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", DB_NAME)

def get_db_connection():
    """Get a SQLite database connection"""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize SQLite database with all tables"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        
        # 1. Users Table
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT DEFAULT 'user',
                        display_name TEXT,
                        requested_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
        
        # Migration: Add display_name column if not exists
        c.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in c.fetchall()]
        if 'display_name' not in columns:
            c.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
            print("Added display_name column to users table")
        if 'requested_at' not in columns:
            c.execute("ALTER TABLE users ADD COLUMN requested_at TIMESTAMP")
            print("Added requested_at column to users table")
                    
        # 2. Sessions Table
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        username TEXT NOT NULL,
                        chatbot_type TEXT NOT NULL,
                        title TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'idle',
                        FOREIGN KEY(username) REFERENCES users(username)
                    )''')
                    
        # 3. Messages Table
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                    )''')
        
        # 4. Pending Users Table (for registration approval)
        c.execute('''CREATE TABLE IF NOT EXISTS pending_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        email TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'pending'
                    )''')
        
        # Migration: Rename created_at to requested_at in pending_users
        c.execute("PRAGMA table_info(pending_users)")
        pending_columns = [col[1] for col in c.fetchall()]
        if 'requested_at' not in pending_columns and 'created_at' in pending_columns:
            # SQLite doesn't support ALTER COLUMN with non-constant default (like CURRENT_TIMESTAMP)
            # So we add it as nullable, then populate it
            c.execute("ALTER TABLE pending_users ADD COLUMN requested_at TIMESTAMP")
            c.execute("UPDATE pending_users SET requested_at = created_at WHERE requested_at IS NULL")
            print("Migrated pending_users to use requested_at")
        
        # 5. LLM Logs Table (for developer dashboard)
        c.execute('''CREATE TABLE IF NOT EXISTS llm_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        username TEXT,
                        chatbot_type TEXT,
                        status TEXT,
                        input_tokens INTEGER DEFAULT 0,
                        output_tokens INTEGER DEFAULT 0,
                        latency_ms INTEGER DEFAULT 0,
                        error_message TEXT,
                        query TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
        
        # 6. Ingestion Logs Table (for admin dashboard)
        c.execute('''CREATE TABLE IF NOT EXISTS ingestion_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pipeline_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        files_processed INTEGER DEFAULT 0,
                        files_upserted INTEGER DEFAULT 0,
                        files_skipped INTEGER DEFAULT 0,
                        errors INTEGER DEFAULT 0,
                        summary TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
        
        conn.commit()
        conn.close()
        print(f"Successfully initialized SQLite database at {SQLITE_DB_PATH}")
    except Exception as e:
        print(f"Failed to initialize SQLite database: {e}")

# -----------------------------------------------------------------------------
# Ingestion Logging
# -----------------------------------------------------------------------------

def log_ingestion_run(pipeline_name: str, status: str, started_at: str = None, 
                      completed_at: str = None, files_processed: int = 0,
                      files_upserted: int = 0, files_skipped: int = 0,
                      errors: int = 0, summary: str = None) -> int:
    """Log an ingestion run to the database"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO ingestion_logs 
                     (pipeline_name, status, started_at, completed_at, files_processed,
                      files_upserted, files_skipped, errors, summary)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (pipeline_name, status, started_at, completed_at, files_processed,
                   files_upserted, files_skipped, errors, summary))
        log_id = c.lastrowid
        conn.commit()
        conn.close()
        return log_id
    except Exception as e:
        print(f"Error logging ingestion run: {e}")
        return -1

# -----------------------------------------------------------------------------
# User Management
# -----------------------------------------------------------------------------

def add_user(username, password_hash, role="user"):
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                  (username, password_hash, role))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"Error adding user: {e}")
        return False

def get_user_by_username(username):
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        if user:
            return dict(user)
        return None
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

def get_all_users():
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, username, display_name, role, requested_at, created_at FROM users")
        users = [dict(row) for row in c.fetchall()]
        conn.close()
        return users
    except Exception as e:
        print(f"Error getting all users: {e}")
        return []

def delete_user_by_id(user_id):
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False

def update_user_display_name(username, display_name):
    """Update user's display name"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET display_name = ? WHERE username = ?", 
                  (display_name, username))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating display name: {e}")
        return False

def update_user_password(username, new_password_hash):
    """Update user's password"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET password_hash = ? WHERE username = ?", 
                  (new_password_hash, username))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating password: {e}")
        return False

# -----------------------------------------------------------------------------
# Pending User Management
# -----------------------------------------------------------------------------

def add_pending_user(username, email, password_hash):
    """Add a user registration request for admin approval"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO pending_users (username, email, password_hash, requested_at) VALUES (?, ?, ?, ?)", 
                  (username, email, password_hash, datetime.now(ZoneInfo("Asia/Jakarta"))))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"Error adding pending user: {e}")
        return False

def get_pending_users():
    """Get all pending registration requests"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Use COALESCE to handle migration: prefer requested_at, fallback to created_at
        c.execute("""SELECT id, username, email, 
                     COALESCE(requested_at, created_at) as requested_at, status 
                     FROM pending_users WHERE status = 'pending' 
                     ORDER BY COALESCE(requested_at, created_at) DESC""")
        users = [dict(row) for row in c.fetchall()]
        conn.close()
        return users
    except Exception as e:
        print(f"Error getting pending users: {e}")
        return []

def get_pending_user_by_id(user_id):
    """Get a pending user by ID"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM pending_users WHERE id = ?", (user_id,))
        user = c.fetchone()
        conn.close()
        return dict(user) if user else None
    except Exception as e:
        print(f"Error getting pending user: {e}")
        return None

def approve_pending_user(user_id):
    """Approve a pending user and move them to users table"""
    try:
        pending = get_pending_user_by_id(user_id)
        if not pending:
            return False
        
        # Add to users table with requested_at from pending
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        requested_at = pending.get('requested_at') or pending.get('created_at')
        c.execute("""INSERT INTO users (username, password_hash, role, requested_at, created_at) 
                     VALUES (?, ?, 'user', ?, CURRENT_TIMESTAMP)""", 
                  (pending['username'], pending['password_hash'], requested_at))
        
        # Update pending status
        c.execute("UPDATE pending_users SET status = 'approved' WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error approving user: {e}")
        return False

def reject_pending_user(user_id):
    """Reject a pending user request"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE pending_users SET status = 'rejected' WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error rejecting user: {e}")
        return False

def check_pending_username_exists(username):
    """Check if username exists in pending users"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT 1 FROM pending_users WHERE username = ? AND status = 'pending'", (username,))
        exists = c.fetchone() is not None
        conn.close()
        return exists
    except Exception as e:
        print(f"Error checking pending username: {e}")
        return False

# -----------------------------------------------------------------------------
# Chat Session Management
# -----------------------------------------------------------------------------

def create_session(username, chatbot_type, session_id=None, title="New Chat"):
    if not session_id:
        session_id = str(uuid.uuid4())
    
    timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).isoformat()
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute("""INSERT INTO sessions (session_id, username, chatbot_type, title, created_at, last_activity) 
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (session_id, username, chatbot_type, title, timestamp, timestamp))
        conn.commit()
        conn.close()
        return session_id
    except Exception as e:
        print(f"Error creating session: {e}")
        return None

def get_chat_sessions(username, chatbot_type):
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get sessions with message count
        query = """
            SELECT s.session_id, s.title, s.last_activity, COUNT(m.id) as message_count 
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            WHERE s.username = ? AND s.chatbot_type = ?
            GROUP BY s.session_id
            ORDER BY s.last_activity DESC
        """
        c.execute(query, (username, chatbot_type))
        
        sessions = [dict(row) for row in c.fetchall()]
        conn.close()
        return sessions
    except Exception as e:
        print(f"Error getting sessions: {e}")
        return []

def get_session_by_id(session_id):
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        session = c.fetchone()
        conn.close()
        if session:
            return dict(session)
        return None
    except Exception as e:
        print(f"Error getting session: {e}")
        return None

def delete_session(username, chatbot_type, session_id): 
    # username and chatbot_type are for validation, but ID is unique
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error deleting session: {e}")

def update_session_title(session_id, title):
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE sessions SET title = ? WHERE session_id = ?", (title, session_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating session title: {e}")

def set_session_status(session_id, status):
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE sessions SET status = ? WHERE session_id = ?", (status, session_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error setting session status: {e}")

def get_session_status(session_id):
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT status FROM sessions WHERE session_id = ?", (session_id,))
        row = c.fetchone()
        conn.close()
        return row['status'] if row else 'idle'
    except Exception as e:
        return 'idle'

# -----------------------------------------------------------------------------
# Message Management
# -----------------------------------------------------------------------------

def save_message(username, chatbot_type, role, content, session_id, timestamp=None):
    if timestamp is None:
        timestamp = datetime.now().isoformat()
        
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        
        # Check if session exists, if not create it (auto-recovery)
        c.execute("SELECT 1 FROM sessions WHERE session_id = ?", (session_id,))
        if not c.fetchone():
            c.execute("""INSERT INTO sessions (session_id, username, chatbot_type, title, created_at, last_activity) 
                         VALUES (?, ?, ?, ?, ?, ?)""",
                      (session_id, username, chatbot_type, "New Chat", timestamp, timestamp))
        
        # Save message
        c.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                  (session_id, role, content, timestamp))
        
        # Update last activity
        c.execute("UPDATE sessions SET last_activity = ? WHERE session_id = ?", (timestamp, session_id))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving message: {e}")

def load_chat_history(username, chatbot_type, session_id=None):
    if not session_id:
        return []
        
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
        messages = [dict(row) for row in c.fetchall()]
        conn.close()
        return messages
    except Exception as e:
        print(f"Error loading chat history: {e}")
        return []

def clear_chat_history(username, chatbot_type, session_id=None):
    # This effectively clears messages for a session
    if not session_id:
        return
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error clearing chat history: {e}")

def delete_all_sessions(username, chatbot_type):
    """Delete all sessions for a specific user and chatbot type"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        c = conn.cursor()
        # Deleting sessions will cascade delete messages due to foreign key
        c.execute("DELETE FROM sessions WHERE username = ? AND chatbot_type = ?", (username, chatbot_type))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting all sessions: {e}")
        return False

# Compabitility shims for existing code
def create_empty_session(username, chatbot_type, session_id):
    create_session(username, chatbot_type, session_id)

def get_last_session_id(username, chatbot_type):
    sessions = get_chat_sessions(username, chatbot_type)
    if sessions:
        return sessions[0]['session_id']
    return None
