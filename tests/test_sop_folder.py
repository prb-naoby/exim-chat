"""Test script to check SOP folder contents"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from azure.identity import ClientSecretCredential
from dotenv import load_dotenv

load_dotenv()

# Get credentials
tenant_id = os.getenv('MS_TENANT_ID')
client_id = os.getenv('MS_CLIENT_ID')
client_secret = os.getenv('MS_CLIENT_SECRET')
drive_id = os.getenv('ONEDRIVE_DRIVE_ID')
folder_path = os.getenv('SOP_FOLDER_PATH')

print("="*80)
print("SOP FOLDER TEST")
print("="*80)
print(f"Folder Path: {folder_path}")
print(f"Drive ID: {drive_id}")
print()

# Get access token
print("Getting access token...")
credential = ClientSecretCredential(
    tenant_id=tenant_id,
    client_id=client_id,
    client_secret=client_secret
)
token = credential.get_token("https://graph.microsoft.com/.default")
headers = {"Authorization": f"Bearer {token.token}"}
print("✓ Access token obtained")
print()

# List folder contents
graph_base_url = "https://graph.microsoft.com/v1.0"
url = f"{graph_base_url}/drives/{drive_id}/root:/{folder_path}:/children"

print(f"Fetching folder contents...")
print(f"URL: {url}")
print()

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    items = data.get('value', [])
    print(f"Total items in folder: {len(items)}")
    print()
    
    # Categorize files
    pdf_files = []
    other_files = []
    folders = []
    
    for item in items:
        name = item.get('name', 'Unknown')
        if 'folder' in item:
            folders.append(name)
        elif name.lower().endswith('.pdf'):
            pdf_files.append({
                'name': name,
                'size': item.get('size', 0),
                'modified': item.get('lastModifiedDateTime', 'Unknown')
            })
        else:
            other_files.append(name)
    
    # Display results
    print(f"PDF Files: {len(pdf_files)}")
    if pdf_files:
        print("PDF files found:")
        for i, pdf in enumerate(pdf_files[:10], 1):
            size_mb = pdf['size'] / (1024*1024)
            print(f"  {i}. {pdf['name']}")
            print(f"     Size: {size_mb:.2f} MB")
            print(f"     Modified: {pdf['modified']}")
        if len(pdf_files) > 10:
            print(f"  ... and {len(pdf_files) - 10} more PDF files")
    else:
        print("  No PDF files found!")
    print()
    
    print(f"Folders: {len(folders)}")
    if folders:
        print("Folders found:")
        for folder in folders[:5]:
            print(f"  - {folder}")
        if len(folders) > 5:
            print(f"  ... and {len(folders) - 5} more folders")
    print()
    
    print(f"Other Files: {len(other_files)}")
    if other_files:
        print("Other files found:")
        for file in other_files[:10]:
            print(f"  - {file}")
        if len(other_files) > 10:
            print(f"  ... and {len(other_files) - 10} more files")

except requests.exceptions.HTTPError as e:
    print(f"HTTP Error: {e}")
    print(f"Response: {e.response.text if hasattr(e, 'response') else 'N/A'}")
except Exception as e:
    print(f"Error: {e}")
