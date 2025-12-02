"""
SOP PDF ingestion module with OCR processing
Uses Microsoft Graph SDK
Workflow:
1. Check for PDF files updated on OneDrive
2. For updated files, send to OCR service
3. Get OCR result and vectorize
4. Store in Qdrant with document link as metadata
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
from azure.identity import ClientSecretCredential


class SOPOneDriveSync:
    """Sync SOP PDF documents from OneDrive"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 drive_id: str, folder_path: str, 
                 ocr_service_url: str, ocr_api_key: Optional[str] = None):
        """
        Initialize SOP OneDrive sync
        
        Args:
            tenant_id: Microsoft Entra tenant ID
            client_id: Microsoft Entra app client ID
            client_secret: Microsoft Entra app client secret
            drive_id: OneDrive drive ID
            folder_path: Folder path within drive (e.g., 'AI/SOP')
            ocr_service_url: URL endpoint for OCR service
            ocr_api_key: Optional API key for OCR service
        """
        self.drive_id = drive_id
        self.folder_path = folder_path
        self.ocr_service_url = ocr_service_url
        self.ocr_api_key = ocr_api_key
        self.graph_base_url = "https://graph.microsoft.com/v1.0"
        
        # Create credential for token acquisition
        self.credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
    
    def _get_access_token(self) -> str:
        """Get access token for Microsoft Graph API"""
        token = self.credential.get_token("https://graph.microsoft.com/.default")
        return token.token
    
    def get_files_metadata(self) -> List[Dict[str, Any]]:
        """
        Get metadata of all PDF files in OneDrive folder
        
        Returns:
            List of file metadata dicts with id, name, lastModifiedDateTime, webUrl
        """
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        files = []
        url = f"{self.graph_base_url}/drives/{self.drive_id}/root:/{self.folder_path}:/children"
        
        # Handle pagination
        while url:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get('value', []):
                # Only include PDF files
                if item['name'].lower().endswith('.pdf'):
                    files.append({
                        'id': item['id'],
                        'name': item['name'],
                        'lastModifiedDateTime': item.get('lastModifiedDateTime'),
                        'size': item.get('size', 0),
                        'webUrl': item.get('webUrl', ''),
                        'downloadUrl': item.get('@microsoft.graph.downloadUrl', '')
                    })
            
            # Get next page URL
            url = data.get('@odata.nextLink')
        
        return files
    
    def download_file_bytes(self, file_id: str) -> bytes:
        """
        Download file content as bytes
        
        Args:
            file_id: OneDrive file ID
            
        Returns:
            File content as bytes
        """
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        url = f"{self.graph_base_url}/drives/{self.drive_id}/items/{file_id}/content"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.content
    
    def send_to_ocr(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Send PDF to OCR service and get extracted text
        
        Args:
            file_bytes: PDF file content as bytes
            filename: Original filename
            
        Returns:
            OCR result with extracted text
        """
        # Prepare multipart/form-data request
        files = {
            'file': (filename, file_bytes, 'application/pdf')
        }
        
        # Optional parameters for OCR service
        data = {
            'lang': 'en',
            'page_range': 'all',
            'dpi': 300,
            'min_confidence': 0.5,
            'detect_headings': True,
            'force_ocr': True
        }
        
        headers = {}
        if self.ocr_api_key:
            headers['X-API-Key'] = self.ocr_api_key
        
        # Send to OCR service
        response = requests.post(
            self.ocr_service_url,
            files=files,
            data=data,
            headers=headers,
            timeout=300  # 5 minutes timeout for OCR processing
        )
        response.raise_for_status()
        
        return response.json()
    
    def check_file_updated(self, file_metadata: Dict[str, Any], 
                          last_sync_date: Optional[datetime] = None) -> bool:
        """
        Check if file has been updated since last sync
        
        Args:
            file_metadata: File metadata from get_files_metadata()
            last_sync_date: Last synchronization date. If None, checks if modified today.
            
        Returns:
            True if file is updated
        """
        # Parse OneDrive timestamp
        modified_str = file_metadata['lastModifiedDateTime']
        modified_date = datetime.fromisoformat(modified_str.replace('Z', '+00:00'))
        
        # Check if file was modified after last sync
        if last_sync_date and modified_date <= last_sync_date:
            return False
        
        # If no last_sync_date, check if modified today
        if not last_sync_date:
            today = datetime.now().date()
            return modified_date.date() == today
        
        return True
    
    def process_updated_file(self, file_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an updated PDF file through OCR
        
        Args:
            file_metadata: File metadata from get_files_metadata()
            
        Returns:
            Processed document with OCR text and metadata
        """
        # Download PDF file
        file_bytes = self.download_file_bytes(file_metadata['id'])
        
        # Send to OCR service
        ocr_result = self.send_to_ocr(file_bytes, file_metadata['name'])
        
        # Create document structure
        document = {
            'filename': file_metadata['name'],
            'file_id': file_metadata['id'],
            'document_link': file_metadata['webUrl'],
            'download_url': file_metadata.get('downloadUrl', ''),
            'lastModifiedDateTime': file_metadata['lastModifiedDateTime'],
            'size': file_metadata['size'],
            'ocr_text': ocr_result.get('text', ''),
            'ocr_metadata': ocr_result.get('metadata', {}),
            'processed_at': datetime.now().isoformat()
        }
        
        return document
    
    def sync_documents(self, last_sync_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Sync all updated SOP PDF documents from OneDrive
        
        Args:
            last_sync_date: Last synchronization date. If None, syncs files modified today.
            
        Returns:
            List of processed documents with OCR text
        """
        files_metadata = self.get_files_metadata()
        updated_documents = []
        
        for file_meta in files_metadata:
            if self.check_file_updated(file_meta, last_sync_date):
                try:
                    document = self.process_updated_file(file_meta)
                    updated_documents.append(document)
                except Exception as e:
                    print(f"Error processing {file_meta['name']}: {e}")
                    continue
        
        return updated_documents
    
    @staticmethod
    def extract_document_id(filename: str) -> str:
        """
        Extract document ID from filename (remove .pdf extension)
        
        Args:
            filename: PDF filename
            
        Returns:
            Document ID
        """
        return filename.replace('.pdf', '').replace('.PDF', '')
