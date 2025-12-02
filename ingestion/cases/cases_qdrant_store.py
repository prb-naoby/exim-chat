"""
Qdrant Store for Cases Q&A

Handles vector storage with hybrid search (dense + sparse BM25) for cases Q&A
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    SparseVectorParams, SparseIndexParams,
    Query, Prefetch
)
import hashlib


class CasesQdrantStore:
    def __init__(
        self,
        url: str,
        api_key: str,
        collection_name: str = "cases_qna",
        vector_size: int = 3072
    ):
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection_name = collection_name
        self.vector_size = vector_size
        
    def create_collection(self):
        """Create Qdrant collection with hybrid vectors (dense + sparse)"""
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            if any(col.name == self.collection_name for col in collections):
                print(f"Collection '{self.collection_name}' already exists")
                return
            
            # Create collection with named vectors
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": VectorParams(
                        size=self.vector_size,
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
            
        except Exception as e:
            print(f"Error creating collection: {str(e)}")
            raise
    
    def _create_sparse_vector(self, text: str) -> Dict[str, List]:
        """Create simple BM25-like sparse vector from text"""
        # Tokenize and count words
        words = text.lower().split()
        word_freq = {}
        
        for word in words:
            if len(word) > 2:  # Skip very short words
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Convert to sparse vector format with hash-based indices
        indices = []
        values = []
        
        for word, freq in word_freq.items():
            # Use hash of word as index
            index = hash(word) % (2**32)  # 32-bit hash
            indices.append(index)
            values.append(float(freq))
        
        return {
            "indices": indices,
            "values": values
        }
    
    def upsert_case(
        self,
        case_no: int,
        date: str,
        question: str,
        answer: str,
        dense_vector: List[float],
        file_last_modified: str
    ):
        """Upsert a single case Q&A to Qdrant"""
        # Create search text (for embedding)
        search_text = f"Q: {question} A: {answer}"
        
        # Create full text (for display)
        full_text = f"Case #{case_no} ({date}): Q: {question} A: {answer}"
        
        # Create sparse vector
        sparse_vector = self._create_sparse_vector(search_text)
        
        # Create unique ID from case_no (use integer directly)
        point_id = case_no
        
        # Create payload
        payload = {
            'case_no': case_no,
            'date': date,
            'question': question,
            'answer': answer,
            'search_text': search_text,
            'full_text': full_text,
            'source': 'cases_spreadsheet',
            'file_last_modified': file_last_modified,
            'dateUpdated': datetime.utcnow().isoformat()
        }
        
        # Upsert point with hybrid vectors
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_vector,
                        "bm25": sparse_vector
                    },
                    payload=payload
                )
            ]
        )
    
    def search_hybrid(
        self,
        query_dense: List[float],
        query_text: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search (dense + sparse) with RRF fusion"""
        # Create sparse vector for query
        sparse_vector = self._create_sparse_vector(query_text)
        
        # Hybrid search with RRF fusion
        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(
                    query=query_dense,
                    using="dense",
                    limit=limit * 2
                ),
                Prefetch(
                    query=sparse_vector,
                    using="bm25",
                    limit=limit * 2
                )
            ],
            query=Query(fusion="rrf"),
            limit=limit
        )
        
        # Format results
        formatted_results = []
        for point in results.points:
            formatted_results.append({
                'case_no': point.payload.get('case_no'),
                'date': point.payload.get('date'),
                'question': point.payload.get('question'),
                'answer': point.payload.get('answer'),
                'score': point.score
            })
        
        return formatted_results
    
    def get_file_last_modified(self) -> Optional[str]:
        """Get the file_last_modified timestamp from the most recent case"""
        try:
            # Scroll through collection to find most recent file_last_modified
            points = self.client.scroll(
                collection_name=self.collection_name,
                limit=1,
                with_payload=True
            )[0]
            
            if points:
                return points[0].payload.get('file_last_modified')
            
            return None
        except Exception as e:
            print(f"Error getting last modified: {str(e)}")
            return None
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                'total_cases': info.points_count,
                'vectors_config': str(info.config.params.vectors),
                'sparse_vectors_config': str(info.config.params.sparse_vectors)
            }
        except Exception as e:
            return {'error': str(e)}
