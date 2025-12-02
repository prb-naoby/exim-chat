"""
Gemini-based parser for SOP PDF documents
"""
import json
import base64
from google import genai
from google.genai import types
from typing import Dict, Any


class SOPParser:
    """Parse SOP PDF documents using Gemini to extract structured fields"""
    
    def __init__(self, model_name: str, api_key: str):
        """
        Initialize SOP parser with Gemini LLM
        
        Args:
            model_name: Gemini model name (e.g., gemini-2.0-flash-exp)
            api_key: Gemini API key
        """
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
    
    def parse_sop_pdf(self, pdf_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse SOP PDF document directly with Gemini to extract structured fields
        
        Args:
            pdf_content: PDF file content as bytes
            filename: Original filename for context and type extraction
            
        Returns:
            Dict with parsed fields: sop_title, tujuan, uraian, dokumen, date, doc_no, rev, type
        """
        # Extract document type from filename (IK_xxx -> IK, SOP_xxx -> SOP)
        doc_type = "UNKNOWN"
        if "_" in filename:
            prefix = filename.split("_")[0].upper()
            if prefix in ["IK", "SOP"]:
                doc_type = prefix
        
        prompt = """You are an expert at analyzing Standard Operating Procedure (SOP) and Instruksi Kerja (IK) documents in Indonesian language.

Please carefully analyze this document and extract the following information:

1. **SOP Title / Judul**: The main title of the document (e.g., "EKSPOR (BC 3.0/BC 3.3)", "ARSIP DOKUMEN")
2. **Tujuan**: The purpose/objective section. This describes WHY this procedure exists and what it aims to achieve.
3. **Uraian**: The detailed procedure description/steps. This is usually the main content with numbered steps or detailed instructions.
4. **Dokumen**: List of required documents mentioned in the DOKUMEN section.
5. **Date**: Document date (format as shown in header)
6. **Doc. No.**: Document number (e.g., "13.1")
7. **Rev.**: Revision number (e.g., "03")

IMPORTANT INSTRUCTIONS:
- For **Tujuan**: Look for section titled "TUJUAN" or similar. Extract the complete text explaining the purpose.
- For **Uraian**: Look for section titled "URAIAN" or the main procedure steps. This is usually the longest section with detailed steps.
- For **Dokumen**: Look for section titled "DOKUMEN" listing required documents. If not found, extract document references from the content.
- If any field is not clearly found, return an empty string for that field.
- Preserve Indonesian text exactly as written.
- For date, try to find in header metadata section.

Return your response ONLY as a valid JSON object with these exact keys:
{
    "sop_title": "...",
    "tujuan": "...",
    "uraian": "...",
    "dokumen": "...",
    "date": "...",
    "doc_no": "...",
    "rev": "..."
}

Important: Return ONLY the JSON object, no markdown formatting, no additional text."""

        try:
            print(f"    Parsing PDF with Gemini: {filename}")
            
            # Convert PDF to base64
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            
            # Create inline data part with base64 PDF
            pdf_part = types.Part(
                inline_data=types.Blob(
                    mime_type="application/pdf",
                    data=pdf_base64
                )
            )
            
            # Generate content with PDF
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(text=prompt),
                            pdf_part
                        ]
                    )
                ]
            )
            
            # Extract JSON from response
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                # Remove ```json or ``` at start
                lines = response_text.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                response_text = '\n'.join(lines)
            
            response_text = response_text.strip()
            
            # Parse JSON
            parsed = json.loads(response_text)
            
            # Validate required keys
            required_keys = ['sop_title', 'tujuan', 'uraian', 'dokumen', 'date', 'doc_no', 'rev']
            for key in required_keys:
                if key not in parsed:
                    parsed[key] = ''
            
            # Add document type based on filename
            parsed['type'] = doc_type
            
            print(f"    Parsed: {parsed.get('sop_title', 'Unknown')[:50]}, Type: {doc_type}")
            return parsed
            
        except json.JSONDecodeError as e:
            print(f"    Warning: Failed to parse Gemini response as JSON: {e}")
            print(f"    Response was: {response_text[:200]}")
            # Return structure with filename info
            return {
                'sop_title': filename.replace('.pdf', ''),
                'tujuan': '',
                'uraian': '',
                'dokumen': '',
                'date': '',
                'doc_no': '',
                'rev': '',
                'type': doc_type
            }
        except Exception as e:
            print(f"    Error parsing PDF: {e}")
            return {
                'sop_title': filename.replace('.pdf', ''),
                'tujuan': '',
                'uraian': '',
                'dokumen': '',
                'date': '',
                'doc_no': '',
                'rev': '',
                'type': doc_type
            }

