import sqlite3
import json
from datetime import datetime
from pathlib import Path

# Database path
# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "chat_history.db"

def init_database():
    """Initialize the database and create tables if they don't exist"""
    # Ensure data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create chat_history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chatbot_type TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            session_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    # Check if session_id column exists, if not add it (migration)
    cursor.execute("PRAGMA table_info(chat_history)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if "session_id" not in columns:
        # Add session_id column with default value
        cursor.execute("ALTER TABLE chat_history ADD COLUMN session_id TEXT DEFAULT 'legacy'")
        conn.commit()
    
    # Create index for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_chatbot 
        ON chat_history(user_id, chatbot_type, session_id, timestamp)
    """)
    
    conn.commit()
    conn.close()

def get_or_create_user(username):
    """Get user_id or create new user if doesn't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Try to get existing user
    cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    
    if result:
        user_id = result[0]
    else:
        # Create new user
        cursor.execute("INSERT INTO users (username) VALUES (?)", (username,))
        user_id = cursor.lastrowid
        conn.commit()
    
    conn.close()
    return user_id

def save_message(username, chatbot_type, role, content, session_id, timestamp=None):
    """Save a chat message to the database with optional timestamp"""
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    user_id = get_or_create_user(username)
    
    cursor.execute("""
        INSERT INTO chat_history (user_id, chatbot_type, role, content, session_id, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, chatbot_type, role, content, session_id, timestamp))
    
    conn.commit()
    conn.close()

def load_chat_history(username, chatbot_type, session_id=None):
    """Load chat history for a specific user and chatbot, optionally filtered by session"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    user_id = get_or_create_user(username)
    
    if session_id:
        cursor.execute("""
            SELECT role, content, timestamp
            FROM chat_history
            WHERE user_id = ? AND chatbot_type = ? AND session_id = ?
            ORDER BY timestamp ASC
        """, (user_id, chatbot_type, session_id))
    else:
        cursor.execute("""
            SELECT role, content, timestamp
            FROM chat_history
            WHERE user_id = ? AND chatbot_type = ?
            ORDER BY timestamp ASC
        """, (user_id, chatbot_type))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "role": row[0],
            "content": row[1],
            "timestamp": row[2]
        })
    
    conn.close()
    return messages

def clear_chat_history(username, chatbot_type, session_id=None):
    """Clear chat history for a specific user and chatbot, optionally for a specific session"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    user_id = get_or_create_user(username)
    
    if session_id:
        cursor.execute("""
            DELETE FROM chat_history
            WHERE user_id = ? AND chatbot_type = ? AND session_id = ?
        """, (user_id, chatbot_type, session_id))
    else:
        cursor.execute("""
            DELETE FROM chat_history
            WHERE user_id = ? AND chatbot_type = ?
        """, (user_id, chatbot_type))
    
    conn.commit()
    conn.close()

def get_all_chat_history(username):
    """Get all chat history for a user (for export or analytics)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    user_id = get_or_create_user(username)
    
    cursor.execute("""
        SELECT chatbot_type, role, content, timestamp
        FROM chat_history
        WHERE user_id = ?
        ORDER BY timestamp ASC
    """, (user_id,))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "chatbot_type": row[0],
            "role": row[1],
            "content": row[2],
            "timestamp": row[3]
        })
    
    conn.close()
    return messages

def get_chat_statistics(username):
    """Get statistics about user's chat usage"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    user_id = get_or_create_user(username)
    
    cursor.execute("""
        SELECT 
            chatbot_type,
            COUNT(*) as message_count,
            MIN(timestamp) as first_message,
            MAX(timestamp) as last_message
        FROM chat_history
        WHERE user_id = ? AND role = 'user'
        GROUP BY chatbot_type
    """, (user_id,))
    
    stats = {}
    for row in cursor.fetchall():
        stats[row[0]] = {
            "message_count": row[1],
            "first_message": row[2],
            "last_message": row[3]
        }
    
    conn.close()
    return stats

def get_chat_sessions(username, chatbot_type):
    """Get all chat sessions for a user and chatbot type"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    user_id = get_or_create_user(username)
    
    cursor.execute("""
        SELECT 
            session_id,
            MIN(timestamp) as first_message_time,
            MAX(timestamp) as last_message_time,
            COUNT(*) as message_count,
            (SELECT content FROM chat_history 
             WHERE user_id = ? AND chatbot_type = ? AND session_id = ch.session_id AND role = 'user'
             ORDER BY timestamp ASC LIMIT 1) as first_user_message
        FROM chat_history ch
        WHERE user_id = ? AND chatbot_type = ?
        GROUP BY session_id
        ORDER BY last_message_time DESC
    """, (user_id, chatbot_type, user_id, chatbot_type))
    
    sessions = []
    for row in cursor.fetchall():
        # Create a title from the first user message (truncate if too long)
        first_message = row[4] if row[4] else "New Chat"
        title = first_message[:50] + "..." if len(first_message) > 50 else first_message
        
        sessions.append({
            "session_id": row[0],
            "first_message_time": row[1],
            "last_message_time": row[2],
            "message_count": row[3],
            "title": title
        })
    
    conn.close()
    return sessions

def create_empty_session(username, chatbot_type, session_id):
    """Create an empty session placeholder so it appears in sidebar immediately"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    user_id = get_or_create_user(username)
    
    # Insert a system message to mark the session as created
    cursor.execute("""
        INSERT INTO chat_history (user_id, chatbot_type, role, content, session_id)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, chatbot_type, "system", "Session created", session_id))
    
    conn.commit()
    conn.close()

def update_session_title(username, chatbot_type, session_id):
    """Update session by removing system placeholder if user has sent messages"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    user_id = get_or_create_user(username)
    
    # Check if there are user messages
    cursor.execute("""
        SELECT COUNT(*) FROM chat_history
        WHERE user_id = ? AND chatbot_type = ? AND session_id = ? AND role = 'user'
    """, (user_id, chatbot_type, session_id))
    
    user_message_count = cursor.fetchone()[0]
    
    # If there are user messages, remove the system placeholder
    if user_message_count > 0:
        cursor.execute("""
            DELETE FROM chat_history
            WHERE user_id = ? AND chatbot_type = ? AND session_id = ? AND role = 'system'
        """, (user_id, chatbot_type, session_id))
        conn.commit()
    
    conn.close()

def delete_session(username, chatbot_type, session_id):
    """Delete a specific chat session"""
    clear_chat_history(username, chatbot_type, session_id)

def get_last_empty_session(username, chatbot_type):
    """Get the last session if it's empty (only has system message), otherwise return None"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    user_id = get_or_create_user(username)
    
    cursor.execute("""
        SELECT session_id FROM chat_history
        WHERE user_id = ? AND chatbot_type = ?
        GROUP BY session_id
        HAVING (
            COUNT(CASE WHEN role = 'user' THEN 1 END) = 0
            AND COUNT(CASE WHEN role = 'assistant' THEN 1 END) = 0
        )
        ORDER BY MAX(timestamp) DESC
        LIMIT 1
    """, (user_id, chatbot_type))
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None
