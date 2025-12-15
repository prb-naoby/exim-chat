"""
Complete ingestion pipeline for INSW documents
Workflow:
1. Sync updated documents from OneDrive (check lastModifiedDateTime)
2. Vectorize documents based on hs_parent_uraian + hs_code
3. Compare with current Qdrant store by hs_code
4. Upsert new/updated documents to Qdrant
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os

from .onedrive_sync import OneDriveSync
from .vectorizer import Vectorizer
from .qdrant_store import QdrantStore


class IngestionPipeline:
    """End-to-end pipeline for INSW document ingestion"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 drive_id: str, folder_path: str,
                 qdrant_url: str, qdrant_api_key: str,
                 embedding_model: str = 'models/text-embedding-004',
                 gemini_api_key: str = None,
                 vector_size: int = 768,
                 skip_qdrant_init: bool = False):
        """
        Initialize ingestion pipeline
        
        Args:
            tenant_id: Microsoft Entra tenant ID
            client_id: Microsoft Entra app client ID
            client_secret: Microsoft Entra app client secret
            drive_id: OneDrive drive ID
            folder_path: Folder path within drive (e.g., 'AI/INSW')
            qdrant_url: Qdrant server URL
            qdrant_api_key: Qdrant API key
            embedding_model: Gemini embedding model name
            gemini_api_key: Google AI Studio API key (required)
            vector_size: Dimension of embedding vectors (768 for text-embedding-004)
            skip_qdrant_init: Skip Qdrant initialization (useful for dry runs when server is unavailable)
        """
        self.onedrive = OneDriveSync(tenant_id, client_id, client_secret, drive_id, folder_path)
        self.vectorizer = Vectorizer(
            model_name=embedding_model,
            api_key=gemini_api_key
        )
        
        # Only initialize Qdrant if not skipping
        if not skip_qdrant_init:
            self.qdrant = QdrantStore(url=qdrant_url, api_key=qdrant_api_key)
            # Create collection if needed
            self.qdrant.create_collection(vector_size=vector_size)
        else:
            self.qdrant = None
    
    def sync_and_upsert(self, last_sync_date: Optional[datetime] = None, dry_run: bool = False, batch_size: int = None) -> Dict[str, Any]:
        """
        Full pipeline: sync from OneDrive -> vectorize -> upsert to Qdrant (in batches)
        
        Args:
            last_sync_date: Last sync date. If None, syncs files modified today.
            dry_run: If True, preview operations without making changes to Qdrant
            batch_size: Number of files to process in each batch. If None, reads from env BATCH_SIZE
            
        Returns:
            Summary of operations (upserted, skipped, errors)
        """
        # Get batch size from parameter or environment
        if batch_size is None:
            batch_size = int(os.getenv('BATCH_SIZE', '50'))
        
        summary = {
            'upserted': [],
            'skipped': [],
            'errors': [],
            'timestamp': datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(),
            'dry_run': dry_run
        }
        
        # Step 1: Get ALL file metadata from OneDrive (still need full list for pagination)
        print("Fetching file list from OneDrive...")
        try:
            all_files_metadata = self.onedrive.get_files_metadata()
            print(f"Found {len(all_files_metadata)} files on OneDrive")
            
            # Filter files by last_sync_date if provided
            if last_sync_date:
                filtered_files = []
                for file_meta in all_files_metadata:
                    modified_str = file_meta['lastModifiedDateTime']
                    modified_date = datetime.fromisoformat(modified_str.replace('Z', '+00:00'))
                    if modified_date > last_sync_date:
                        filtered_files.append(file_meta)
                all_files_metadata = filtered_files
                print(f"After filtering by date: {len(all_files_metadata)} files to process")
            
            summary['total_files'] = len(all_files_metadata)
        except Exception as e:
            summary['errors'].append({'error': f"Failed to get file metadata: {str(e)}"})
            return summary
        
        # Step 2: Process files in batches
        print(f"\nProcessing files in batches of {batch_size}...")
        print(f"dry_run = {dry_run}")
        print(f"self.qdrant = {self.qdrant}")
        
        total_processed = 0
        total_downloaded = 0
        
        for batch_start in range(0, len(all_files_metadata), batch_size):
            batch_end = min(batch_start + batch_size, len(all_files_metadata))
            batch_files = all_files_metadata[batch_start:batch_end]
            
            print(f"\n--- Batch {batch_start//batch_size + 1}: Checking files {batch_start+1} to {batch_end} ---")
            
            # First, check which files need updating (compare with Qdrant)
            files_to_download = []
            for file_meta in batch_files:
                try:
                    # Extract HS code from filename
                    filename = file_meta['name']
                    hs_code = filename.replace('.json', '').strip()
                    onedrive_last_modified = file_meta['lastModifiedDateTime']
                    
                    # Check if exists in Qdrant
                    qdrant_last_modified = None
                    if self.qdrant:
                        qdrant_last_modified = self.qdrant.get_last_modified(hs_code)
                    
                    # Compare timestamps
                    if qdrant_last_modified:
                        if onedrive_last_modified <= qdrant_last_modified:
                            # Skip - already up to date
                            summary['skipped'].append({
                                'hs_code': hs_code,
                                'reason': 'Already up to date',
                                'qdrant_modified': qdrant_last_modified,
                                'onedrive_modified': onedrive_last_modified
                            })
                            continue
                    
                    # Need to download and process this file
                    files_to_download.append(file_meta)
                    
                except Exception as e:
                    print(f"  Error checking {file_meta.get('name')}: {e}")
            
            if not files_to_download:
                print(f"  All files in this batch are up-to-date, skipping...")
                continue
            
            print(f"  Need to download: {len(files_to_download)}/{len(batch_files)} files")
            
            # Download only the files that need updating
            batch_documents = []
            for file_meta in files_to_download:
                try:
                    content = self.onedrive.get_file_content(file_meta['id'])
                    content['_file_metadata'] = {
                        'name': file_meta['name'],
                        'lastModifiedDateTime': file_meta['lastModifiedDateTime'],
                        'size': file_meta['size']
                    }
                    batch_documents.append(content)
                except Exception as e:
                    print(f"  Error downloading {file_meta.get('name')}: {e}")
                    summary['errors'].append({
                        'document': file_meta.get('name'),
                        'error': f"Download failed: {str(e)}"
                    })
            
            # Download only the files that need updating
            batch_documents = []
            for file_meta in files_to_download:
                try:
                    content = self.onedrive.get_file_content(file_meta['id'])
                    content['_file_metadata'] = {
                        'name': file_meta['name'],
                        'lastModifiedDateTime': file_meta['lastModifiedDateTime'],
                        'size': file_meta['size']
                    }
                    batch_documents.append(content)
                    total_downloaded += 1
                except Exception as e:
                    print(f"  Error downloading {file_meta.get('name')}: {e}")
                    summary['errors'].append({
                        'document': file_meta.get('name'),
                        'error': f"Download failed: {str(e)}"
                    })
            
            print(f"  Downloaded {len(batch_documents)} files (total so far: {total_downloaded})")
            
            # Process each document in batch
            for i, document in enumerate(batch_documents, 1):
                total_processed += 1
                
                try:
                    # Extract HS code and file metadata
                    filename = document.get('_file_metadata', {}).get('name', '')
                    hs_code = OneDriveSync.extract_hs_code(document, filename)
                    onedrive_last_modified = document.get('_file_metadata', {}).get('lastModifiedDateTime', '')
                    
                    if total_processed <= 3:  # Debug first 3 documents overall
                        print(f"\n  DEBUG Document {total_processed}:")
                        print(f"    HS Code: {hs_code}")
                        print(f"    OneDrive LastModified: {onedrive_last_modified}")
                    
                    # We already checked Qdrant before downloading, so this is a new/updated document
                    if total_processed <= 3:
                        print(f"    Processing as NEW or UPDATED document")
                    
                    # Vectorize the document
                    if total_processed <= 3:
                        print(f"    Vectorizing...")
                    vectorized_doc = self.vectorizer.vectorize_document(document)
                
                    # Upsert to Qdrant (skip if dry_run or no Qdrant connection)
                    if not dry_run and self.qdrant:
                        if total_processed <= 3:
                            print(f"    Calling qdrant.upsert_document...")
                        self.qdrant.upsert_document(
                            hs_code=hs_code,
                            embedding=vectorized_doc['embedding'],
                            document=document,
                            last_modified=onedrive_last_modified
                        )
                        if total_processed <= 3:
                            print(f"    Upsert completed!")
                        summary['upserted'].append({
                            'hs_code': hs_code,
                            'search_text': vectorized_doc.get('search_text', ''),
                            'is_new': True,  # We already filtered, so all are new/updated
                            'onedrive_modified': onedrive_last_modified
                        })
                    elif dry_run:
                        if total_processed <= 3:
                            print(f"    SKIPPING UPSERT: dry_run=True")
                    elif not self.qdrant:
                        if total_processed <= 3:
                            print(f"    SKIPPING UPSERT: qdrant is None")
                    
                except Exception as e:
                    if total_processed <= 3:
                        print(f"    ERROR: {e}")
                        import traceback
                        traceback.print_exc()
                    summary['errors'].append({
                        'document': filename,
                        'error': str(e)
                    })
            
            # Clear batch from memory
            batch_documents.clear()
            print(f"  Batch complete. Total processed: {total_processed}/{len(all_files_metadata)}")
        
        print(f"\nProcessing complete!")
        return summary
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar INSW documents
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of search results
        """
        # Vectorize query
        query_embedding = self.vectorizer.vectorize_query(query)
        
        # Search in Qdrant
        results = self.qdrant.search_similar(
            embedding=query_embedding,
            top_k=top_k,
            score_threshold=0.0
        )
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get pipeline statistics
        
        Returns:
            Statistics about the Qdrant store
        """
        return self.qdrant.get_collection_stats()
    
    @staticmethod
    def _documents_equal(doc1: Dict[str, Any], doc2: Dict[str, Any]) -> bool:
        """
        Compare two documents for equality (ignoring embeddings and metadata)
        
        Args:
            doc1: First document
            doc2: Second document
            
        Returns:
            True if documents are equal
        """
        # Remove non-comparable fields
        d1 = {k: v for k, v in doc1.items() 
              if k not in ['embedding', 'search_text', '_file_metadata']}
        d2 = {k: v for k, v in doc2.items() 
              if k not in ['embedding', 'search_text', '_file_metadata']}
        
        return json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)
