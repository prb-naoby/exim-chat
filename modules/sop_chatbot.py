import streamlit as st
from modules import database
from datetime import datetime
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import Prefetch, FusionQuery

load_dotenv()

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
    """
    Dummy helper function to generate session title from first user message
    In production, this would use LLM to generate a concise topic/title
    """
    # Simple dummy: just use first few words or truncate
    words = user_message.split()
    if len(words) <= 5:
        return user_message
    else:
        return " ".join(words[:5]) + "..."

def _create_embedding(text: str) -> List[float]:
    """Create embedding using Gemini"""
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    embedding_model = os.getenv('EMBEDDING_MODEL', 'models/gemini-embedding-001')
    
    client = genai.Client(api_key=gemini_api_key)
    result = client.models.embed_content(
        model=embedding_model,
        contents=text
    )
    return result.embeddings[0].values


def _create_sparse_vector(text: str) -> Dict[str, List]:
    """Create simple BM25-like sparse vector"""
    words = text.lower().split()
    word_freq = {}
    
    for word in words:
        if len(word) > 2:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    indices = []
    values = []
    
    for word, freq in word_freq.items():
        index = hash(word) % (2**32)
        indices.append(index)
        values.append(float(freq))
    
    return {
        "indices": indices,
        "values": values
    }


def _search_sop_collection(query_vector: List[float], query_text: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Search SOP documents collection with hybrid search"""
    qdrant_url = os.getenv('SOP_QDRANT_URL')
    qdrant_api_key = os.getenv('SOP_QDRANT_API_KEY')
    collection_name = os.getenv('SOP_QDRANT_COLLECTION_NAME', 'sop_documents')
    
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    sparse_vector = _create_sparse_vector(query_text)
    
    results = client.query_points(
        collection_name=collection_name,
        prefetch=[
            Prefetch(query=query_vector, using="dense", limit=limit * 2),
            Prefetch(query=sparse_vector, using="bm25", limit=limit * 2)
        ],
        query=FusionQuery(fusion="rrf"),
        limit=limit
    )
    
    formatted_results = []
    for point in results.points:
        formatted_results.append({
            'sop_title': point.payload.get('sop_title', ''),
            'type': point.payload.get('type', ''),
            'tujuan': point.payload.get('tujuan', ''),
            'uraian': point.payload.get('uraian', ''),
            'dokumen': point.payload.get('dokumen', ''),
            'date': point.payload.get('date', ''),
            'doc_no': point.payload.get('doc_no', ''),
            'rev': point.payload.get('rev', ''),
            'webUrl': point.payload.get('webUrl', ''),
            'score': point.score
        })
    
    return formatted_results


def _search_cases_collection(query_vector: List[float], query_text: str, limit: int = 2) -> List[Dict[str, Any]]:
    """Search cases Q&A collection with hybrid search"""
    qdrant_url = os.getenv('CASES_QDRANT_URL')
    qdrant_api_key = os.getenv('CASES_QDRANT_API_KEY')
    collection_name = os.getenv('CASES_QDRANT_COLLECTION_NAME', 'cases_qna')
    
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    sparse_vector = _create_sparse_vector(query_text)
    
    try:
        results = client.query_points(
            collection_name=collection_name,
            prefetch=[
                Prefetch(query=query_vector, using="dense", limit=limit * 2),
                Prefetch(query=sparse_vector, using="bm25", limit=limit * 2)
            ],
            query=FusionQuery(fusion="rrf"),
            limit=limit
        )
        
        formatted_results = []
        for point in results.points:
            formatted_results.append({
                'case_no': point.payload.get('case_no', ''),
                'date': point.payload.get('date', ''),
                'question': point.payload.get('question', ''),
                'answer': point.payload.get('answer', ''),
                'score': point.score
            })
        
        return formatted_results
    except Exception as e:
        print(f"Error searching cases collection: {str(e)}")
        return []


def _build_context(sop_results: List[Dict], case_results: List[Dict]) -> str:
    """Build context string from search results"""
    context_parts = []
    
    # Add SOPs context
    if sop_results:
        context_parts.append("=== Dokumen SOP/IK yang Relevan ===\n")
        for idx, sop in enumerate(sop_results, 1):
            # Truncate long uraian
            uraian = sop.get('uraian', '')
            if len(uraian) > 500:
                uraian = uraian[:500] + "..."
            
            sop_text = f"{idx}. {sop.get('sop_title', 'N/A')} [Type: {sop.get('type', 'N/A')}]\n"
            sop_text += f"   Doc No: {sop.get('doc_no', 'N/A')} | Rev: {sop.get('rev', 'N/A')} | Date: {sop.get('date', 'N/A')}\n"
            
            if sop.get('tujuan'):
                sop_text += f"   Tujuan: {sop.get('tujuan')}\n"
            if uraian:
                sop_text += f"   Uraian: {uraian}\n"
            if sop.get('dokumen'):
                sop_text += f"   Dokumen: {sop.get('dokumen')}\n"
            if sop.get('webUrl'):
                sop_text += f"   Link Dokumen: {sop.get('webUrl')}\n"
            
            context_parts.append(sop_text)
    
    # Add cases context
    if case_results:
        context_parts.append("\n=== Kasus Historis yang Relevan ===\n")
        for idx, case in enumerate(case_results, 1):
            case_text = f"{idx}. Case #{case.get('case_no', 'N/A')} ({case.get('date', 'N/A')})\n"
            case_text += f"   Q: {case.get('question', '')}\n"
            case_text += f"   A: {case.get('answer', '')}\n"
            context_parts.append(case_text)
    
    if not context_parts:
        return "Tidak ada dokumen atau kasus yang relevan ditemukan."
    
    return "\n".join(context_parts)


def _generate_llm_response(user_query: str, context: str) -> str:
    """Generate response using Gemini LLM"""
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    llm_model = os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    
    client = genai.Client(api_key=gemini_api_key)
    
    system_prompt = """Anda adalah Asisten SOP EXIM untuk operasi ekspor-impor.

Peran Anda:
- Memberikan prosedur SOP yang akurat dari dokumen resmi
- Mereferensikan kasus historis jika relevan
- Mengutip nomor dokumen dan nama dokumen
- SELALU sertakan link dokumen dari webUrl untuk setiap SOP yang direferensikan
- Menggunakan penjelasan yang jelas dan bertahap dalam Bahasa Indonesia
- Jika tidak yakin, nyatakan dengan jelas dan berikan hasil yang paling mendekati

Format Jawaban:
1. Jawaban Ringkas: Berikan ringkasan singkat dan informatif tentang proses (mencakup pihak yang terlibat, tujuan utama, output yang dihasilkan)
2. Prosedur langkah demi langkah jika berlaku
3. Daftar Dokumen yang Dibutuhkan (HANYA ambil dari field "Dokumen" yang tersedia di konteks, jangan buat daftar sendiri. Perbaiki kapitalisasi dengan benar: huruf besar untuk awal kata penting, bukan semua huruf besar)
4. Referensi ke kasus historis (jika relevan)
5. Sitasi dokumen menggunakan format dengan hyperlink: [TYPE DOC_NO SOP_TITLE](webUrl)
   Contoh: [SOP 17.1 Pemasukan Tooling](https://url-link)
   Format hyperlink Markdown yang benar: [Teks yang ditampilkan](URL lengkap)
   Perbaiki kapitalisasi judul: huruf besar untuk awal kata penting, bukan semua huruf besar

Jika ada lebih dari satu dokumen SOP yang relevan:
- Analisis kombinasi informasi dari semua dokumen
- Hindari pengulangan informasi yang sama
- Gabungkan prosedur yang saling melengkapi
- Jelaskan hubungan atau perbedaan antar dokumen jika ada
- Prioritaskan informasi yang paling relevan dengan pertanyaan

Penting:
- Selalu gunakan informasi dari konteks yang diberikan
- Jangan membuat informasi yang tidak ada di konteks
- Untuk daftar dokumen: HANYA gunakan informasi dari field "Dokumen" di konteks SOP
- WAJIB gunakan format hyperlink Markdown [teks](url) untuk semua sitasi dokumen
- Perbaiki kapitalisasi untuk keterbacaan yang lebih baik (title case, bukan UPPERCASE)
- Jika informasi tidak tersedia, katakan "Informasi tidak tersedia dalam dokumen"
"""
    
    user_message = f"""Konteks:
{context}

Pertanyaan Pengguna: {user_query}

Berikan jawaban yang komprehensif berdasarkan konteks di atas."""
    
    try:
        response = client.models.generate_content(
            model=llm_model,
            contents=[
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "model", "parts": [{"text": "Saya mengerti. Saya akan menjawab pertanyaan berdasarkan dokumen SOP/IK dan kasus historis yang relevan, dengan selalu mengutip sumber."}]},
                {"role": "user", "parts": [{"text": user_message}]}
            ]
        )
        return response.text
    except Exception as e:
        return f"Error generating response: {str(e)}"


def search_sop_exim(user_input: str) -> str:
    """
    Main function for SOP Chatbot with RAG pipeline:
    1. Create embedding from user query
    2. Search both SOP and Cases collections
    3. Build context from search results
    4. Generate response with Gemini LLM
    """
    try:
        # 1. Create embedding
        query_vector = _create_embedding(user_input)
        
        # 2. Search both collections
        sop_results = _search_sop_collection(query_vector, user_input, limit=3)
        case_results = _search_cases_collection(query_vector, user_input, limit=2)
        
        # 3. Build context
        context = _build_context(sop_results, case_results)
        
        # 4. Generate response with LLM
        response = _generate_llm_response(user_input, context)
        
        return response
        
    except Exception as e:
        return f"❌ Error: {str(e)}\n\nSilakan coba lagi atau hubungi administrator."

def show():
    """Display SOP Chatbot page"""
    # Initialize chat history for SOP chatbot if not exists
    if "messages_sop" not in st.session_state:
        st.session_state.messages_sop = []
    
    # Initialize edit state
    if "edit_message_index" not in st.session_state:
        st.session_state.edit_message_index = None
    
    # Display chat history with timestamps and action buttons
    for idx, message in enumerate(st.session_state.messages_sop):
        with st.chat_message(message["role"]):
            # Display timestamp if available (smaller size)
            if "timestamp" in message:
                st.markdown(f"<span style='font-size: 0.75rem; opacity: 0.7;'>🕐 {message['timestamp']}</span>", unsafe_allow_html=True)
            
            # Show edit input if this message is being edited
            if message["role"] == "user" and st.session_state.edit_message_index == idx:
                edited_text = st.text_area(
                    "Edit your message:",
                    value=message["content"],
                    key=f"edit_input_{idx}",
                    height=100
                )
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("💾 Save", key=f"save_edit_{idx}", use_container_width=True):
                        # Update message
                        st.session_state.messages_sop[idx]["content"] = edited_text
                        st.session_state.messages_sop[idx]["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Remove all messages after this one
                        st.session_state.messages_sop = st.session_state.messages_sop[:idx+1]
                        
                        # Regenerate response
                        response = search_sop_exim(edited_text)
                        assistant_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        st.session_state.messages_sop.append({
                            "role": "assistant",
                            "content": response,
                            "timestamp": assistant_timestamp
                        })
                        
                        # Save to database
                        database.save_message(
                            "guest",
                            "SOP",
                            "user",
                            edited_text,
                            st.session_state.current_session_id,
                            st.session_state.messages_sop[idx]["timestamp"]
                        )
                        database.save_message(
                            "guest",
                            "SOP",
                            "assistant",
                            response,
                            st.session_state.current_session_id,
                            assistant_timestamp
                        )
                        
                        st.session_state.edit_message_index = None
                        st.rerun()
                
                with col2:
                    if st.button("✖️ Cancel", key=f"cancel_edit_{idx}", use_container_width=True):
                        st.session_state.edit_message_index = None
                        st.rerun()
            else:
                # Display message content
                st.markdown(message["content"])
                
                # Show action buttons for user messages (ChatGPT-like minimal buttons)
                if message["role"] == "user":
                    col1, col2, col3 = st.columns([10, 0.5, 0.5])
                    with col2:
                        st.markdown('<div class="action-btn-container">', unsafe_allow_html=True)
                        if st.button("✏️", key=f"edit_{idx}", help="Edit message"):
                            st.session_state.edit_message_index = idx
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with col3:
                        st.markdown('<div class="action-btn-container">', unsafe_allow_html=True)
                        if st.button("🔄", key=f"regen_{idx}", help="Regenerate response"):
                            # Remove all messages after this one
                            st.session_state.messages_sop = st.session_state.messages_sop[:idx+1]
                            
                            # Regenerate response
                            response = search_sop_exim(message["content"])
                            assistant_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            st.session_state.messages_sop.append({
                                "role": "assistant",
                                "content": response,
                                "timestamp": assistant_timestamp
                            })
                            
                            # Save to database
                            database.save_message(
                                "guest",
                                "SOP",
                                "assistant",
                                response,
                                st.session_state.current_session_id,
                                assistant_timestamp
                            )
                            
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
    
    # Chat input
    if prompt := st.chat_input("Ask about EXIM SOPs... (e.g., 'document approval process')"):
        # Capture current datetime
        user_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add user message to chat history with timestamp
        st.session_state.messages_sop.append({"role": "user", "content": prompt, "timestamp": user_timestamp})
        
        # Check if this is the first user message in this session
        is_first_message = len([msg for msg in st.session_state.messages_sop if msg["role"] == "user"]) == 1
        
        # Save to database with timestamp
        database.save_message(
            "guest", 
            "SOP", 
            "user", 
            prompt,
            st.session_state.current_session_id,
            user_timestamp
        )
        
        # If first message, update session title
        if is_first_message:
            database.update_session_title(
                "guest",
                "SOP",
                st.session_state.current_session_id
            )
        
        with st.chat_message("user"):
            st.markdown(f"<span style='font-size: 0.75rem; opacity: 0.7;'>🕐 {user_timestamp}</span>", unsafe_allow_html=True)
            st.markdown(prompt)
        
        # Generate response using helper function
        response = search_sop_exim(prompt)
        
        # Capture response datetime
        assistant_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add assistant response to chat history with timestamp
        st.session_state.messages_sop.append({"role": "assistant", "content": response, "timestamp": assistant_timestamp})
        
        # Save to database with timestamp
        database.save_message(
            "guest", 
            "SOP", 
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
    #     if st.button("🗑️ Clear", key="clear_sop", use_container_width=True):
    #         database.clear_chat_history(st.session_state.username, "SOP", st.session_state.current_session_id)
    #         st.session_state.messages_sop = []
    #         st.rerun()
