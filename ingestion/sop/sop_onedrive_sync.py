"""
OneDrive synchronization for SOP PDF documents
"""
import requests
from azure.identity import ClientSecretCredential
from typing import List, Dict, Any
from datetime import datetime


class SOPOneDriveSync:
    """Sync SOP PDF documents from OneDrive"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 drive_id: str, folder_path: str):
        """
        Initialize OneDrive sync for SOP PDFs
        
        Args:
            tenant_id: Azure AD tenant ID
            client_id: Azure AD client ID
            client_secret: Azure AD client secret
            drive_id: OneDrive drive ID
            folder_path: Folder path containing SOP PDFs
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.drive_id = drive_id
        self.folder_path = folder_path
        self.graph_base_url = "https://graph.microsoft.com/v1.0"
        
        # Initialize credential
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
        
        page = 0
        # Handle pagination
        while url:
            page += 1
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
                        'webUrl': item.get('webUrl', '')
                    })
            
            # Get next page URL
            url = data.get('@odata.nextLink')
            
            if url:
                print(f"  Fetched page {page}: {len(files)} PDF files so far...")
        
        print(f"  Total PDF files found: {len(files)}")
        return files
    
    def get_file_content(self, file_id: str) -> bytes:
        """
        Download PDF file content from OneDrive
        
        Args:
            file_id: OneDrive file ID
            
        Returns:
            PDF content as bytes
        """
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        url = f"{self.graph_base_url}/drives/{self.drive_id}/items/{file_id}/content"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return response.content
