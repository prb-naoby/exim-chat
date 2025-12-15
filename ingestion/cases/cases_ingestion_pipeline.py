"""
Cases Q&A Ingestion Pipeline

Workflow:
1. Download Excel file from OneDrive AI/Cases folder
2. Parse rows (Case No, Date, Question, Answer)
3. Create embeddings for each Q&A pair
4. Upsert to Qdrant with hybrid vectors (dense + sparse)
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo

from .cases_onedrive_sync import CasesOneDriveSync
from .cases_qdrant_store import CasesQdrantStore
from ingestion.vectorizer import Vectorizer


class CasesIngestionPipeline:
    """Pipeline for Cases Q&A ingestion from Excel spreadsheet"""
    
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        user_id: str,  # This is actually the drive_id
        folder_path: str,
        qdrant_url: str,
        qdrant_api_key: str,
        collection_name: str,
        gemini_api_key: str,
        embedding_model: str = 'models/text-embedding-004',
        vector_size: int = 768,
        batch_size: int = 50
    ):
        # Initialize OneDrive sync
        self.onedrive = CasesOneDriveSync(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            user_id=user_id,
            folder_path=folder_path
        )
        
        # Initialize Qdrant store
        self.qdrant = CasesQdrantStore(
            url=qdrant_url,
            api_key=qdrant_api_key,
            collection_name=collection_name,
            vector_size=vector_size
        )
        
        # Initialize vectorizer
        self.vectorizer = Vectorizer(
            model_name=embedding_model,
            api_key=gemini_api_key
        )
        
        self.batch_size = batch_size
        self.collection_name = collection_name
        
    def sync_and_upsert(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Full pipeline: Download Excel -> Parse -> Vectorize -> Upsert
        
        Args:
            dry_run: If True, don't actually upsert to Qdrant
            
        Returns:
            Summary of operations
        """
        summary = {
            'upserted': [],
            'skipped': [],
            'errors': [],
            'timestamp': datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(),
            'dry_run': dry_run
        }
        
        # Step 1: Check if file has been modified since last sync
        print("Checking Excel file metadata...")
        file_metadata = self.onedrive.get_excel_file_metadata()
        
        if not file_metadata:
            summary['errors'].append({'error': 'No Excel file found in AI/Cases folder'})
            return summary
        
        onedrive_last_modified = file_metadata.get('lastModifiedDateTime', '')
        print(f"Excel file: {file_metadata['name']}, LastModified: {onedrive_last_modified}")
        
        # Check Qdrant for existing data
        qdrant_last_modified = self.qdrant.get_file_last_modified()
        
        if qdrant_last_modified and onedrive_last_modified <= qdrant_last_modified:
            print(f"Excel file is up to date (Qdrant: {qdrant_last_modified})")
            summary['skipped'].append({
                'filename': file_metadata['name'],
                'reason': 'Already up to date'
            })
            return summary
        
        # Step 2: Create collection if needed
        print("Ensuring Qdrant collection exists...")
        self.qdrant.create_collection()
        
        # Step 3: Download and parse Excel
        print("Downloading Excel file...")
        df = self.onedrive.download_excel_as_dataframe()
        
        if df is None or df.empty:
            summary['errors'].append({'error': 'Failed to download or parse Excel file'})
            return summary
        
        summary['total_rows'] = len(df)
        print(f"Downloaded {len(df)} rows from Excel")
        
        # Step 4: Process each row
        print(f"Processing rows...")
        
        # Expected columns: NO, DATE, QUESTION, ANSWER
        required_cols = ['NO', 'DATE', 'QUESTION', 'ANSWER']
        columns = [str(c).upper().strip() for c in df.columns.tolist()]
        
        # Check if all required columns exist
        missing = [c for c in required_cols if c not in columns]
        if missing:
            # Try case-insensitive match
            df.columns = [str(c).upper().strip() for c in df.columns]
        
        print(f"Excel columns: {df.columns.tolist()}")
        
        processed = 0
        for idx, row in df.iterrows():
            try:
                # Extract fields using exact column names
                case_no = int(row.get('NO', idx + 1))
                date_val = row.get('DATE', '')
                question = str(row.get('QUESTION', '')).strip()
                answer = str(row.get('ANSWER', '')).strip()
                
                # Convert date to string
                if hasattr(date_val, 'strftime'):
                    date_str = date_val.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_val)
                
                # Skip empty rows
                if not question or not answer or question == 'nan' or answer == 'nan':
                    continue
                
                # Create search text for embedding
                search_text = f"Q: {question} A: {answer}"
                
                # Vectorize
                dense_vector = self.vectorizer.vectorize_text(search_text)
                
                # Upsert to Qdrant
                if not dry_run:
                    self.qdrant.upsert_case(
                        case_no=case_no,
                        date=date_str,
                        question=question,
                        answer=answer,
                        dense_vector=dense_vector,
                        file_last_modified=onedrive_last_modified
                    )
                
                summary['upserted'].append({
                    'case_no': case_no,
                    'question': question[:50] + '...' if len(question) > 50 else question
                })
                processed += 1
                
                if processed % 10 == 0:
                    print(f"  Processed {processed} cases...")
                    
            except Exception as e:
                summary['errors'].append({
                    'row': idx,
                    'error': str(e)
                })
        
        print(f"\nProcessing complete! {processed} cases upserted.")
        summary['total_processed'] = processed
        
        return summary
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search cases by query"""
        query_vector = self.vectorizer.vectorize_text(query)
        return self.qdrant.search_hybrid(
            query_dense=query_vector,
            query_text=query,
            limit=top_k
        )
