"""
OCR processing for SOP PDF documents
"""
import requests
from typing import Dict, Any, Optional


class OCRProcessor:
    """Process PDFs through OCR service"""
    
    def __init__(self, ocr_url: str, ocr_api_key: Optional[str] = None):
        """
        Initialize OCR processor
        
        Args:
            ocr_url: OCR service endpoint
            ocr_api_key: Optional API key for OCR service
        """
        self.ocr_url = ocr_url
        self.ocr_api_key = ocr_api_key
    
    def process_pdf(self, pdf_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Send PDF to OCR service and get text
        
        Args:
            pdf_content: PDF file content as bytes
            filename: Original filename
            
        Returns:
            Dict with 'text' key containing OCR result
        """
        # Prepare multipart form data
        files = {
            'file': (filename, pdf_content, 'application/pdf')
        }
        
        data = {
            'lang': 'en',
            'page_range': 'all',
            'dpi': 300,
            'min_confidence': 0.5,
            'detect_headings': 'true',
            'force_ocr': 'true'
        }
        
        headers = {}
        if self.ocr_api_key:
            headers['Authorization'] = f'Bearer {self.ocr_api_key}'
        
        print(f"    Sending PDF to OCR service: {filename}")
        
        try:
            response = requests.post(
                self.ocr_url,
                files=files,
                data=data,
                headers=headers,
                timeout=120  # 2 minutes timeout for OCR
            )
            response.raise_for_status()
            result = response.json()
            
            print(f"    OCR completed: {len(result.get('text', ''))} characters")
            return result
            
        except requests.exceptions.Timeout:
            raise Exception(f"OCR timeout for {filename}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"OCR request failed for {filename}: {str(e)}")
        except Exception as e:
            raise Exception(f"OCR processing error for {filename}: {str(e)}")
