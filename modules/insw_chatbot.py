
from modules import database, chatbot_utils
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os
from ingestion.insw.insw_qdrant_store import INSWQdrantStore
import dateutil.parser

load_dotenv()

# Initialize Qdrant client for INSW with correct env vars
qdrant_url = os.getenv("INSW_QDRANT_URL", "http://localhost:6333")
qdrant_api_key = os.getenv("INSW_QDRANT_API_KEY", "")
insw_collection_name = os.getenv("INSW_QDRANT_COLLECTION_NAME", "insw_regulations_hybrid")
insw_store = INSWQdrantStore(qdrant_url, qdrant_api_key, insw_collection_name)

# Initialize Gemini Client
client = chatbot_utils.init_gemini_client()

# Setup loggers
from modules import app_logger
logger = app_logger.setup_logger()
llm_logger = app_logger.setup_llm_logger()

def _format_date(date_str):
    """Format ISO date string to readable format"""
    if not date_str:
        return "N/A"
    try:
        dt = dateutil.parser.parse(date_str)
        return dt.strftime("%d %B %Y")
    except:
        return date_str

def _build_insw_context(results: list) -> str:
    """
    Build context string from INSW search results.
    Parses the 'full_document' JSON to extract comprehensive details including:
    - Hierarchy (Bagian, Bab, Parent Uraian)
    - Detailed Regulations (Import, Border, Post-Border, Export)
    - BC Documents
    - Reference Satuan
    """
    if not results:
        return "Tidak ada data INSW yang relevan ditemukan."
    
    context_parts = ["=== Data INSW yang Relevan ===\n"]
    
    for idx, result in enumerate(results, 1):
        payload = result.get("payload", {})
        
        # 1. Try to parse 'full_document' JSON string
        # The payload often contains a 'full_document' string which has the nested structure
        full_doc_str = payload.get("full_document", "")
        data = {}
        
        if full_doc_str and isinstance(full_doc_str, str):
            try:
                import json
                data = json.loads(full_doc_str)
            except Exception as e:
                print(f"Error parsing full_document: {e}")
                data = payload # Fallback to flat payload
        else:
            data = payload # Fallback if no full_document

        # 2. Extract Basic Info
        hs_code = data.get("hs_code", "N/A")
        deskripsi = data.get("deskripsi", "")
        uraian_barang = data.get("uraian_barang", "")
        
        # 3. Extract Hierarchy
        bagian = data.get("bagian", "")
        bab = data.get("bab", "")
        bagian_penjelasan = data.get("bagian_penjelasan", [])
        bab_penjelasan = data.get("bab_penjelasan", [])
        hs_parent_uraian = data.get("hs_parent_uraian", [])
        
        # 4. Extract Regulations
        regulations = data.get("regulations", {})
        import_regs = regulations.get("import_regulation", [])
        import_border = regulations.get("import_regulation_border", [])
        import_post_border = regulations.get("import_regulation_post_border", [])
        export_regs = regulations.get("export_regulation", [])
        
        # 5. Extract Documents & Refs
        bc_documents = data.get("bc_documents", [])
        ref_satuan = data.get("ref_satuan", [])
        link = data.get("link", "")

        # --- Build Context String ---
        item = f"{idx}. HS Code: {hs_code}\n"
        if deskripsi: item += f"   Deskripsi: {deskripsi}\n"
        if uraian_barang: item += f"   Uraian Barang: {uraian_barang}\n"
        
        # Hierarchy
        hierarchy_info = []
        if bagian: hierarchy_info.append(f"Bagian {bagian}")
        if bab: hierarchy_info.append(f"Bab {bab}")
        if hierarchy_info:
            item += f"   Klasifikasi: {', '.join(hierarchy_info)}\n"
            
        if hs_parent_uraian:
            # Join with arrow for visual hierarchy
            item += f"   Hierarki: {' > '.join(hs_parent_uraian)}\n"
            
        # Regulations Detail
        if import_regs:
            item += "   [Ketentuan Impor Umum]:\n"
            for r in import_regs:
                item += f"    - {r.get('name', '')}\n"
                if r.get('legal'): item += f"      Legal: {r.get('legal')}\n"

        if import_border:
            item += "   [Ketentuan Impor Border (Pengawasan di Perbatasan)]:\n"
            for r in import_border:
                item += f"    - {r.get('name', '')}\n"
                if r.get('legal'): item += f"      Legal: {r.get('legal')}\n"

        if import_post_border:
            item += "   [Ketentuan Impor Post-Border (Pengawasan Setelah Keluar Pelabuhan)]:\n"
            for r in import_post_border:
                item += f"    - {r.get('name', '')}\n"
                if r.get('legal'): item += f"      Legal: {r.get('legal')}\n"

        if export_regs:
            item += "   [Ketentuan Ekspor]:\n"
            for r in export_regs:
                item += f"    - {r.get('name', '')}\n"
                if r.get('legal'): item += f"      Legal: {r.get('legal')}\n"

        # BC Documents
        if bc_documents:
            doc_types = [d.get('type') for d in bc_documents if d.get('type')]
            if doc_types:
                item += f"   Dokumen BC: {', '.join(doc_types)}\n"

        # Satuan
        if ref_satuan:
            satuan_list = [f"{s.get('ur_satuan')} ({s.get('kd_satuan')})" for s in ref_satuan if s.get('ur_satuan')]
            if satuan_list:
                item += f"   Satuan: {', '.join(satuan_list)}\n"
        
        if link:
            item += f"   Link Detail: {link}\n"
            
        context_parts.append(item)
    
    return "\n".join(context_parts)


def search_insw_regulation(user_input):
    """
    Search INSW regulations using hybrid search (dense + sparse)
    """
    try:
        # Guardrail: Check for very short/empty input
        if not user_input or len(user_input.strip()) < 2:
            return "Mohon masukkan kata kunci yang lebih spesifik.\n\n---\n*Untuk informasi lebih lanjut, silakan kunjungi [INSW INTR](https://insw.go.id/intr).*"

        # HS Code Auto-detection: If input is purely numeric, treat as HS Code
        clean_input = user_input.strip()
        # Remove spaces to check if it's a number (e.g. "12 34")
        if clean_input.replace(" ", "").isdigit():
            user_input = f"hs code {clean_input}"

        # Create embeddings for query
        query_embedding = chatbot_utils.create_embedding(client, user_input)
        
        # Search in Qdrant with hybrid search
        results = insw_store.search_hybrid(user_input, query_embedding, limit=5)
        
        logger.info(f"INSW Search: '{user_input}' found {len(results)} results")
        
        # Check confidence
        max_score = 0.0
        latest_date = None
        
        if results:
            max_score = max(r.get('score', 0.0) if isinstance(r, dict) else getattr(r, 'score', 0.0) for r in results)
            
            # Extract latest modification date
            for r in results:
                payload = r.get('payload', {})
                # Try top level first, then full_document metadata
                date_str = payload.get('lastModifiedDateTime')
                if not date_str:
                    # Try parsing full_document
                    try:
                        import json
                        full_doc = json.loads(payload.get('full_document', '{}'))
                        date_str = full_doc.get('lastModifiedDateTime')
                    except:
                        pass
                
                if date_str:
                    # Simple string comparison works for ISO dates to find latest
                    if latest_date is None or date_str > latest_date:
                        latest_date = date_str

        # Build footer with data date if available
        if latest_date:
            formatted_date = _format_date(latest_date)
            footer = f"\n\n---\n*Data yang disajikan di atas berdasarkan informasi INSW per {formatted_date}. Untuk informasi terbaru atau pencarian manual, silakan kunjungi [INSW INTR](https://insw.go.id/intr).*"
        else:
            footer = "\n\n---\n*Untuk informasi terbaru atau pencarian manual, silakan kunjungi [INSW INTR](https://insw.go.id/intr).*"

        if max_score < chatbot_utils.CONFIDENCE_THRESHOLD:
            logger.warning(f"INSW Low confidence: {max_score} for query '{user_input}'")
            return "Maaf, saya tidak menemukan informasi regulasi HS Code yang cukup relevan untuk menjawab pertanyaan Anda. Mohon pastikan kata kunci atau HS Code yang Anda masukkan benar." + footer
        
        if not results:
            logger.warning(f"INSW No results for query '{user_input}'")
            return "Tidak ditemukan data HS Code yang relevan. Silakan coba kata kunci lain." + footer
        
        # Build context from search results
        context = _build_insw_context(results)
        
        # Generate LLM response with Indonesian system prompt
        system_prompt = """Anda adalah Asisten HS Code untuk regulasi ekspor-impor.

Peran Anda:
- Memberikan informasi akurat tentang HS Code, regulasi import/export, dan dokumen kepabeanan
- Menjelaskan ketentuan larangan/pembatasan (Lartas) yang berlaku secara spesifik (Border vs Post-Border)
- Mengutip dasar hukum/peraturan yang relevan
- Menggunakan Bahasa Indonesia yang profesional
- Data yang Anda gunakan berasal dari database HS Code, BUKAN dari pengguna

Format Jawaban:
1. **Ringkasan**: Jawaban singkat tentang HS Code, uraian barang, dan status regulasinya.
2. **Detail Regulasi**:
   - **Impor (Border)**: Ketentuan yang harus dipenuhi di perbatasan (jika ada).
   - **Impor (Post-Border)**: Ketentuan yang harus dipenuhi setelah keluar pelabuhan (jika ada).
   - **Ekspor**: Ketentuan ekspor (jika ada).
3. **Dokumen yang Diperlukan**: Dokumen BC dan perizinan yang dibutuhkan.
4. **Dasar Hukum**: Peraturan yang menjadi dasar ketentuan.
5. **Link Referensi**: Sertakan link referensi jika tersedia.

Penting:
- Selalu sebutkan HS Code lengkap (8 digit)
- Bedakan dengan jelas antara regulasi Border dan Post-Border
- Jika ada beberapa HS Code relevan, jelaskan detailnya satu per satu
- Jika informasi tidak tersedia, nyatakan dengan jelas
- JANGAN katakan "berdasarkan data yang Anda berikan" - data berasal dari database HS Code, bukan dari pengguna
- Gunakan frasa seperti "berdasarkan data HS Code" atau "berdasarkan informasi dari database"
"""

        user_message = f"""Konteks:
{context}

Pertanyaan: {user_input}

Berikan jawaban yang komprehensif berdasarkan konteks di atas."""

        # Use the global client instance
        start_time = datetime.now(ZoneInfo("Asia/Jakarta"))
        response = client.models.generate_content(
            model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            contents=[
                {"role": "user", "parts": [{"text": system_prompt}]},
                {"role": "model", "parts": [{"text": "Saya mengerti. Saya akan menjawab pertanyaan tentang regulasi HS Code dengan mengutip HS Code, ketentuan import/export (Border/Post-Border), dan dasar hukum yang relevan."}]},
                {"role": "user", "parts": [{"text": user_message}]}
            ]
        )
        end_time = datetime.now(ZoneInfo("Asia/Jakarta"))
        duration = (end_time - start_time).total_seconds()
        
        # Log LLM analytics
        llm_logger.info("INSW LLM Call", extra={
            "query": user_input,
            "duration": duration,
            "model": os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            "input_chars": len(system_prompt) + len(user_message),
            "output_chars": len(response.text)
        })
        
        return response.text + footer

    except Exception as e:
        logger.error(f"Error searching INSW regulations: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)}\n\nSilakan coba lagi atau hubungi administrator.\n\n---\n*Untuk informasi lebih lanjut, silakan kunjungi [INSW INTR](https://insw.go.id/intr).*"

        



