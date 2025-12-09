import streamlit as st
from modules import database, chatbot_utils, app_logger
from datetime import datetime
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Prefetch, FusionQuery

load_dotenv()

# Initialize Gemini Client
client = chatbot_utils.init_gemini_client()

# Setup loggers
logger = app_logger.setup_logger()
llm_logger = app_logger.setup_llm_logger()

# Initialize Qdrant Client (Global/Cached)
@st.cache_resource
def get_qdrant_client():
    url = os.getenv('SOP_QDRANT_URL')
    api_key = os.getenv('SOP_QDRANT_API_KEY')
    return QdrantClient(url=url, api_key=api_key)

def _search_sop_collection(query_vector: List[float], query_text: str, limit: int = 3, session_id: str = None) -> List[Dict[str, Any]]:
    """Search SOP documents collection with hybrid search"""
    collection_name = os.getenv('SOP_QDRANT_COLLECTION_NAME', 'sop_documents')
    
    qdrant_client = get_qdrant_client()
    sparse_vector = chatbot_utils.create_sparse_vector(query_text)
    
    results = qdrant_client.query_points(
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
        # Use local trigger link for on-demand generation
        filename = point.payload.get('filename', '')
        
        # Fallback to webUrl if filename is missing
        web_url = point.payload.get('webUrl', '')
        
        if filename:
            # Create a secure local trigger link
            # Use passed session_id (from background thread) or fallback to session_state (if foreground)
            target_sid = session_id or st.session_state.get('current_session_id')
            
            if target_sid:
                token = chatbot_utils.generate_secure_token(filename, target_sid)
                if token:
                    web_url = f"/?token={token}"
                else:
                    web_url = "#error-generating-token"
            else:
                 # Fallback if session ID missing
                 logger.warning(f"Session ID missing during link generation for {filename}. Falling back to legacy link.")
                 import urllib.parse
                 safe_filename = urllib.parse.quote(filename)
                 web_url = f"/?download_file={safe_filename}"

        formatted_results.append({
            'sop_title': point.payload.get('sop_title', ''),
            'type': point.payload.get('type', ''),
            'tujuan': point.payload.get('tujuan', ''),
            'uraian': point.payload.get('uraian', ''),
            'dokumen': point.payload.get('dokumen', ''),
            'date': point.payload.get('date', ''),
            'doc_no': point.payload.get('doc_no', ''),
            'rev': point.payload.get('rev', ''),
            'webUrl': web_url,
            'score': point.score
        })
    
    return formatted_results





def _search_cases_collection(query_vector: List[float], query_text: str, limit: int = 2) -> List[Dict[str, Any]]:
    """Search cases Q&A collection with hybrid search"""
    collection_name = os.getenv('CASES_QDRANT_COLLECTION_NAME', 'cases_qna')
    
    qdrant_client = get_qdrant_client()
    sparse_vector = chatbot_utils.create_sparse_vector(query_text)
    
    try:
        results = qdrant_client.query_points(
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
        logger.error(f"Error searching cases collection: {str(e)}")
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
    llm_model = os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    
    system_prompt = """Anda adalah Asisten SOP EXIM untuk operasi ekspor-impor.

Peran Anda:
- Memberikan prosedur SOP yang akurat dari dokumen resmi
- Mereferensikan kasus historis jika relevan
- Mengutip nomor dokumen dan nama dokumen
- SELALU sertakan link dokumen dari webUrl untuk setiap SOP yang direferensikan
- Menggunakan penjelasan yang jelas dan bertahap dalam Bahasa Indonesia
- Jika tidak yakin, nyatakan dengan jelas dan berikan hasil yang paling mendekati

Format Jawaban:
1. Jawaban Ringkas: Berikan ringkasan singkat dan informatif (mencakup pihak, tujuan, output)
2. Prosedur langkah demi langkah jika berlaku
3. Daftar Dokumen yang Dibutuhkan (HANYA dari field "Dokumen" di konteks)
4. Tanda Sitasi: Gunakan angka dalam kurung siku `[1]`, `[2]` di akhir kalimat yang relevan. JANGAN gunakan hyperlink di dalam paragraf teks.

Aturan Penting:
- Sitasi dalam teks: Gunakan angka dalam kurung siku `[1]`, `[2]` di akhir kalimat.
- FORMAT Referensi (Wajib di bagian paling bawah):
  Buat daftar vertikal (satu baris per sumber).
  Gunakan format Markdown Link yang valid.
  
  Referensi Dokumen:
  1. [Judul Dokumen 1](URL_Lengkap_1)
  2. [Judul Dokumen 2](URL_Lengkap_2)

- Kasus Historis (Case): Gunakan sebagai info tambahan tapi JANGAN pernah membuat sitasi atau link ke Case. JANGAN masukkan Case ke daftar Referensi.
- Jika tidak ada URL untuk dokumen tersebut, jangan buat link, cukup tulis judulnya.
- Kapitalisasi: Gunakan Title Case untuk nama dokumen.

Penting:
- HANYA gunakan informasi dari konteks.
- JANGAN buat informasi palsu.
- WAJIB gunakan format sitasi `[n]` di teks.
- WAJIB gunakan format Markdown link `[tampil](url)` di daftar referensi. JANGAN menulis URL telanjang.
- JANGAN pernah memberi link ke "Kasus Historis" / "Case Data".
"""
    
    user_message = f"""Konteks:
{context}

Pertanyaan Pengguna: {user_query}

Berikan jawaban yang komprehensif berdasarkan konteks di atas."""
    
    try:
        start_time = datetime.now()
        response = client.models.generate_content(
            model=llm_model,
            contents=[
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "model", "parts": [{"text": "Saya mengerti. Saya akan menjawab pertanyaan berdasarkan dokumen SOP/IK dan kasus historis yang relevan, dengan selalu mengutip sumber."}]},
                {"role": "user", "parts": [{"text": user_message}]}
            ]
        )
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Log LLM analytics
        llm_logger.info("SOP LLM Call", extra={
            "query": user_query,
            "duration": duration,
            "model": llm_model,
            "input_chars": len(system_prompt) + len(user_message),
            "output_chars": len(response.text)
        })
        
        return response.text
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        return f"Error generating response: {str(e)}"


def _check_intent(user_input: str) -> dict:
    """
    Check if user query is related to SOP/EXIM procedures using LLM.
    Returns: {"is_relevant": bool, "reason": str, "confidence": str}
    """
    llm_model = os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    
    prompt = f"""Analisis apakah pertanyaan berikut terkait dengan Standard Operating Procedure (SOP) untuk ekspor-impor atau proses bisnis EXIM.

Pertanyaan: "{user_input}"

Kriteria SOP/EXIM:
- Prosedur, proses, atau langkah-langkah operasional
- Dokumen kepabeanan (BC 2.3, BC 2.5, dll)
- Regulasi ekspor/impor
- Kasus bisnis atau operasional perusahaan
- Pertanyaan tentang "bagaimana", "apa prosedur", "dokumen apa"

BUKAN SOP/EXIM:
- Pertanyaan umum tidak terkait bisnis (cuaca, resep, hiburan)
- Topik di luar ekspor-impor dan operasional bisnis

Berikan jawaban dalam format JSON:
{{
  "is_relevant": true/false,
  "reason": "penjelasan singkat",
  "confidence": "high/medium/low"
}}

Hanya output JSON, tanpa teks tambahan."""

    try:
        start_time = datetime.now()
        response = client.models.generate_content(
            model=llm_model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Log LLM analytics
        llm_logger.info("SOP Intent Check", extra={
            "query": user_input,
            "duration": duration,
            "model": llm_model
        })
        
        # Parse JSON response
        import json
        result_text = response.text.strip()
        # Remove markdown code blocks if present
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        
        result = json.loads(result_text.strip())
        return result
    except Exception as e:
        logger.error(f"Error in intent check: {e}", exc_info=True)
        print(f"Error in intent check: {e}")
        # Default to allowing query if check fails
        return {"is_relevant": True, "reason": "Error in classification", "confidence": "low"}


def _judge_document_relevance(user_input: str, context: str) -> dict:
    """
    Judge if retrieved documents are relevant to answer the user query.
    Returns: {"is_relevant": bool, "reason": str}
    """
    llm_model = os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    
    prompt = f"""Evaluasi apakah dokumen yang ditemukan relevan untuk menjawab pertanyaan pengguna.

Pertanyaan: "{user_input}"

Dokumen yang ditemukan:
{context}

Kriteria Relevan:
- Dokumen berisi informasi yang dapat menjawab pertanyaan
- Ada prosedur, aturan, atau kasus yang sesuai dengan pertanyaan
- Informasi cukup spesifik dan tidak terlalu umum

Berikan jawaban dalam format JSON:
{{
  "is_relevant": true/false,
  "reason": "penjelasan singkat mengapa relevan/tidak"
}}

Hanya output JSON, tanpa teks tambahan."""

    try:
        start_time = datetime.now()
        response = client.models.generate_content(
            model=llm_model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Log LLM analytics
        llm_logger.info("SOP Relevance Check", extra={
            "query": user_input,
            "duration": duration,
            "model": llm_model
        })
        
        # Parse JSON response
        import json
        result_text = response.text.strip()
        # Remove markdown code blocks if present
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        
        result = json.loads(result_text.strip())
        return result
    except Exception as e:
        logger.error(f"Error in relevance judgment: {e}", exc_info=True)
        print(f"Error in relevance judgment: {e}")
        # Default to allowing if check fails
        return {"is_relevant": True, "reason": "Error in judgment"}


def _filter_relevant_cases(user_input: str, cases: List[Dict]) -> List[Dict]:
    """
    Filter cases to only include those strictly relevant to the user query using LLM.
    """
    if not cases:
        return []
        
    llm_model = os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    
    # Prepare cases for prompt
    cases_text = ""
    for i, c in enumerate(cases):
        cases_text += f"Case {i+1} (ID: {c.get('case_no')}):\nQ: {c.get('question')}\nA: {c.get('answer')}\n\n"
        
    prompt = f"""Analisis apakah kasus-kasus berikut SANGAT RELEVAN dengan pertanyaan pengguna.

Pertanyaan Pengguna: "{user_input}"

Daftar Kasus:
{cases_text}

Instruksi:
1. Evaluasi setiap kasus. Apakah kasus ini membahas topik yang SAMA PERSIS atau SANGAT MIRIP dengan pertanyaan pengguna?
2. Jika kasus hanya sedikit terkait atau topiknya berbeda, JANGAN dimasukkan.
3. Kita ingin strict filtering. Lebih baik tidak menampilkan kasus daripada menampilkan yang tidak relevan.

Output JSON list berisi ID kasus yang relevan. Contoh: ["10", "12"]. Jika tidak ada yang relevan, kembalikan list kosong [].

Hanya output JSON."""

    try:
        start_time = datetime.now()
        response = client.models.generate_content(
            model=llm_model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Log LLM analytics
        llm_logger.info("SOP Case Filter", extra={
            "query": user_input,
            "duration": duration,
            "model": llm_model
        })
        
        # Parse JSON
        import json
        result_text = response.text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        
        relevant_ids = json.loads(result_text.strip())
        
        # Filter original list
        filtered_cases = [c for c in cases if str(c.get('case_no')) in [str(rid) for rid in relevant_ids]]
        
        logger.info(f"Case Filter: {len(cases)} -> {len(filtered_cases)} relevant cases")
        return filtered_cases
        
    except Exception as e:
        logger.error(f"Error in case filtering: {e}", exc_info=True)
        # On error, default to empty to be safe (strict)
        return []

def search_sop_exim(user_input: str, session_id: str = None) -> str:
    """
    Main function for SOP Chatbot with multi-step guardrail RAG pipeline
    """
    try:
        # Step 1: Length guardrail
        if not user_input or len(user_input.strip()) < 2:
            return "Mohon masukkan kata kunci yang lebih spesifik."
        
        # Step 2: Intent classification
        intent_result = _check_intent(user_input)
        logger.info(f"SOP Intent Check: {intent_result} for query '{user_input}'")
        print(f"Intent check: {intent_result}")
        
        # If clearly not SOP-related with high confidence, reject immediately
        if not intent_result["is_relevant"] and intent_result["confidence"] == "high":
            logger.info(f"SOP Rejected irrelevant query: '{user_input}'")
            return "Maaf, saya kurang memahami maksud dari pertanyaan Anda. Silakan ajukan pertanyaan yang lebih spesifik terkait prosedur EXIM."
        
        # Step 3: Retrieve documents (for uncertain or SOP-related queries)
        max_retries = int(os.getenv('SOP_MAX_RETRIES', '1'))
        retry_count = 0
        
        while retry_count <= max_retries:
            # Create embedding
            query_vector = chatbot_utils.create_embedding(client, user_input)
            
            # Search both collections
            sop_results = _search_sop_collection(query_vector, user_input, limit=3, session_id=session_id)
            case_results = _search_cases_collection(query_vector, user_input, limit=2)
            
            logger.info(f"SOP Search (Attempt {retry_count+1}): Found {len(sop_results)} SOPs, {len(case_results)} Cases")
            
            # Check if we have any results
            if not sop_results and not case_results:
                logger.warning(f"SOP No results found for query '{user_input}'")
                return "Maaf, saya tidak menemukan dokumen SOP yang relevan untuk menjawab pertanyaan Anda. Mohon coba dengan kata kunci yang lebih spesifik atau hubungi tim EXIM untuk bantuan lebih lanjut."
            
            # Build context
            context = _build_context(sop_results, case_results)
            
            # Step 4: Judge document relevance
            relevance_result = _judge_document_relevance(user_input, context)
            logger.info(f"SOP Relevance Judgment: {relevance_result}")
            print(f"Relevance judgment (attempt {retry_count + 1}): {relevance_result}")
            
            # If documents are relevant, generate answer
            if relevance_result["is_relevant"]:
                response = _generate_llm_response(user_input, context)
                
                # Append case data if available and relevant
                if case_results:
                    # STRICT FILTERING
                    relevant_cases = _filter_relevant_cases(user_input, case_results)
                    
                    if relevant_cases:
                        import json
                        # Filter only necessary fields for display
                        cases_for_display = [
                            {
                                "case_no": c.get("case_no"),
                                "question": c.get("question"),
                                "answer": c.get("answer")
                            }
                            for c in relevant_cases
                        ]
                        response += f"\n\n<CASE_DATA>\n{json.dumps(cases_for_display)}"
                
                return response
            
            # If documents not relevant
            # Check if this was a SOP-related query
            if intent_result["is_relevant"]:
                # SOP-related but docs not relevant - retry with expanded query
                if retry_count < max_retries:
                    logger.info(f"SOP Retrying with expanded query (attempt {retry_count + 1}/{max_retries})")
                    print(f"Retrying with expanded query (attempt {retry_count + 1}/{max_retries})")
                    # Expand query for retry
                    user_input = f"{user_input} prosedur SOP dokumen"
                    retry_count += 1
                    continue
                else:
                    # Max retries reached
                    logger.warning(f"SOP Max retries reached for query '{user_input}'")
                    return "Maaf, saya tidak menemukan dokumen SOP yang relevan untuk menjawab pertanyaan Anda. Mohon coba dengan kata kunci yang lebih spesifik atau hubungi tim EXIM untuk bantuan lebih lanjut."
            else:
                # Not SOP-related and docs not relevant - give guidance
                logger.info(f"SOP Irrelevant query and docs: '{user_input}'")
                return "Saya kurang memahami pertanyaan Anda. Silakan ajukan pertanyaan yang lebih spesifik terkait regulasi atau prosedur EXIM."
        
        # Fallback (should not reach here)
        return "Maaf, saya tidak menemukan dokumen SOP yang relevan untuk menjawab pertanyaan Anda. Mohon coba dengan kata kunci yang lebih spesifik atau hubungi tim EXIM untuk bantuan lebih lanjut."
        
    except Exception as e:
        logger.error(f"Error in search_sop_exim: {e}", exc_info=True)
        print(f"Error in search_sop_exim: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)}\n\nSilakan coba lagi atau hubungi administrator."

def show():
    """Display SOP Chatbot page"""
    # Initialize chat history
    if "messages_sop" not in st.session_state:
        st.session_state.messages_sop = []
    
    # Initialize edit state
    if "edit_message_index" not in st.session_state:
        st.session_state.edit_message_index = None
    
    # Sync messages from Redis to Session State
    if "current_session_id" in st.session_state and st.session_state.current_session_id:
        db_messages = database.load_chat_history("guest", "SOP", st.session_state.current_session_id)
        st.session_state.messages_sop = [
            {"role": m["role"], "content": m["content"], "timestamp": m.get("timestamp")} 
            for m in db_messages
        ]

    # Display chat history
    for idx, message in enumerate(st.session_state.messages_sop):
        chatbot_utils.render_chat_message(
            message, 
            idx, 
            "messages_sop", 
            "edit_message_index",
            lambda i, t: chatbot_utils.regenerate_response(i, t, "messages_sop", "SOP", search_sop_exim)
        )
    
    # Chat input
    # Check status from DB
    session_id = st.session_state.get("current_session_id")
    if not session_id:
        return

    status = database.get_session_status(session_id)
    is_processing = (status == "processing")

    prompt = st.chat_input(
        "Ask about EXIM SOPs... (e.g., 'document approval process')",
        key="sop_input",
        disabled=is_processing
    )

    if prompt:
        chatbot_utils.handle_chat_input(prompt, "messages_sop", "SOP", search_sop_exim)
    
    # Polling if processing
    if is_processing:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                import time
                while True:
                    time.sleep(1)
                    new_status = database.get_session_status(session_id)
                    if new_status != "processing":
                        st.rerun()
                        break
