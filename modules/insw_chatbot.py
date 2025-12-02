import streamlit as st
from modules import database
from datetime import datetime
from dotenv import load_dotenv
import os
from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import Prefetch, FusionQuery
from ingestion.insw.insw_qdrant_store import INSWQdrantStore

load_dotenv()

# Initialize Qdrant client for INSW with correct env vars
qdrant_url = os.getenv("INSW_QDRANT_URL", "http://localhost:6333")
qdrant_api_key = os.getenv("INSW_QDRANT_API_KEY", "")
insw_collection_name = os.getenv("INSW_QDRANT_COLLECTION_NAME", "insw_regulations_hybrid")
insw_store = INSWQdrantStore(qdrant_url, qdrant_api_key, insw_collection_name)

# Initialize Gemini client
gemini_api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=gemini_api_key)

# CSS for compact action buttons
st.markdown("""
    <style>
        .action-btn-container {
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .action-btn-container button {
            padding: 0.2rem 0.35rem !important;
            height: 1.6rem !important;
            min-height: 1.6rem !important;
            width: auto !important;
            font-size: 0.95rem !important;
            line-height: 1 !important;
        }
    </style>
""", unsafe_allow_html=True)

def generate_session_title(user_message):
    """Generate session title from first user message"""
    words = user_message.split()
    if len(words) <= 5:
        return user_message
    else:
        return " ".join(words[:5]) + "..."


def _create_embedding(text: str):
    """Create dense embedding using Gemini"""
    try:
        response = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text
        )
        return response['embedding']
    except Exception as e:
        print(f"Error creating embedding: {e}")
        return [0.0] * 3072


def _create_sparse_vector(text: str):
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


def _build_insw_context(results: list) -> str:
    """
    Build context string from INSW search results
    Handles the actual INSW payload structure
    """
    if not results:
        return "Tidak ada data INSW yang relevan ditemukan."
    
    context_parts = ["=== Data INSW yang Relevan ===\n"]
    
    for idx, result in enumerate(results, 1):
        payload = result.get("payload", {})
        
        hs_code = payload.get("hs_code", "N/A")
        deskripsi = payload.get("deskripsi", "")
        uraian_barang = payload.get("uraian_barang", "")
        search_text = payload.get("search_text", "")
        link = payload.get("link", "")
        
        # Regulation info
        has_import = payload.get("has_import_regulations", False)
        has_export = payload.get("has_export_regulations", False)
        has_border = payload.get("has_import_border_regulations", False)
        has_post_border = payload.get("has_post_border_regulations", False)
        regulation_count = payload.get("regulation_count", 0)
        
        # BC Documents
        bc_types = payload.get("bc_document_types", [])
        
        # Build context for this result
        item = f"{idx}. HS Code: {hs_code}\n"
        if deskripsi:
            item += f"   Deskripsi: {deskripsi}\n"
        if uraian_barang:
            item += f"   Uraian Barang: {uraian_barang}\n"
        
        # Regulation summary
        reg_flags = []
        if has_import:
            reg_flags.append("Import")
        if has_export:
            reg_flags.append("Export")
        if has_border:
            reg_flags.append("Border")
        if has_post_border:
            reg_flags.append("Post-Border")
        
        if reg_flags:
            item += f"   Regulasi: {', '.join(reg_flags)} ({regulation_count} ketentuan)\n"
        
        if bc_types:
            item += f"   Dokumen BC: {', '.join(bc_types)}\n"
        
        if link:
            item += f"   Link: {link}\n"
        
        # Try to get full_document for detailed regulations
        full_doc = payload.get("full_document", "")
        if full_doc and isinstance(full_doc, str):
            try:
                import json
                doc_data = json.loads(full_doc)
                regulations = doc_data.get("regulations", {})
                
                # Import regulations
                import_regs = regulations.get("import_regulation", [])
                if import_regs:
                    item += "   Ketentuan Import:\n"
                    for reg in import_regs[:2]:  # Limit to 2
                        item += f"      - {reg.get('name', '')}\n"
                        if reg.get('legal'):
                            item += f"        Legal: {reg.get('legal')}\n"
                
                # Export regulations
                export_regs = regulations.get("export_regulation", [])
                if export_regs:
                    item += "   Ketentuan Export:\n"
                    for reg in export_regs[:2]:  # Limit to 2
                        item += f"      - {reg.get('name', '')}\n"
                        if reg.get('legal'):
                            item += f"        Legal: {reg.get('legal')}\n"
            except:
                pass
        
        context_parts.append(item)
    
    return "\n".join(context_parts)


def search_insw_regulation(user_input):
    """
    Search INSW regulations using hybrid search (dense + sparse)
    """
    try:
        # Create embeddings for query
        query_embedding = _create_embedding(user_input)
        
        # Search in Qdrant with hybrid search
        results = insw_store.search_hybrid(user_input, query_embedding, limit=5)
        
        if not results:
            return "Tidak ditemukan data INSW yang relevan. Silakan coba kata kunci lain."
        
        # Build context from search results
        context = _build_insw_context(results)
        
        # Generate LLM response with Indonesian system prompt
        system_prompt = """Anda adalah Asisten INSW (Indonesia National Single Window) untuk regulasi ekspor-impor.

Peran Anda:
- Memberikan informasi akurat tentang HS Code, regulasi import/export, dan dokumen kepabeanan
- Menjelaskan ketentuan larangan/pembatasan (Lartas) yang berlaku
- Mengutip dasar hukum/peraturan yang relevan
- Menggunakan Bahasa Indonesia yang profesional

Format Jawaban:
1. **Ringkasan**: Jawaban singkat tentang HS Code dan status regulasinya
2. **Detail Regulasi**: Ketentuan import/export yang berlaku (jika ada)
3. **Dokumen yang Diperlukan**: Dokumen BC dan perizinan yang dibutuhkan
4. **Dasar Hukum**: Peraturan yang menjadi dasar ketentuan
5. **Link Referensi**: Sertakan link INSW jika tersedia

Penting:
- Selalu sebutkan HS Code lengkap (8 digit)
- Jelaskan apakah ada larangan atau pembatasan
- Jika ada beberapa HS Code relevan, bandingkan perbedaannya
- Jika informasi tidak tersedia, nyatakan dengan jelas"""
        
        user_message = f"""Konteks:
{context}

Pertanyaan: {user_input}

Berikan jawaban yang komprehensif berdasarkan konteks di atas."""
        
        client = genai.Client(api_key=gemini_api_key)
        response = client.models.generate_content(
            model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            contents=[
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "model", "parts": [{"text": "Saya mengerti. Saya akan menjawab pertanyaan tentang regulasi INSW dengan mengutip HS Code, ketentuan import/export, dan dasar hukum yang relevan."}]},
                {"role": "user", "parts": [{"text": user_message}]}
            ]
        )
        
        return response.text
    
    except Exception as e:
        print(f"Error searching INSW regulations: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)}\n\nSilakan coba lagi atau hubungi administrator."

def show():
    """Display INSW Chatbot page"""
    # Initialize chat history for INSW chatbot if not exists
    if "messages_insw" not in st.session_state:
        st.session_state.messages_insw = []
    
    # Initialize edit state
    if "edit_message_index_insw" not in st.session_state:
        st.session_state.edit_message_index_insw = None
    
    # Display chat history with timestamps and action buttons
    for idx, message in enumerate(st.session_state.messages_insw):
        with st.chat_message(message["role"]):
            # Display timestamp if available (smaller size)
            if "timestamp" in message:
                st.markdown(f"<span style='font-size: 0.75rem; opacity: 0.7;'>🕐 {message['timestamp']}</span>", unsafe_allow_html=True)
            
            # Show edit input if this message is being edited
            if message["role"] == "user" and st.session_state.edit_message_index_insw == idx:
                edited_text = st.text_area(
                    "Edit your message:",
                    value=message["content"],
                    key=f"edit_input_insw_{idx}",
                    height=100
                )
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("💾 Save", key=f"save_edit_insw_{idx}", use_container_width=True):
                        # Update message
                        st.session_state.messages_insw[idx]["content"] = edited_text
                        st.session_state.messages_insw[idx]["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Remove all messages after this one
                        st.session_state.messages_insw = st.session_state.messages_insw[:idx+1]
                        
                        # Regenerate response
                        response = search_insw_regulation(edited_text)
                        assistant_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        st.session_state.messages_insw.append({
                            "role": "assistant",
                            "content": response,
                            "timestamp": assistant_timestamp
                        })
                        
                        # Save to database
                        database.save_message(
                            "guest",
                            "INSW",
                            "user",
                            edited_text,
                            st.session_state.current_session_id,
                            st.session_state.messages_insw[idx]["timestamp"]
                        )
                        database.save_message(
                            "guest",
                            "INSW",
                            "assistant",
                            response,
                            st.session_state.current_session_id,
                            assistant_timestamp
                        )
                        
                        st.session_state.edit_message_index_insw = None
                        st.rerun()
                
                with col2:
                    if st.button("✖️ Cancel", key=f"cancel_edit_insw_{idx}", use_container_width=True):
                        st.session_state.edit_message_index_insw = None
                        st.rerun()
            else:
                # Display message content
                st.markdown(message["content"])
                
                # Show action buttons for user messages (ChatGPT-like minimal buttons)
                if message["role"] == "user":
                    col1, col2, col3 = st.columns([10, 0.5, 0.5])
                    with col2:
                        st.markdown('<div class="action-btn-container">', unsafe_allow_html=True)
                        if st.button("✏️", key=f"edit_insw_{idx}", help="Edit message"):
                            st.session_state.edit_message_index_insw = idx
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with col3:
                        st.markdown('<div class="action-btn-container">', unsafe_allow_html=True)
                        if st.button("🔄", key=f"regen_insw_{idx}", help="Regenerate response"):
                            # Remove all messages after this one
                            st.session_state.messages_insw = st.session_state.messages_insw[:idx+1]
                            
                            # Regenerate response
                            response = search_insw_regulation(message["content"])
                            assistant_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            st.session_state.messages_insw.append({
                                "role": "assistant",
                                "content": response,
                                "timestamp": assistant_timestamp
                            })
                            
                            # Save to database
                            database.save_message(
                                "guest",
                                "INSW",
                                "assistant",
                                response,
                                st.session_state.current_session_id,
                                assistant_timestamp
                            )
                            
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
    
    # Chat input
    if prompt := st.chat_input("Search for INSW regulations... (e.g., 'export permit requirements')"):
        # Capture current datetime
        user_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add user message to chat history with timestamp
        st.session_state.messages_insw.append({"role": "user", "content": prompt, "timestamp": user_timestamp})
        
        # Check if this is the first user message in this session
        is_first_message = len([msg for msg in st.session_state.messages_insw if msg["role"] == "user"]) == 1
        
        # Save to database with timestamp
        database.save_message(
            "guest", 
            "INSW", 
            "user", 
            prompt,
            st.session_state.current_session_id,
            user_timestamp
        )
        
        # If first message, update session title
        if is_first_message:
            database.update_session_title(
                "guest",
                "INSW",
                st.session_state.current_session_id
            )
        
        with st.chat_message("user"):
            st.markdown(f"<span style='font-size: 0.75rem; opacity: 0.7;'>🕐 {user_timestamp}</span>", unsafe_allow_html=True)
            st.markdown(prompt)
        
        # Generate response using helper function
        response = search_insw_regulation(prompt)
        
        # Capture response datetime
        assistant_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add assistant response to chat history with timestamp
        st.session_state.messages_insw.append({"role": "assistant", "content": response, "timestamp": assistant_timestamp})
        
        # Save to database with timestamp
        database.save_message(
            "guest", 
            "INSW", 
            "assistant", 
            response,
            st.session_state.current_session_id,
            assistant_timestamp
        )
        
        with st.chat_message("assistant"):
            st.markdown(f"<span style='font-size: 0.75rem; opacity: 0.7;'>🕐 {assistant_timestamp}</span>", unsafe_allow_html=True)
            st.markdown(response)
    
    # Clear chat button in the corner (hidden, functionality moved to sidebar)
    # col1, col2 = st.columns([6, 1])
    # with col2:
    #     if st.button("🗑️ Clear", key="clear_insw", use_container_width=True):
    #         database.clear_chat_history(st.session_state.username, "INSW", st.session_state.current_session_id)
    #         st.session_state.messages_insw = []
    #         st.rerun()
