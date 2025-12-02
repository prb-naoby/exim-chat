"""
Qdrant store for SOP documents with hybrid search (dense + sparse vectors)
"""
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, 
    SparseVectorParams, SparseIndexParams,
    NamedVector, NamedSparseVector,
    Prefetch, Query, SparseVector
)
from typing import List, Dict, Any, Optional
import json
import hashlib


class SOPQdrantStore:
    """Qdrant vector store for SOP documents with hybrid search"""
    
    def __init__(self, url: str, api_key: str, collection_name: str = "sop_documents"):
        """
        Initialize Qdrant store for SOP documents
        
        Args:
            url: Qdrant server URL
            api_key: Qdrant API key
            collection_name: Collection name
        """
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection_name = collection_name
    
    def create_collection(self, vector_size: int = 3072):
        """
        Create collection with hybrid vectors (dense + sparse)
        
        Args:
            vector_size: Dense vector size (3072 for gemini-embedding-001)
        """
        # Check if collection exists
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if exists:
            info = self.client.get_collection(self.collection_name)
            print(f"Collection '{self.collection_name}' already exists with {info.points_count} points")
            return
        
        # Create collection with named vectors
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            },
            sparse_vectors_config={
                "bm25": SparseVectorParams(
                    index=SparseIndexParams()
                )
            }
        )
        print(f"Created collection '{self.collection_name}' with hybrid vectors")
    
    def _generate_doc_id(self, doc_no: str, filename: str) -> str:
        """
        Generate unique document ID from doc_no and filename
        
        Args:
            doc_no: Document number
            filename: PDF filename
            
        Returns:
            Hash-based ID
        """
        # Use doc_no if available, otherwise use filename
        key = doc_no if doc_no else filename
        return hashlib.md5(key.encode()).hexdigest()
    
    def _create_sparse_vector(self, text: str) -> Dict[str, Any]:
        """
        Create BM25-like sparse vector from text
        Simple implementation: word frequencies as indices
        
        Args:
            text: Text to vectorize
            
        Returns:
            Sparse vector dict with indices and values
        """
        # Tokenize and count words
        words = text.lower().split()
        word_freq = {}
        for word in words:
            if len(word) > 2:  # Skip short words
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Convert to sparse format (use hash of word as index)
        indices = []
        values = []
        for word, freq in word_freq.items():
            idx = abs(hash(word)) % (10**6)  # Use hash as index
            indices.append(idx)
            values.append(float(freq))
        
        return {
            "indices": indices,
            "values": values
        }
    
    def upsert_document(self, doc_no: str, filename: str, dense_embedding: List[float],
                       parsed_data: Dict[str, Any], full_text: str,
                       file_metadata: Dict[str, Any]) -> str:
        """
        Upsert SOP document with hybrid vectors
        
        Args:
            doc_no: Document number (used as primary key)
            filename: PDF filename
            dense_embedding: Dense vector from Gemini
            parsed_data: Parsed SOP fields (sop_title, tujuan, etc.)
            full_text: Full OCR text
            file_metadata: OneDrive metadata (lastModifiedDateTime, size, webUrl)
            
        Returns:
            Document ID
        """
        doc_id = self._generate_doc_id(doc_no, filename)
        
        print(f"      Upserting SOP to Qdrant: {doc_id}")
        
        # Create search text for sparse vector
        search_text = f"SOP: {parsed_data.get('sop_title', '')}. Tujuan: {parsed_data.get('tujuan', '')}. Uraian: {parsed_data.get('uraian', '')}. Dokumen: {parsed_data.get('dokumen', '')}"
        sparse_vector = self._create_sparse_vector(search_text)
        
        # Create point with named vectors
        point = PointStruct(
            id=doc_id,
            vector={
                "dense": dense_embedding,
                "bm25": sparse_vector
            },
            payload={
                # Parsed fields
                'sop_title': parsed_data.get('sop_title', ''),
                'tujuan': parsed_data.get('tujuan', ''),
                'uraian': parsed_data.get('uraian', ''),
                'dokumen': parsed_data.get('dokumen', ''),
                'date': parsed_data.get('date', ''),
                'doc_no': parsed_data.get('doc_no', ''),
                'rev': parsed_data.get('rev', ''),
                'type': parsed_data.get('type', 'UNKNOWN'),  # IK or SOP
                
                # Search text
                'search_text': search_text,
                
                # Full content
                'full_text': full_text,
                
                # File metadata
                'filename': filename,
                'lastModifiedDateTime': file_metadata.get('lastModifiedDateTime', ''),
                'dateUpdated': file_metadata.get('lastModifiedDateTime', ''),
                'size': file_metadata.get('size', 0),
                'webUrl': file_metadata.get('webUrl', '')
            }
        )
        
        # Upsert
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        
        print(f"      Upsert successful: {doc_id}")
        return doc_id
    
    def get_last_modified(self, doc_no: str, filename: str) -> Optional[str]:
        """
        Get lastModifiedDateTime for a document
        
        Args:
            doc_no: Document number
            filename: PDF filename
            
        Returns:
            lastModifiedDateTime string or None if not found
        """
        try:
            doc_id = self._generate_doc_id(doc_no, filename)
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[doc_id]
            )
            
            if points:
                return points[0].payload.get('lastModifiedDateTime')
            return None
        except:
            return None
    
    def search_hybrid(self, query_dense: List[float], query_text: str,
                     top_k: int = 5, alpha: float = 0.5) -> List[Dict[str, Any]]:
        """
        Hybrid search with dense + sparse vectors
        
        Args:
            query_dense: Dense query vector
            query_text: Text query for sparse search
            top_k: Number of results
            alpha: Weight for dense vs sparse (0.5 = equal weight)
            
        Returns:
            List of search results with metadata
        """
        query_sparse = self._create_sparse_vector(query_text)
        
        # Qdrant hybrid search with prefetch
        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(
                    query=query_dense,
                    using="dense",
                    limit=top_k * 2
                ),
                Prefetch(
                    query=SparseVector(
                        indices=query_sparse["indices"],
                        values=query_sparse["values"]
                    ),
                    using="bm25",
                    limit=top_k * 2
                )
            ],
            query=Query(fusion="rrf"),
            limit=top_k
        )
        
        return [
            {
                'id': hit.id,
                'score': hit.score,
                'sop_title': hit.payload.get('sop_title', ''),
                'type': hit.payload.get('type', 'UNKNOWN'),
                'tujuan': hit.payload.get('tujuan', ''),
                'uraian': hit.payload.get('uraian', ''),
                'dokumen': hit.payload.get('dokumen', ''),
                'doc_no': hit.payload.get('doc_no', ''),
                'rev': hit.payload.get('rev', ''),
                'filename': hit.payload.get('filename', ''),
                'webUrl': hit.payload.get('webUrl', '')
            }
            for hit in results.points
        ]
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        info = self.client.get_collection(self.collection_name)
        return {
            'collection_name': self.collection_name,
            'points_count': info.points_count,
            'status': info.status
        }
