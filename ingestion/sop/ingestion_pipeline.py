"""
SOP ingestion pipeline
Workflow:
1. Check OneDrive for updated PDF files
2. Send to OCR service for text extraction
3. Vectorize OCR text
4. Upsert to Qdrant with document link
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from .onedrive_sync import SOPOneDriveSync
from ..vectorizer import Vectorizer
from ..qdrant_store import QdrantStore


class SOPIngestionPipeline:
    """End-to-end pipeline for SOP PDF document ingestion"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 drive_id: str, folder_path: str,
                 ocr_service_url: str, ocr_api_key: Optional[str],
                 qdrant_url: str, qdrant_api_key: str,
                 collection_name: str = "sop_documents",
                 embedding_model: str = 'models/text-embedding-004',
                 gemini_api_key: str = None,
                 vector_size: int = 768):
        """
        Initialize SOP ingestion pipeline
        
        Args:
            tenant_id: Microsoft Entra tenant ID
            client_id: Microsoft Entra app client ID
            client_secret: Microsoft Entra app client secret
            drive_id: OneDrive drive ID
            folder_path: Folder path within drive (e.g., 'AI/SOP')
            ocr_service_url: OCR service endpoint URL
            ocr_api_key: OCR service API key
            qdrant_url: Qdrant server URL
            qdrant_api_key: Qdrant API key
            collection_name: Qdrant collection name
            embedding_model: Gemini embedding model name
            gemini_api_key: Google AI Studio API key (required)
            vector_size: Dimension of embedding vectors (768 for text-embedding-004)
        """
        self.onedrive = SOPOneDriveSync(
            tenant_id,
            client_id,
            client_secret,
            drive_id,
            folder_path,
            ocr_service_url,
            ocr_api_key
        )
        self.vectorizer = Vectorizer(
            model_name=embedding_model,
            api_key=gemini_api_key
        )
        self.qdrant = QdrantStore(
            url=qdrant_url, 
            api_key=qdrant_api_key,
            collection_name=collection_name
        )
        
        # Create collection if needed
        self.qdrant.create_collection(vector_size=vector_size)
    
    def vectorize_sop_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Vectorize SOP document using OCR text
        
        Args:
            document: Document with OCR text
            
        Returns:
            Document with embedding
        """
        # Use OCR text for vectorization
        text = document.get('ocr_text', '')
        
        if not text:
            raise ValueError(f"No OCR text found for document {document.get('filename')}")
        
        # Vectorize
        embedding = self.vectorizer.vectorize_text(text)
        
        document_copy = document.copy()
        document_copy['embedding'] = embedding
        document_copy['search_text'] = text[:500]  # Store preview
        
        return document_copy
    
    def sync_and_upsert(self, last_sync_date: Optional[datetime] = None, dry_run: bool = False) -> Dict[str, Any]:
        """
        Full pipeline: sync from OneDrive -> OCR -> vectorize -> upsert to Qdrant
        
        Args:
            last_sync_date: Last sync date. If None, syncs files modified today.
            dry_run: If True, preview operations without making changes to Qdrant
            
        Returns:
            Summary of operations (upserted, skipped, errors)
        """
        summary = {
            'upserted': [],
            'skipped': [],
            'errors': [],
            'timestamp': datetime.now().isoformat(),
            'dry_run': dry_run
        }
        
        # Step 1: Sync and OCR documents from OneDrive
        try:
            updated_documents = self.onedrive.sync_documents(last_sync_date)
            summary['synced_count'] = len(updated_documents)
        except Exception as e:
            summary['errors'].append(f"OneDrive sync failed: {str(e)}")
            return summary
        
        # Step 2 & 3: Process each document
        for document in updated_documents:
            try:
                # Extract document ID from filename
                doc_id = SOPOneDriveSync.extract_document_id(document['filename'])
                
                # Check if document already exists in Qdrant
                existing_doc = self.qdrant.get_document(doc_id)
                
                # Compare by lastModifiedDateTime
                if existing_doc:
                    existing_modified = existing_doc.get('lastModifiedDateTime')
                    new_modified = document.get('lastModifiedDateTime')
                    
                    if existing_modified == new_modified:
                        summary['skipped'].append({
                            'document_id': doc_id,
                            'reason': 'No changes detected'
                        })
                        continue
                
                # Vectorize the document
                vectorized_doc = self.vectorize_sop_document(document)
                
                # Upsert to Qdrant (skip if dry_run)
                if not dry_run:
                    self.qdrant.upsert_document(
                        hs_code=doc_id,  # Using doc_id as unique identifier
                        embedding=vectorized_doc['embedding'],
                        document=document
                    )
                
                summary['upserted'].append({
                    'document_id': doc_id,
                    'filename': document['filename'],
                    'document_link': document.get('document_link', ''),
                    'is_new': existing_doc is None,
                    'would_upsert': dry_run
                })
                
            except Exception as e:
                summary['errors'].append({
                    'document': document.get('filename', 'unknown'),
                    'error': str(e)
                })
        
        return summary
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar SOP documents
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of search results with document links
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
