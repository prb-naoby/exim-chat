
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from datetime import timedelta
from modules import database, auth_utils, chatbot_utils
from fastapi.concurrency import run_in_threadpool
from modules.llm_logger import llm_logger
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"

class UserOut(BaseModel):
    id: int
    username: str
    role: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatSessionCreate(BaseModel):
    chatbot_type: str
    title: str = "New Chat"

# -----------------------------------------------------------------------------
# Dependency: Get Current User
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Dependency: Get Current User (supports Header and Cookie)
# -----------------------------------------------------------------------------
from fastapi import Cookie

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    access_token: Optional[str] = Cookie(None)
):
    # Prefer header token if available, else cookie
    final_token = token or access_token
    
    # DEBUG: Log auth attempt
    # print(f"DEBUG: Auth Check. Header: {token is not None}, Cookie: {access_token is not None}")
    
    if not final_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = auth_utils.decode_access_token(final_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    user = database.get_user_by_username(username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

async def get_current_admin_user(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return current_user

# -----------------------------------------------------------------------------
# Auth Endpoints
# -----------------------------------------------------------------------------

@router.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # Try to get user
    user = database.get_user_by_username(form_data.username)
    
    # Verify password (assuming hash match)
    # If using 'admin' with plain text or hash? 
    # For now, let's assume auth_utils handles verification properly.
    if not user or not auth_utils.verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_utils.create_access_token(
        data={"sub": user["username"], "role": user["role"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/auth/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """Return current user info including display_name"""
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "display_name": current_user.get("display_name") or current_user["username"],
        "role": current_user["role"]
    }

class ProfileUpdate(BaseModel):
    display_name: str

@router.patch("/auth/profile")
async def update_profile(
    profile: ProfileUpdate, 
    current_user: dict = Depends(get_current_user)
):
    """Update user's display name"""
    success = database.update_user_display_name(current_user["username"], profile.display_name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update profile")
    return {"message": "Profile updated successfully", "display_name": profile.display_name}

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

@router.patch("/auth/password")
async def change_password(
    passwords: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    """Change user's password"""
    # Verify current password
    if not auth_utils.verify_password(passwords.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Hash new password and update
    new_hash = auth_utils.get_password_hash(passwords.new_password)
    success = database.update_user_password(current_user["username"], new_hash)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update password")
    return {"message": "Password changed successfully"}

# -----------------------------------------------------------------------------
# Registration Endpoint (Public)
# -----------------------------------------------------------------------------

class UserRegister(BaseModel):
    username: str
    email: str
    password: str

@router.post("/auth/register")
async def register_user(user: UserRegister):
    """Public endpoint for user registration. Creates a pending user for admin approval."""
    # Check if username already exists in users
    existing_user = database.get_user_by_username(user.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if username already pending
    if database.check_pending_username_exists(user.username):
        raise HTTPException(status_code=400, detail="Registration already pending for this username")
    
    # Hash password and add to pending users
    hashed_password = auth_utils.get_password_hash(user.password)
    success = database.add_pending_user(user.username, user.email, hashed_password)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to submit registration request")
    
    return {"message": "Registration request submitted. Please wait for admin approval."}

# -----------------------------------------------------------------------------
# Admin Endpoints
# -----------------------------------------------------------------------------

@router.post("/admin/users", response_model=UserOut, dependencies=[Depends(get_current_admin_user)])
async def create_user(user: UserCreate):
    db_user = database.get_user_by_username(user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = auth_utils.get_password_hash(user.password)
    success = database.add_user(user.username, hashed_password, user.role)
    
    if not success:
         raise HTTPException(status_code=500, detail="Failed to create user")
         
    new_user = database.get_user_by_username(user.username)
    return new_user

@router.get("/admin/users", response_model=List[UserOut], dependencies=[Depends(get_current_admin_user)])
async def read_users():
    return database.get_all_users()

@router.delete("/admin/users/{user_id}", dependencies=[Depends(get_current_admin_user)])
async def delete_user(user_id: int):
    success = database.delete_user_by_id(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}

# Pending Users Management
@router.get("/admin/pending-users", dependencies=[Depends(get_current_admin_user)])
async def get_pending_users():
    """Get all pending registration requests"""
    return database.get_pending_users()

@router.post("/admin/pending-users/{user_id}/approve", dependencies=[Depends(get_current_admin_user)])
async def approve_user(user_id: int):
    """Approve a pending user registration"""
    success = database.approve_pending_user(user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to approve user")
    return {"message": "User approved successfully"}

@router.post("/admin/pending-users/{user_id}/reject", dependencies=[Depends(get_current_admin_user)])
async def reject_user(user_id: int):
    """Reject a pending user registration"""
    success = database.reject_pending_user(user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reject user")
    return {"message": "User rejected"}

# -----------------------------------------------------------------------------
# Chat Endpoints
# -----------------------------------------------------------------------------

@router.get("/chat/sessions/{chatbot_type}")
async def get_sessions(chatbot_type: str, current_user: dict = Depends(get_current_user)):
    if chatbot_type not in ["SOP", "INSW", "OTHERS"]:
         raise HTTPException(status_code=400, detail="Invalid chatbot type")
    return database.get_chat_sessions(current_user["username"], chatbot_type)

@router.post("/chat/sessions")
async def create_session(session: ChatSessionCreate, current_user: dict = Depends(get_current_user)):
    session_id = database.create_session(current_user["username"], session.chatbot_type, title=session.title)
    if not session_id:
         raise HTTPException(status_code=500, detail="Failed to create session")
    return {"session_id": session_id}

@router.delete("/chat/sessions/{chatbot_type}")
async def delete_all_sessions(chatbot_type: str, current_user: dict = Depends(get_current_user)):
    if chatbot_type not in ["SOP", "INSW", "OTHERS"]:
         raise HTTPException(status_code=400, detail="Invalid chatbot type")
    
    success = database.delete_all_sessions(current_user["username"], chatbot_type)
    if not success:
         raise HTTPException(status_code=500, detail="Failed to delete sessions")
    return {"message": "All sessions deleted"}

@router.get("/chat/history/{session_id}")
async def get_history(session_id: str, current_user: dict = Depends(get_current_user)):
    # Verify ownership
    session = database.get_session_by_id(session_id)
    if not session or session["username"] != current_user["username"]:
        raise HTTPException(status_code=404, detail="Session not found")
        
    messages = database.load_chat_history(current_user["username"], "", session_id)
    return messages

@router.delete("/chat/history/{session_id}")
async def delete_history(session_id: str, current_user: dict = Depends(get_current_user)):
    # Verify ownership
    session = database.get_session_by_id(session_id)
    if not session or session["username"] != current_user["username"]:
         raise HTTPException(status_code=404, detail="Session not found")
         
    database.delete_session(current_user["username"], "", session_id)
    return {"message": "Session deleted"}

class SessionTitleUpdate(BaseModel):
    title: str

@router.patch("/chat/sessions/{session_id}/title")
async def update_session_title(session_id: str, update: SessionTitleUpdate, current_user: dict = Depends(get_current_user)):
    # Verify ownership
    session = database.get_session_by_id(session_id)
    if not session or session["username"] != current_user["username"]:
         raise HTTPException(status_code=404, detail="Session not found")
    
    database.update_session_title(session_id, update.title)
    return {"message": "Session title updated", "title": update.title}

# -----------------------------------------------------------------------------
# Bot Logic Integration
# -----------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: ChatMessage
    session_id: str

# -----------------------------------------------------------------------------
# Bot Logic Integration
# -----------------------------------------------------------------------------
from modules import sop_chatbot, insw_chatbot, others_chatbot

@router.post("/chat/sop")
async def chat_sop(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    # Verify session ownership
    session = database.get_session_by_id(request.session_id)
    if not session:
        # Auto-create if missing (optional, but good for UX)
        request.session_id = database.create_session(current_user["username"], "SOP", request.session_id)
    elif session["username"] != current_user["username"]:
         raise HTTPException(status_code=403, detail="Not authorized for this session")

    # Save User Message
    database.save_message(current_user["username"], "SOP", "user", request.message.content, request.session_id)
    
    # Generate Response with logging
    from fastapi.concurrency import run_in_threadpool
    import time
    
    start_time = time.time()
    try:
        response_text = await run_in_threadpool(sop_chatbot.search_sop_exim, request.message.content, request.session_id)
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log successful response to developer dashboard
        status = "answered" if response_text and not response_text.startswith("Error") else "unanswered"
        llm_logger.log_call(
            session_id=request.session_id,
            username=current_user["username"],
            chatbot_type="SOP",
            status=status,
            input_tokens=len(request.message.content.split()) * 2,  # Rough estimate
            output_tokens=len(response_text.split()) * 2 if response_text else 0,
            latency_ms=latency_ms,
            query=request.message.content[:200]
        )
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        response_text = f"Error processing request: {str(e)}"
        
        # Log error to developer dashboard
        llm_logger.log_call(
            session_id=request.session_id,
            username=current_user["username"],
            chatbot_type="SOP",
            status="error",
            latency_ms=latency_ms,
            error_message=str(e)[:500],
            query=request.message.content[:200]
        )

    # Save Assistant Message
    database.save_message(current_user["username"], "SOP", "assistant", response_text, request.session_id)
    
    # Auto-generate title if this is the first message (session has title "New Chat")
    if session and session.get("title") == "New Chat":
        try:
            from modules.chatbot_utils import generate_chat_title, init_gemini_client
            client = init_gemini_client()
            if client:
                title = await run_in_threadpool(generate_chat_title, client, request.message.content, response_text)
                if title:
                    database.update_session_title(request.session_id, title)
        except Exception as e:
            print(f"Error generating title: {e}")
    
    return {"role": "assistant", "content": response_text}

@router.post("/chat/insw")
async def chat_insw(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    # Verify session ownership
    session = database.get_session_by_id(request.session_id)
    if not session:
        request.session_id = database.create_session(current_user["username"], "INSW", request.session_id)
    elif session["username"] != current_user["username"]:
         raise HTTPException(status_code=403, detail="Not authorized for this session")

    # Save User Message
    database.save_message(current_user["username"], "INSW", "user", request.message.content, request.session_id)
    
    # Generate Response with logging
    import time
    start_time = time.time()
    
    try:
        response_text = await run_in_threadpool(insw_chatbot.search_insw_regulation, request.message.content)
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log successful response
        llm_logger.log_call(
            session_id=request.session_id,
            username=current_user["username"],
            chatbot_type="INSW",
            status="answered" if response_text else "unanswered",
            input_tokens=len(request.message.content.split()) * 2,
            output_tokens=len(response_text.split()) * 2 if response_text else 0,
            latency_ms=latency_ms,
            query=request.message.content[:200]
        )
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        response_text = f"Error processing request: {str(e)}"
        llm_logger.log_call(
            session_id=request.session_id,
            username=current_user["username"],
            chatbot_type="INSW",
            status="error",
            latency_ms=latency_ms,
            error_message=str(e)[:500],
            query=request.message.content[:200]
        )
        
    # Save Assistant Message
    database.save_message(current_user["username"], "INSW", "assistant", response_text, request.session_id)
    
    # Auto-generate title if this is the first message (session has title "New Chat")
    if session and session.get("title") == "New Chat":
        try:
            from modules.chatbot_utils import generate_chat_title, init_gemini_client
            client = init_gemini_client()
            if client:
                title = await run_in_threadpool(generate_chat_title, client, request.message.content, response_text)
                if title:
                    database.update_session_title(request.session_id, title)
        except Exception as e:
            print(f"Error generating title: {e}")
    
    return {"role": "assistant", "content": response_text}

@router.post("/chat/others")
async def chat_others(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    # Verify session ownership
    session = database.get_session_by_id(request.session_id)
    if not session:
        request.session_id = database.create_session(current_user["username"], "OTHERS", request.session_id)
    elif session["username"] != current_user["username"]:
         raise HTTPException(status_code=403, detail="Not authorized for this session")

    # Save User Message
    database.save_message(current_user["username"], "OTHERS", "user", request.message.content, request.session_id)
    
    from fastapi.concurrency import run_in_threadpool
    import time
    start_time = time.time()
    
    try:
        response_text = await run_in_threadpool(others_chatbot.search_others, request.message.content, request.session_id)
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log successful response
        llm_logger.log_call(
            session_id=request.session_id,
            username=current_user["username"],
            chatbot_type="OTHERS",
            status="answered" if response_text else "unanswered",
            input_tokens=len(request.message.content.split()) * 2,
            output_tokens=len(response_text.split()) * 2 if response_text else 0,
            latency_ms=latency_ms,
            query=request.message.content[:200]
        )
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        response_text = f"Error processing request: {str(e)}"
        llm_logger.log_call(
            session_id=request.session_id,
            username=current_user["username"],
            chatbot_type="OTHERS",
            status="error",
            latency_ms=latency_ms,
            error_message=str(e)[:500],
            query=request.message.content[:200]
        )
        
    # Save Assistant Message
    database.save_message(current_user["username"], "OTHERS", "assistant", response_text, request.session_id)
    
    # Auto-generate title
    if session and session.get("title") == "New Chat":
        try:
            from modules.chatbot_utils import generate_chat_title, init_gemini_client
            client = init_gemini_client()
            if client:
                title = await run_in_threadpool(generate_chat_title, client, request.message.content, response_text)
                if title:
                    database.update_session_title(request.session_id, title)
        except Exception as e:
            print(f"Error generating title: {e}")
    
    return {"role": "assistant", "content": response_text}

# -----------------------------------------------------------------------------
# Download Endpoint
# -----------------------------------------------------------------------------


@router.get("/download-link")
async def get_download_link(
    filename: str,
    chatbot_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Stream a file by filename. Requires authentication.
    Streams file from OneDrive and sets correct Content-Disposition header.
    """
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    # Get OneDrive download URL (this is a temporary pre-authenticated URL)
    download_url = chatbot_utils.get_onedrive_download_link(filename, chatbot_type)
    if not download_url:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    
    
    # Stream the file from OneDrive through our backend
    import httpx
    
    async def stream_file():
        async with httpx.AsyncClient(follow_redirects=True) as client:
            async with client.stream("GET", download_url) as response:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    yield chunk
    
    # Return with explicit headers that override any from OneDrive
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        stream_file(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        }
    )

# -----------------------------------------------------------------------------
# Developer Dashboard Endpoints (Admin Only)
# -----------------------------------------------------------------------------
from modules.llm_logger import llm_logger

@router.get("/dev/logs")
async def get_llm_logs(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    chatbot_type: Optional[str] = None,
    current_user: dict = Depends(get_current_admin_user)
):
    """Get paginated LLM logs for developer dashboard"""
    logs = llm_logger.get_logs(
        limit=limit,
        offset=offset,
        status_filter=status,
        chatbot_type_filter=chatbot_type
    )
    return {"logs": logs, "limit": limit, "offset": offset}

@router.get("/dev/stats")
async def get_llm_stats(current_user: dict = Depends(get_current_admin_user)):
    """Get aggregate LLM statistics for developer dashboard"""
    return llm_logger.get_stats()

# -----------------------------------------------------------------------------
# Ingestion Scheduler Admin Endpoints
# -----------------------------------------------------------------------------
from modules.scheduler import get_scheduler_status

@router.get("/admin/ingestion/logs")
async def get_ingestion_logs(
    limit: int = 50,
    offset: int = 0,
    pipeline: Optional[str] = None,
    current_user: dict = Depends(get_current_admin_user)
):
    """Get ingestion logs for admin dashboard"""
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT id, pipeline_name, status, started_at, completed_at, 
                   files_processed, files_upserted, files_skipped, errors, summary
            FROM ingestion_logs
        '''
        params = []
        
        if pipeline:
            query += ' WHERE pipeline_name = ?'
            params.append(pipeline)
        
        query += ' ORDER BY id DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        logs = []
        for row in rows:
            logs.append({
                'id': row[0],
                'pipeline_name': row[1],
                'status': row[2],
                'started_at': row[3],
                'completed_at': row[4],
                'files_processed': row[5],
                'files_upserted': row[6],
                'files_skipped': row[7],
                'errors': row[8],
                'summary': row[9]
            })
        
        return {'logs': logs, 'limit': limit, 'offset': offset}
    except Exception as e:
        return {'logs': [], 'error': str(e)}

@router.get("/admin/ingestion/status")
async def get_ingestion_status(current_user: dict = Depends(get_current_admin_user)):
    """Get current scheduler status for admin dashboard"""
    return get_scheduler_status()

@router.post("/admin/ingestion/run/{pipeline}")
async def trigger_ingestion(
    pipeline: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """Manually trigger an ingestion pipeline (admin only)"""
    from modules.scheduler import (
        run_sop_ingestion, run_insw_ingestion, 
        run_cases_ingestion, run_general_ingestion
    )
    import asyncio
    
    pipeline_map = {
        'sop': run_sop_ingestion,
        'insw': run_insw_ingestion,
        'cases': run_cases_ingestion,
        'general': run_general_ingestion
    }
    
    if pipeline.lower() not in pipeline_map:
        raise HTTPException(status_code=400, detail=f"Invalid pipeline: {pipeline}")
    
    # Run async in background
    asyncio.create_task(pipeline_map[pipeline.lower()]())
    
    return {'message': f'{pipeline} ingestion triggered', 'status': 'started'}
