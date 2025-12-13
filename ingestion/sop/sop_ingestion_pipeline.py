"""
Complete SOP ingestion pipeline
Workflow:
1. Get PDF files metadata from OneDrive
2. Check against Qdrant (skip if up-to-date)
3. Download PDF → OCR → Parse with LLM
4. Create hybrid vectors (dense + sparse)
5. Upsert to Qdrant
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
import os

from .sop_parser import SOPParser
from .sop_qdrant_store import SOPQdrantStore
from .sop_onedrive_sync import SOPOneDriveSync
from ..vectorizer import Vectorizer


class SOPIngestionPipeline:
    """Complete pipeline for SOP PDF ingestion"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 drive_id: str, folder_path: str,
                 qdrant_url: str, qdrant_api_key: str,
                 embedding_model: str, gemini_api_key: str,
                 llm_model: str, vector_size: int,
                 skip_qdrant_init: bool = False):
        """
        Initialize SOP ingestion pipeline
        
        Args:
            tenant_id: Azure AD tenant ID
            client_id: Azure AD client ID  
            client_secret: Azure AD client secret
            drive_id: OneDrive drive ID
            folder_path: SOP folder path
            qdrant_url: Qdrant server URL
            qdrant_api_key: Qdrant API key
            embedding_model: Gemini embedding model
            gemini_api_key: Gemini API key
            llm_model: Gemini LLM model for parsing PDFs
            vector_size: Vector dimension
            skip_qdrant_init: Skip Qdrant initialization for dry runs
        """
        # Initialize OneDrive sync
        self.onedrive = SOPOneDriveSync(tenant_id, client_id, client_secret, drive_id, folder_path)
        
        # Initialize Gemini parser (no OCR needed - Gemini processes PDFs directly)
        self.parser = SOPParser(llm_model, gemini_api_key)
        
        # Initialize vectorizer
        self.vectorizer = Vectorizer(
            model_name=embedding_model,
            api_key=gemini_api_key
        )
        
        # Initialize Qdrant
        if not skip_qdrant_init:
            self.qdrant = SOPQdrantStore(url=qdrant_url, api_key=qdrant_api_key)
            self.qdrant.create_collection(vector_size=vector_size)
        else:
            self.qdrant = None
    
    def sync_and_upsert(self, last_sync_date: Optional[datetime] = None,
                       dry_run: bool = False, batch_size: int = None) -> Dict[str, Any]:
        """
        Full pipeline: sync PDFs → OCR → Parse → Vectorize → Upsert
        
        Args:
            last_sync_date: Last sync date (None = sync all)
            dry_run: If True, don't upsert to Qdrant
            batch_size: Batch size from env or parameter
            
        Returns:
            Summary of operations
        """
        # Get batch size
        if batch_size is None:
            batch_size = int(os.getenv('BATCH_SIZE', '50'))
        
        summary = {
            'upserted': [],
            'skipped': [],
            'errors': [],
            'timestamp': datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(),
            'dry_run': dry_run
        }
        
        # Step 1: Get PDF metadata from OneDrive
        print("Fetching PDF list from OneDrive...")
        try:
            all_files_metadata = self.onedrive.get_files_metadata()
            print(f"Found {len(all_files_metadata)} PDF files on OneDrive")
            
            # Filter by date if provided
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
        
        # Step 2: Process in batches
        print(f"\nProcessing files in batches of {batch_size}...")
        print(f"dry_run = {dry_run}")
        print(f"self.qdrant = {self.qdrant}")
        
        total_processed = 0
        total_downloaded = 0
        
        for batch_start in range(0, len(all_files_metadata), batch_size):
            batch_end = min(batch_start + batch_size, len(all_files_metadata))
            batch_files = all_files_metadata[batch_start:batch_end]
            
            print(f"\n--- Batch {batch_start//batch_size + 1}: Checking files {batch_start+1} to {batch_end} ---")
            
            # Check which files need processing
            files_to_process = []
            for file_meta in batch_files:
                try:
                    filename = file_meta['name']
                    onedrive_last_modified = file_meta['lastModifiedDateTime']
                    
                    # Check Qdrant
                    qdrant_last_modified = None
                    if self.qdrant:
                        # Use filename as doc_no for now (will be updated after parsing)
                        qdrant_last_modified = self.qdrant.get_last_modified('', filename)
                    
                    # Compare timestamps
                    if qdrant_last_modified:
                        if onedrive_last_modified <= qdrant_last_modified:
                            summary['skipped'].append({
                                'filename': filename,
                                'reason': 'Already up to date',
                                'qdrant_modified': qdrant_last_modified,
                                'onedrive_modified': onedrive_last_modified
                            })
                            continue
                    
                    files_to_process.append(file_meta)
                    
                except Exception as e:
                    print(f"  Error checking {file_meta.get('name')}: {e}")
            
            if not files_to_process:
                print(f"  All files in this batch are up-to-date, skipping...")
                continue
            
            print(f"  Need to process: {len(files_to_process)}/{len(batch_files)} files")
            
            # Process each file
            for i, file_meta in enumerate(files_to_process, 1):
                total_processed += 1
                filename = file_meta['name']
                
                try:
                    if total_processed <= 3:
                        print(f"\n  DEBUG Document {total_processed}: {filename}")
                    
                    # Download PDF
                    if total_processed <= 3:
                        print(f"    Downloading PDF...")
                    pdf_content = self.onedrive.get_file_content(file_meta['id'])
                    total_downloaded += 1
                    
                    # Parse PDF directly with Gemini (no OCR needed)
                    if total_processed <= 3:
                        print(f"    Parsing PDF with Gemini...")
                    parsed_data = self.parser.parse_sop_pdf(pdf_content, filename)
                    
                    # Create search text (store full OCR-like text from parsed fields)
                    full_text = f"Title: {parsed_data.get('sop_title', '')}\n\nTujuan: {parsed_data.get('tujuan', '')}\n\nUraian: {parsed_data.get('uraian', '')}\n\nDokumen: {parsed_data.get('dokumen', '')}"
                    search_text = f"SOP: {parsed_data.get('sop_title', '')}. Type: {parsed_data.get('type', '')}. Tujuan: {parsed_data.get('tujuan', '')}. Uraian: {parsed_data.get('uraian', '')}. Dokumen: {parsed_data.get('dokumen', '')}"
                    
                    # Vectorize
                    if total_processed <= 3:
                        print(f"    Vectorizing...")
                    embedding = self.vectorizer.vectorize_text(search_text)
                    
                    # Upsert to Qdrant
                    if not dry_run and self.qdrant:
                        if total_processed <= 3:
                            print(f"    Upserting to Qdrant...")
                        self.qdrant.upsert_document(
                            doc_no=parsed_data.get('doc_no', ''),
                            filename=filename,
                            dense_embedding=embedding,
                            parsed_data=parsed_data,
                            full_text=full_text,
                            file_metadata=file_meta
                        )
                        if total_processed <= 3:
                            print(f"    Upsert completed!")
                        
                        summary['upserted'].append({
                            'filename': filename,
                            'sop_title': parsed_data.get('sop_title', ''),
                            'doc_no': parsed_data.get('doc_no', ''),
                            'is_new': True
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
                        'filename': filename,
                        'error': str(e)
                    })
            
            print(f"  Batch complete. Total processed: {total_processed}/{len(all_files_metadata)}")
        
        print(f"\nProcessing complete!")
        return summary
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search SOP documents with hybrid search
        
        Args:
            query: Search query
            top_k: Number of results
            
        Returns:
            List of search results
        """
        if not self.qdrant:
            raise Exception("Qdrant not initialized")
        
        # Vectorize query
        query_embedding = self.vectorizer.vectorize_text(query)
        
        # Hybrid search
        results = self.qdrant.search_hybrid(
            query_dense=query_embedding,
            query_text=query,
            top_k=top_k
        )
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        if not self.qdrant:
            raise Exception("Qdrant not initialized")
        return self.qdrant.get_collection_stats()
