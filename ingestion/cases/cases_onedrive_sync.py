"""
OneDrive Sync for Cases Q&A Excel File

Handles downloading Excel spreadsheet from OneDrive folder AI/Cases
"""

import os
import io
from typing import Dict, Any, Optional
from datetime import datetime
import requests
from azure.identity import ClientSecretCredential
import pandas as pd


class CasesOneDriveSync:
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        user_id: str,
        folder_path: str = "AI/Cases"
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_id = user_id
        self.folder_path = folder_path
        
        # Get access token
        self.credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
    def _get_access_token(self) -> str:
        """Get access token for Microsoft Graph API"""
        token = self.credential.get_token("https://graph.microsoft.com/.default")
        return token.token
    
    def get_excel_file_metadata(self) -> Optional[Dict[str, Any]]:
        """Get metadata of the Excel file in AI/Cases folder"""
        access_token = self._get_access_token()
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Get folder ID
        folder_url = f"https://graph.microsoft.com/v1.0/users/{self.user_id}/drive/root:/{self.folder_path}"
        folder_response = requests.get(folder_url, headers=headers)
        
        if folder_response.status_code != 200:
            print(f"Error accessing folder: {folder_response.status_code}")
            print(folder_response.text)
            return None
            
        folder_id = folder_response.json()['id']
        
        # List files in folder
        files_url = f"https://graph.microsoft.com/v1.0/users/{self.user_id}/drive/items/{folder_id}/children"
        files_response = requests.get(files_url, headers=headers)
        
        if files_response.status_code != 200:
            print(f"Error listing files: {files_response.status_code}")
            return None
        
        files = files_response.json().get('value', [])
        
        # Find Excel file (.xlsx or .xls)
        for file in files:
            filename = file.get('name', '').lower()
            if filename.endswith('.xlsx') or filename.endswith('.xls'):
                return {
                    'id': file['id'],
                    'name': file['name'],
                    'size': file.get('size', 0),
                    'lastModifiedDateTime': file.get('lastModifiedDateTime'),
                    'webUrl': file.get('webUrl', '')
                }
        
        print("No Excel file found in AI/Cases folder")
        return None
    
    def download_excel_as_dataframe(self) -> Optional[pd.DataFrame]:
        """Download Excel file and return as pandas DataFrame"""
        file_metadata = self.get_excel_file_metadata()
        
        if not file_metadata:
            return None
        
        print(f"Downloading Excel file: {file_metadata['name']}")
        
        access_token = self._get_access_token()
        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Download file content
        download_url = f"https://graph.microsoft.com/v1.0/users/{self.user_id}/drive/items/{file_metadata['id']}/content"
        response = requests.get(download_url, headers=headers)
        
        if response.status_code != 200:
            print(f"Error downloading file: {response.status_code}")
            return None
        
        # Read Excel from bytes
        excel_bytes = io.BytesIO(response.content)
        
        try:
            df = pd.read_excel(excel_bytes)
            print(f"Successfully loaded {len(df)} rows from Excel")
            return df
        except Exception as e:
            print(f"Error reading Excel: {str(e)}")
            return None
    
    def get_file_last_modified(self) -> Optional[datetime]:
        """Get last modified datetime of the Excel file"""
        file_metadata = self.get_excel_file_metadata()
        
        if not file_metadata:
            return None
        
        last_modified_str = file_metadata.get('lastModifiedDateTime')
        if last_modified_str:
            return datetime.fromisoformat(last_modified_str.replace('Z', '+00:00'))
        
        return None
