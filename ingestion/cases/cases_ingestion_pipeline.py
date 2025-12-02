"""
Cases Q&A Ingestion Pipeline

Orchestrates the complete workflow:
1. Download Excel from OneDrive
2. Parse rows (NO, DATE, QUESTION, ANSWER)
3. Create embeddings (dense + sparse)
4. Upsert to Qdrant
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
from google import genai

from .cases_onedrive_sync import CasesOneDriveSync
from .cases_qdrant_store import CasesQdrantStore


class CasesIngestionPipeline:
    def __init__(
        self,
        # OneDrive credentials
        tenant_id: str,
        client_id: str,
        client_secret: str,
        user_id: str,
        folder_path: str,
        # Qdrant credentials
        qdrant_url: str,
        qdrant_api_key: str,
        collection_name: str,
        # Gemini credentials
        gemini_api_key: str,
        embedding_model: str,
        vector_size: int,
        # Processing options
        batch_size: int = 50
    ):
        # Initialize components
        self.onedrive = CasesOneDriveSync(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            user_id=user_id,
            folder_path=folder_path
        )
        
        self.qdrant = CasesQdrantStore(
            url=qdrant_url,
            api_key=qdrant_api_key,
            collection_name=collection_name,
            vector_size=vector_size
        )
        
        # Initialize Gemini client for embeddings
        self.gemini_client = genai.Client(api_key=gemini_api_key)
        self.embedding_model = embedding_model
        self.batch_size = batch_size
        
        print(f"Initialized Cases Ingestion Pipeline")
        print(f"  Folder: {folder_path}")
        print(f"  Collection: {collection_name}")
        print(f"  Embedding Model: {embedding_model}")
        print(f"  Batch Size: {batch_size}")
    
    def _create_embedding(self, text: str) -> List[float]:
        """Create dense embedding using Gemini"""
        try:
            result = self.gemini_client.models.embed_content(
                model=self.embedding_model,
                contents=text
            )
            return result.embeddings[0].values
        except Exception as e:
            print(f"Error creating embedding: {str(e)}")
            raise
    
    def _validate_row(self, row: pd.Series) -> bool:
        """Validate that row has required columns"""
        required_cols = ['NO', 'DATE', 'QUESTION', 'ANSWER']
        
        for col in required_cols:
            if col not in row or pd.isna(row[col]):
                return False
        
        return True
    
    def sync_and_upsert(self) -> Dict[str, Any]:
        """
        Main ingestion workflow:
        1. Download Excel from OneDrive
        2. Parse and validate rows
        3. Create embeddings
        4. Upsert to Qdrant
        """
        stats = {
            'total_rows': 0,
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'start_time': datetime.utcnow().isoformat()
        }
        
        # Ensure collection exists
        self.qdrant.create_collection()
        
        # Download Excel file
        print("\n=== Downloading Excel file from OneDrive ===")
        df = self.onedrive.download_excel_as_dataframe()
        
        if df is None:
            print("Failed to download Excel file")
            return stats
        
        stats['total_rows'] = len(df)
        
        # Get file last modified timestamp
        file_last_modified = self.onedrive.get_file_last_modified()
        file_last_modified_str = file_last_modified.isoformat() if file_last_modified else datetime.utcnow().isoformat()
        
        # Check if we need to update (compare with Qdrant)
        qdrant_last_modified = self.qdrant.get_file_last_modified()
        
        if qdrant_last_modified and qdrant_last_modified == file_last_modified_str:
            print(f"Excel file not modified since last ingestion ({file_last_modified_str})")
            print("Skipping ingestion")
            return stats
        
        print(f"\n=== Processing {stats['total_rows']} cases ===")
        
        # Process rows
        for idx, row in df.iterrows():
            try:
                # Validate row
                if not self._validate_row(row):
                    print(f"Skipping invalid row {idx + 1}")
                    stats['skipped'] += 1
                    continue
                
                # Extract fields
                case_no = int(row['NO'])
                date = str(row['DATE']) if not pd.isna(row['DATE']) else ''
                question = str(row['QUESTION']).strip()
                answer = str(row['ANSWER']).strip()
                
                print(f"\nProcessing case #{case_no}: {question[:50]}...")
                
                # Create search text for embedding
                search_text = f"Q: {question} A: {answer}"
                
                # Create embedding
                print(f"  Creating embedding...")
                dense_vector = self._create_embedding(search_text)
                
                # Upsert to Qdrant
                print(f"  Upserting to Qdrant...")
                self.qdrant.upsert_case(
                    case_no=case_no,
                    date=date,
                    question=question,
                    answer=answer,
                    dense_vector=dense_vector,
                    file_last_modified=file_last_modified_str
                )
                
                stats['processed'] += 1
                print(f"  ✓ Successfully processed case #{case_no}")
                
            except Exception as e:
                print(f"Error processing row {idx + 1}: {str(e)}")
                stats['errors'] += 1
                continue
        
        stats['end_time'] = datetime.utcnow().isoformat()
        
        # Print summary
        print("\n=== Ingestion Summary ===")
        print(f"Total rows: {stats['total_rows']}")
        print(f"Processed: {stats['processed']}")
        print(f"Skipped: {stats['skipped']}")
        print(f"Errors: {stats['errors']}")
        
        # Get collection stats
        collection_stats = self.qdrant.get_collection_stats()
        print(f"\nCollection stats: {collection_stats}")
        
        return stats
