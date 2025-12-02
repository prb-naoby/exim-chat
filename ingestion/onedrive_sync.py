"""
OneDrive synchronization module for fetching and comparing INSW documents
Uses Microsoft Graph SDK
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import requests
from azure.identity import ClientSecretCredential


class OneDriveSync:
    """Sync documents from OneDrive based on modification date"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 drive_id: str, folder_path: str):
        """
        Initialize OneDrive sync
        
        Args:
            tenant_id: Microsoft Entra tenant ID
            client_id: Microsoft Entra app client ID
            client_secret: Microsoft Entra app client secret
            drive_id: OneDrive drive ID
            folder_path: Folder path within the drive (e.g., 'AI/INSW')
        """
        self.drive_id = drive_id
        self.folder_path = folder_path
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
        Get metadata of all files in OneDrive folder
        
        Returns:
            List of file metadata dicts with id, name, lastModifiedDateTime
        """
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        files = []
        url = f"{self.graph_base_url}/drives/{self.drive_id}/root:/{self.folder_path}:/children"
        
        page = 0
        # Handle pagination
        while url:
            page += 1
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get('value', []):
                # Only include JSON files (INSW documents)
                if item['name'].endswith('.json'):
                    files.append({
                        'id': item['id'],
                        'name': item['name'],
                        'lastModifiedDateTime': item.get('lastModifiedDateTime'),
                        'size': item.get('size', 0)
                    })
            
            # Get next page URL
            url = data.get('@odata.nextLink')
            
            if url:
                print(f"  Fetched page {page}: {len(files)} files so far...")
        
        print(f"  Total files found: {len(files)}")
        return files
    
    def get_file_content(self, file_id: str) -> Dict[str, Any]:
        """
        Download file content from OneDrive
        
        Args:
            file_id: OneDrive file ID
            
        Returns:
            Parsed JSON content
        """
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        url = f"{self.graph_base_url}/drives/{self.drive_id}/items/{file_id}/content"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Parse JSON
        return response.json()
    
    def download_file_if_updated(self, file_metadata: Dict[str, Any], 
                                  last_sync_date: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Download file if it has been modified since last sync
        
        Args:
            file_metadata: File metadata from get_files_metadata()
            last_sync_date: Last synchronization date. If None, downloads all files.
            
        Returns:
            File content if updated, None otherwise
        """
        # Parse OneDrive timestamp
        modified_str = file_metadata['lastModifiedDateTime']
        modified_date = datetime.fromisoformat(modified_str.replace('Z', '+00:00'))
        
        # If last_sync_date provided, check if file was modified after it
        if last_sync_date:
            if modified_date <= last_sync_date:
                return None
        else:
            # If no last_sync_date, only sync files modified today
            today = datetime.now().date()
            if modified_date.date() != today:
                return None
        
        # Download file
        content = self.get_file_content(file_metadata['id'])
        content['_file_metadata'] = {
            'name': file_metadata['name'],
            'lastModifiedDateTime': modified_str,
            'size': file_metadata['size']
        }
        
        return content
    
    def sync_documents(self, last_sync_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Sync all updated documents from OneDrive
        
        Args:
            last_sync_date: Last synchronization date. If None, syncs all files modified today.
            
        Returns:
            List of updated document contents
        """
        files_metadata = self.get_files_metadata()
        updated_documents = []
        
        print(f"Found {len(files_metadata)} files, checking for updates...")
        
        for i, file_meta in enumerate(files_metadata, 1):
            content = self.download_file_if_updated(file_meta, last_sync_date)
            if content:
                updated_documents.append(content)
                if i % 10 == 0:  # Progress update every 10 files
                    print(f"  Processed {i}/{len(files_metadata)} files, {len(updated_documents)} updated so far...")
        
        print(f"Completed: {len(updated_documents)} documents synced from OneDrive")
        return updated_documents
    
    @staticmethod
    def extract_hs_code(document: Dict[str, Any], filename: str) -> str:
        """
        Extract HS code from document or filename
        
        Args:
            document: Document content
            filename: Filename of the document
            
        Returns:
            HS code string
        """
        # First try to get from document
        hs_code = document.get('hs_code', '').strip()
        
        # If empty or missing, try from filename (expected format: {hs_code}.json)
        if not hs_code:
            hs_code = filename.replace('.json', '')
        
        return hs_code
    
    @staticmethod
    def create_search_text(document: Dict[str, Any]) -> str:
        """
        Create search text from INSW document
        Concatenates hs_parent_uraian list items and hs_code
        
        Args:
            document: INSW document content
            
        Returns:
            Combined search text
        """
        # Get hs_parent_uraian (can be list or string)
        hs_parent = document.get('hs_parent_uraian', [])
        if isinstance(hs_parent, list):
            hs_parent_text = ' '.join(hs_parent)
        else:
            hs_parent_text = str(hs_parent)
        
        # Get hs_code
        hs_code = document.get('hs_code', '')
        
        # Combine
        search_text = f"{hs_parent_text} {hs_code}".strip()
        return search_text
