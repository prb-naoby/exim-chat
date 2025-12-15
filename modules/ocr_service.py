
import os
import requests
from typing import Optional, Dict, Any

# Robust import for google.genai
genai = None
try:
    from google import genai
    from google.genai import types
except ImportError:
    try:
        import google.genai as genai
        from google.genai import types
    except ImportError:
        try:
            import google.generativeai as genai
            types = None # Old SDK doesn't use types.Part in same way
        except ImportError:
            pass

class OCRService:
    def __init__(self, api_url: str = None, api_key: str = None, gemini_api_key: str = None):
        self.api_url = api_url or os.getenv('OCR_SERVICE_URL')
        self.api_key = api_key or os.getenv('OCR_API_KEY')
        self.gemini_api_key = gemini_api_key or os.getenv('GEMINI_API_KEY')
        
        self.gemini_client = None
        if self.gemini_api_key and genai:
             try:
                self.gemini_client = genai.Client(api_key=self.gemini_api_key)
             except Exception as e:
                print(f"Warning: Failed to init Gemini client in OCRService: {e}")
        
    # process_pdf removed as we migrated to process_with_genai


    def process_with_genai(self, file_path: str, model_name: str = "gemini-2.5-flash") -> Optional[str]:
        """
        Process a PDF/Image file using Google GenAI (Gemini) for OCR/Transcription.
        
        Args:
            file_path: Path to file
            model_name: Gemini model to use
            
        Returns:
            Transcribed text or None
        """
        if not self.gemini_client:
            print("Gemini client not initialized via OCRService")
            return None
            
        if not os.path.exists(file_path):
             print(f"File not found for GenAI OCR: {file_path}")
             return None
             
        try:
             import base64
             
             # Read file
             with open(file_path, "rb") as f:
                 file_content = f.read()
                 
             # MIME type detection
             mime_type = "application/pdf"
             if file_path.lower().endswith(('.jpg', '.jpeg')):
                 mime_type = "image/jpeg"
             elif file_path.lower().endswith('.png'):
                 mime_type = "image/png"
                 
             # Prompt
             prompt = """
Task: Extract the exact text content from this document page.
Rules:
1. Extract ONLY the text visible on the page. Do NOT add any words, interpretations, or descriptions.
2. Maintain the strict reading order (top-to-bottom, left-to-right).
3. If a section is a table, extract the text row-by-row, cell-by-cell, separated by spaces or tabs, preserving the order.
4. Ignore purely visual elements like shapes or icons unless they contain text labels.
5. Do NOT use Markdown formatting (no headers, no bolding). Just plain text.
6. Strictly follow the primary language of the document.
7. Output nothing but the extracted text.
"""
             
             # Prepare content depending on SDK version (assuming new SDK based on imports)
             # Check if we have types.Part (New SDK)
             if types and hasattr(types, 'Part'):
                 parts = [
                     types.Part(text=prompt),
                     types.Part(
                         inline_data=types.Blob(
                             mime_type=mime_type,
                             data=base64.b64encode(file_content).decode('utf-8')
                         )
                     )
                 ]
                 
                 response = self.gemini_client.models.generate_content(
                     model=model_name,
                     contents=[types.Content(role="user", parts=parts)]
                 )
                 
             else:
                 # Fallback to old SDK usage pattern if types not available or init differently
                 # But self.gemini_client construction implies new SDK (genai.Client)
                 # If old SDK (google.generativeai), the client structure is different (GenerativeModel)
                 # We assume new SDK per check_genai.py results users environment
                 
                 # Basic fallback for new SDK without types helper if needed
                 b64_data = base64.b64encode(file_content).decode('utf-8')
                 response = self.gemini_client.models.generate_content(
                     model=model_name,
                     contents=[
                         {"role": "user", "parts": [
                             {"text": prompt},
                             {"inline_data": {"mime_type": mime_type, "data": b64_data}}
                         ]}
                     ]
                 )
                 
             return response.text.strip()
             
        except Exception as e:
            print(f"GenAI OCR Error: {e}")
            return None

    def analyze_image_answer(self, image_bytes: bytes, question: str, model_name: str = "gemini-2.5-flash") -> Optional[str]:
        """
        Analyze an image and generate an answer based on the question context.
        Used for Cases Q&A where the answer is an image/screenshot.
        
        Args:
            image_bytes: Raw image bytes (PNG, JPEG, etc.)
            question: The question that this image is answering
            model_name: Gemini model to use
            
        Returns:
            Generated text answer or None
        """
        if not self.gemini_client:
            print("Gemini client not initialized")
            return None
            
        try:
            import base64
            
            # Detect MIME type from magic bytes
            mime_type = "image/png"  # default
            if image_bytes[:3] == b'\xff\xd8\xff':
                mime_type = "image/jpeg"
            elif image_bytes[:4] == b'\x89PNG':
                mime_type = "image/png"
            elif image_bytes[:4] == b'GIF8':
                mime_type = "image/gif"
            
            # Prompt that instructs Gemini to answer the question based on image
            prompt = f"""Pertanyaan: {question}

Lihat gambar di bawah dan jawab pertanyaan di atas secara langsung.

Aturan:
1. Jawab pertanyaan secara LANGSUNG tanpa menyebut "gambar", "screenshot", "berdasarkan gambar", dll.
2. Tulis jawaban seolah-olah Anda yang mengetahui informasinya, bukan mengekstrak dari gambar.
3. Jika gambar menunjukkan langkah-langkah, jelaskan langkah-langkahnya secara jelas.
4. Jika gambar menunjukkan data/tabel, sajikan informasinya secara terstruktur.
5. Gunakan Bahasa Indonesia.
6. Langsung pada inti jawaban, JANGAN awali dengan "Jawaban:" atau pengantar lainnya.

Jawaban:"""
            
            # Prepare content
            b64_data = base64.b64encode(image_bytes).decode('utf-8')
            
            if types and hasattr(types, 'Part'):
                parts = [
                    types.Part(text=prompt),
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=mime_type,
                            data=b64_data
                        )
                    )
                ]
                
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=[types.Content(role="user", parts=parts)]
                )
            else:
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=[
                        {"role": "user", "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": mime_type, "data": b64_data}}
                        ]}
                    ]
                )
                
            return response.text.strip()
            
        except Exception as e:
            print(f"Image Analysis Error: {e}")
            return None
