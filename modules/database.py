import redis
import json
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_DB = 0

# Initialize Redis client
redis_client = redis.Redis(
    host=REDIS_HOST, 
    port=REDIS_PORT, 
    password=REDIS_PASSWORD, 
    db=REDIS_DB, 
    decode_responses=True
)

def init_database():
    """Check Redis connection"""
    try:
        redis_client.ping()
        print("Successfully connected to Redis")
    except redis.ConnectionError:
        print("Failed to connect to Redis. Make sure Redis is running.")

def save_message(username, chatbot_type, role, content, session_id, timestamp=None):
    """Save a chat message to Redis"""
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    
    # Message object
    message = {
        "role": role,
        "content": content,
        "timestamp": timestamp,
        "chatbot_type": chatbot_type
    }
    
    # Keys
    session_key = f"session:{session_id}:messages"
    meta_key = f"session:{session_id}:meta"
    
    # Use pipeline for atomic operations
    pipe = redis_client.pipeline()
    
    # 1. Push message to list (Right Push preserves order)
    pipe.rpush(session_key, json.dumps(message))
    
    # 2. Update session metadata and last_activity
    pipe.hset(meta_key, mapping={
        "username": username,
        "chatbot_type": chatbot_type,
        "last_activity": timestamp
    })
    
    # 3. Add to sorted set of sessions for the user (score = timestamp)
    user_sessions_key = f"user:{username}:sessions:{chatbot_type}"
    # Score is timestamp as float (or int) for sorting
    try:
        score = datetime.fromisoformat(timestamp).timestamp()
    except:
        score = datetime.now().timestamp()
        
    pipe.zadd(user_sessions_key, {session_id: score})
    
    pipe.execute()

def load_chat_history(username, chatbot_type, session_id=None):
    """Load chat history from Redis"""
    if not session_id:
        return []
        
    session_key = f"session:{session_id}:messages"
    
    # Get all messages from list
    raw_messages = redis_client.lrange(session_key, 0, -1)
    
    messages = []
    for raw in raw_messages:
        try:
            msg = json.loads(raw)
            messages.append(msg)
        except json.JSONDecodeError:
            continue
            
    return messages

def clear_chat_history(username, chatbot_type, session_id=None):
    """Clear chat history (delete session)"""
    if not session_id:
        return

    session_key = f"session:{session_id}:messages"
    meta_key = f"session:{session_id}:meta"
    user_sessions_key = f"user:{username}:sessions:{chatbot_type}"
    
    pipe = redis_client.pipeline()
    pipe.delete(session_key)
    pipe.delete(meta_key)
    pipe.zrem(user_sessions_key, session_id)
    pipe.execute()

def get_chat_sessions(username, chatbot_type):
    """Get all chat sessions for a user and chatbot type sorted by last activity"""
    user_sessions_key = f"user:{username}:sessions:{chatbot_type}"
    
    # Get session IDs sorted by score (timestamp) descending
    session_ids = redis_client.zrevrange(user_sessions_key, 0, -1)
    
    sessions = []
    for sid in session_ids:
        meta_key = f"session:{sid}:meta"
        messages_key = f"session:{sid}:messages"
        
        # Get metadata
        meta = redis_client.hgetall(meta_key)
        
        # Get first message for title
        first_msg_raw = redis_client.lindex(messages_key, 0)
        first_msg_content = "New Chat"
        if first_msg_raw:
            try:
                first_msg_content = json.loads(first_msg_raw).get("content", "New Chat")
            except:
                pass
                
        title = meta.get("title", first_msg_content[:50] + "..." if len(first_msg_content) > 50 else first_msg_content)
        
        # Get message count
        count = redis_client.llen(messages_key)
        
        sessions.append({
            "session_id": sid,
            "title": title,
            "message_count": count,
            "last_message_time": meta.get("last_activity", "")
        })
        
    return sessions

def create_empty_session(username, chatbot_type, session_id):
    """Create an empty session placeholder"""
    timestamp = datetime.now().isoformat()
    meta_key = f"session:{session_id}:meta"
    user_sessions_key = f"user:{username}:sessions:{chatbot_type}"
    
    pipe = redis_client.pipeline()
    pipe.hset(meta_key, mapping={
        "username": username,
        "chatbot_type": chatbot_type,
        "created_at": timestamp,
        "last_activity": timestamp,
        "title": "New Chat"
    })
    
    score = datetime.now().timestamp()
    pipe.zadd(user_sessions_key, {session_id: score})
    pipe.execute()

def update_session_title(username, chatbot_type, session_id):
    """Update session title based on first user message"""
    messages_key = f"session:{session_id}:messages"
    meta_key = f"session:{session_id}:meta"
    
    # Find first user message
    messages = redis_client.lrange(messages_key, 0, -1)
    for raw in messages:
        try:
            msg = json.loads(raw)
            if msg.get("role") == "user":
                content = msg.get("content", "")
                title = content[:50] + "..." if len(content) > 50 else content
                redis_client.hset(meta_key, "title", title)
                break
        except:
            continue

def delete_session(username, chatbot_type, session_id):
    clear_chat_history(username, chatbot_type, session_id)

def get_last_empty_session(username, chatbot_type):
    """Get last empty session"""
    # Simply check the most recent session
    user_sessions_key = f"user:{username}:sessions:{chatbot_type}"
    last_ids = redis_client.zrevrange(user_sessions_key, 0, 0)
    
    if not last_ids:
        return None
        
    sid = last_ids[0]
    messages_key = f"session:{sid}:messages"
    count = redis_client.llen(messages_key)
    
    if count == 0:
        return sid
    return None

# Status management for async processing
def set_session_status(session_id, status):
    """Set session status (processing/idle)"""
    redis_client.hset(f"session:{session_id}:meta", "status", status)

def get_session_status(session_id):
    """Get session status"""
    return redis_client.hget(f"session:{session_id}:meta", "status") or "idle"
