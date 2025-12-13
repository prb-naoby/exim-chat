from modules import database, chatbot_utils, app_logger
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Prefetch, FusionQuery
from functools import lru_cache

load_dotenv()

# Initialize Gemini Client
client = chatbot_utils.init_gemini_client()

# Setup loggers
logger = app_logger.setup_logger()
llm_logger = app_logger.setup_llm_logger()

# Initialize Qdrant Client (Global/Cached)
@lru_cache(maxsize=1)
def get_qdrant_client():
    url = os.getenv('SOP_QDRANT_URL') 
    api_key = os.getenv('SOP_QDRANT_API_KEY')
    # Using same credentials as SOP for now, assuming shared instance
    return QdrantClient(url=url, api_key=api_key)

def _search_others_collection(query_vector: List[float], query_text: str, limit: int = 5, threshold: float = 0.45) -> List[Dict[str, Any]]:
    """
    Search Others (unstructured) documents collection with STRICT filtering.
    """
    collection_name = os.getenv('OTHERS_QDRANT_COLLECTION_NAME', 'others_documents')
    qdrant_client = get_qdrant_client()
    
    try:
        # Use query_points instead of search (search deprecated/missing in this version)
        result_obj = qdrant_client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            score_threshold=threshold,
            with_payload=True
        )
        results = result_obj.points
        
        # DEBUG: Log retrieval scores
        if results:
            scores = [r.score for r in results]
            logger.info(f"Others Search Scores for '{query_text}': {scores}")
        else:
            logger.info(f"Others Search: No results found above threshold {threshold}")
        
        formatted_results = []
        for point in results:
            formatted_results.append({
                'content': point.payload.get('content', ''),
                'filename': point.payload.get('filename', ''),
                'webUrl': point.payload.get('webUrl', ''),
                'score': point.score
            })
            
        return formatted_results
    except Exception as e:
        logger.error(f"Error searching others collection: {str(e)}")
        print(f"Error searching others collection: {str(e)}")
        return []

def _build_context(others_results: List[Dict]) -> str:
    """Build context string from search results"""
    if not others_results:
        return ""
    
    context_parts = []
    context_parts.append("=== Informasi Umum & Internal EXIM ===\n")
    
    for idx, item in enumerate(others_results, 1):
        content = item.get('content', '').strip()
        filename = item.get('filename', 'Unknown')
        web_url = item.get('webUrl')
        
        # Consistent Link Logic (Parity with SOP Chatbot)
        # Always try to generate a download link if filename exists
        if filename and filename != 'Unknown':
             import urllib.parse
             safe_filename = urllib.parse.quote(filename)
             # Overwrite/Set web_url to the internal download endpoint
             web_url = f"/download-link?filename={safe_filename}&chatbot_type=OTHERS"
        
        # Truncate very long content (approx 2000 chars per chunk to fit context)
        if len(content) > 2000:
            content = content[:2000] + "..."
            
        text = f"{idx}. Dokumen: {filename} (Score: {item.get('score', 0):.2f})\n"
        text += f"   Konten: {content}\n"
        
        if web_url:
             text += f"   Link Dokumen: [{filename}]({web_url})\n"
        
        context_parts.append(text)

    return "\n".join(context_parts)

def _generate_llm_response(user_query: str, context: str) -> str:
    """Generate response using Gemini LLM"""
    llm_model = os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    
    # If context is empty, we act as a General Assistant but declare we don't have specific internal docs
    if not context:
        context_warning = "CATATAN SISTEM: Tidak ada dokumen internal Panarub yang ditemukan cocok dengan pertanyaan ini (skor relevansi rendah)."
    else:
        context_warning = ""

    system_prompt = """Anda adalah Asisten Virtual General & EXIM untuk PT Panarub Industry.
    
Tugas Utama Anda:
1. Menjawab pertanyaan pengguna HANYA dan MUTLAK berdasarkan informasi yang tersedia di "Konteks Dokumen".
2. JANGAN menggunakan pengetahuan umum Anda. Jika informasi tidak ada di konteks, KATAKAN: "Maaf, saya tidak menemukan informasi tersebut dalam dokumen internal kami."
3. Langsung berikan jawaban inti. JANGAN MEMULAI dengan frasa seperti "Berdasarkan dokumen...", "Mengacu pada konteks...", atau sejenisnya.
4. Gaya bahasa: Formal, Informatif, Profesional, Langsung pada inti.

Aturan Referensi (Link Wajib):
- WAJIB menyertakan daftar dokumen sumber di BAGIAN PALING BAWAH jawaban.
- Format yang HARUS dipatuhi untuk setiap referensi:
  
  **Referensi:**
  - [Judul Dokumen](URL Link Dokumen)
  
  (Ambil URL dari bagian "Link Dokumen" di dalam konteks. Jangan ubah link tersebut.)

Aturan Kritis:
- JIKA KONTEKS KOSONG atau TIDAK RELEVAN: JANGAN MENJAWAB pertanyaan. Cukup katakan: "Maaf, saya tidak memiliki dokumen referensi yang relevan untuk menjawab pertanyaan ini."
"""

    user_message = f"""{context_warning}

Konteks Dokumen:
{context}

Pertanyaan Pengguna: {user_query}

Ingat: HANYA jawab dari konteks. Jika konteks kosong, tolak menjawab."""

    try:
        response = client.models.generate_content(
            model=llm_model,
            contents=[
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "model", "parts": [{"text": "Dimengerti. Saya SANGAT PATUH pada konteks. Jika tidak ada di konteks, saya akan menolak menjawab."}]},
                {"role": "user", "parts": [{"text": user_message}]}
            ]
        )
        
        return response.text
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        return f"Error generating response: {str(e)}"

        return response.text
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        return f"Error generating response: {str(e)}"

def _check_relevancy(user_query: str, chunks: List[Dict[str, Any]]) -> bool:
    """
    Ask LLM if the provided chunks are relevant to the user query.
    Returns True if relevant, False otherwise.
    """
    llm_model = os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    
    # Prepare chunk summaries for validation
    chunk_text = ""
    for idx, c in enumerate(chunks, 1):
        chunk_text += f"Chunk {idx}: {c.get('content', '')[:500]}...\n"

    system_prompt = """Anda adalah validator relevansi dokumen.
    Tugas: Jawab pertanyaan ini untuk setiap potongan dokumen:
    "Apakah ada informasi di dalam potongan ini yang MUNGKIN bisa menjawab pertanyaan pengguna?"
    
    Kriteria:
    - Jawab "YA" jika ada sedikit saja informasi yang berkaitan atau bisa membantu menjawab.
    - Jawab "TIDAK" hanya jika sama sekali tidak relevan.
    
    Jawab HANYA dengan satu kata: "YA" atau "TIDAK".
    """
    
    user_message = f"""Potongan Dokumen:
{chunk_text}

Pertanyaan Pengguna: {user_query}

Apakah relevan? (YA/TIDAK)"""

    try:
        response = client.models.generate_content(
            model=llm_model,
            contents=[
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "user", "parts": [{"text": user_message}]}
            ]
        )
        answer = response.text.strip().upper()
        logger.info(f"Relevancy Check for '{user_query}': {answer}")
        return "YA" in answer
    except Exception as e:
        logger.error(f"Error checking relevancy: {e}")
        # Default to True on error to avoid blocking potentially good answers if LLM acts up
        return True 

def _check_intent_others(user_input: str) -> dict:
    """Check if query is related to General EXIM/Others"""
    llm_model = os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    
    prompt = f"""Analisis jenis pertanyaan berikut.

Pertanyaan: "{user_input}"

Kategori:
1. OTHERS: Terkait dokumen internal perusahaan, regulasi umum, atau informasi yang mungkin disimpan dalam database 'Lainnya' (Bahan sosialisasi, Notulensi rapat, dll).
2. GREETING: Sapaan sopan santun (Halo, Selamat pagi).
3. IRRELEVANT: Coding, Resep masakan, Pembahasan game, dan hal lain yang TIDAK ADA HUBUNGANNYA dengan pekerjaan kantor atau EXIM.

Berikan jawaban dalam format JSON:
{{
  "category": "OTHERS" atau "GREETING" atau "IRRELEVANT",
  "reason": "..."
}}
Hanya output JSON."""

    try:
        start_time = datetime.now(ZoneInfo("Asia/Jakarta"))
        response = client.models.generate_content(
            model=llm_model, contents=[{"role": "user", "parts": [{"text": prompt}]}]
        )
        end_time = datetime.now(ZoneInfo("Asia/Jakarta"))
        duration = (end_time - start_time).total_seconds()
        
        # Log LLM analytics
        llm_logger.info("OTHERS Intent Check", extra={
            "query": user_input, "duration": duration, "model": llm_model
        })
        
        import json
        result_text = response.text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"): result_text = result_text[4:]
        return json.loads(result_text.strip())
    except:
        return {"category": "OTHERS"}

def _generate_greeting_response(user_input: str) -> str:
    return "Halo! Saya adalah Asisten Dokumen Lainnya. Saya dapat membantu mencari informasi dari bahan sosialisasi, notulensi rapat, dan dokumen internal lainnya."

def _generate_irrelevant_response() -> str:
    return "Maaf, saya hanya dapat menjawab pertanyaan terkait dokumen internal perusahaan dan informasi EXIM."

def search_others(user_input: str, session_id: str = None) -> str:
    """
    Main function for Others Chatbot.
    """
    try:
        if not user_input or len(user_input.strip()) < 2:
            return "Mohon masukkan pertanyaan yang lebih jelas."
        
        # Intent Check
        intent_result = _check_intent_others(user_input)
        category = intent_result.get("category", "OTHERS")
        
        if category == "GREETING":
            return _generate_greeting_response(user_input)
        if category == "IRRELEVANT":
            return _generate_irrelevant_response()

        # Create embedding
        query_vector = chatbot_utils.create_embedding(client, user_input)
        
        # 1. Primary Search: Lowered Strict Threshold (0.35) to improve recall
        results = _search_others_collection(query_vector, user_input, limit=5, threshold=0.35)
        
        # 2. Fallback: If no results, try Top 5 without strict threshold & Check Relevancy
        if not results:
            logger.info("Strict search returned 0 results. Attempting Fallback...")
            fallback_results = _search_others_collection(query_vector, user_input, limit=5, threshold=0.0)
            
            if fallback_results:
                is_relevant = _check_relevancy(user_input, fallback_results)
                if is_relevant:
                    logger.info("Fallback: Relevancy Check PASSED. Using fallback results.")
                    results = fallback_results
                else:
                    logger.info("Fallback: Relevancy Check FAILED. Ignoring fallback results.")
            else:
                logger.info("Fallback: No documents found even with 0 threshold.")

        logger.info(f"Others Search: Final Context has {len(results)} docs for '{user_input}'")
        
        # Build Context
        context = _build_context(results)
        
        # Generate Answer
        response = _generate_llm_response(user_input, context)
        
        return response

    except Exception as e:
        logger.error(f"Error in search_others: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)}\n\nSilakan coba lagi."
