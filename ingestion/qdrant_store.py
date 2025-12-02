"""
Qdrant vector store integration for storing and retrieving INSW documents
"""

from typing import List, Dict, Any, Optional
import json
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams


class QdrantStore:
    """Vector store for INSW documents using Qdrant"""
    
    def __init__(self, url: str, api_key: str, collection_name: str = "insw_regulations"):
        """
        Initialize Qdrant store
        
        Args:
            url: Qdrant server URL
            api_key: API key for Qdrant
            collection_name: Name of the collection
        """
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection_name = collection_name
    
    def create_collection(self, vector_size: int = 384, distance: str = "Cosine"):
        """
        Create collection if it doesn't exist
        
        Args:
            vector_size: Dimension of vectors
            distance: Distance metric (Cosine, Euclid, Manhattan)
        """
        try:
            collection = self.client.get_collection(self.collection_name)
            print(f"Collection '{self.collection_name}' already exists with {collection.points_count} points")
        except Exception as e:
            # Collection doesn't exist, create it
            print(f"Creating collection '{self.collection_name}' with vector size {vector_size}")
            distance_enum = {
                "Cosine": Distance.COSINE,
                "Euclid": Distance.EUCLID,
                "Manhattan": Distance.MANHATTAN
            }.get(distance, Distance.COSINE)
            
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=distance_enum)
            )
            print(f"Collection '{self.collection_name}' created successfully")
    
    def upsert_document(self, hs_code: str, embedding: List[float], 
                       document: Dict[str, Any], last_modified: str = None) -> str:
        """
        Upsert a single document to Qdrant
        
        Args:
            hs_code: HS code identifier
            embedding: Vector embedding
            document: Document content
            last_modified: lastModifiedDateTime from OneDrive
            
        Returns:
            Point ID (hs_code)
        """
        print(f"    Upserting HS Code: {hs_code} to collection: {self.collection_name}")
        
        # Convert HS code to integer (remove leading zeros if any, treat as number)
        point_id = int(hs_code)
        
        # Extract regulations info
        regulations = document.get('regulations', {})
        import_regs = regulations.get('import_regulation', [])
        export_regs = regulations.get('export_regulation', [])
        import_border_regs = regulations.get('import_regulation_border', [])
        post_border_regs = regulations.get('import_regulation_post_border', [])
        
        # Extract BC document types
        bc_documents = document.get('bc_documents', [])
        bc_types = [doc.get('type', '') for doc in bc_documents]
        
        point = PointStruct(
            id=point_id,  # Use hs_code as integer ID
            vector=embedding,
            payload={
                # Core identifiers
                'hs_code': hs_code,
                'deskripsi': document.get('deskripsi', ''),
                'uraian_barang': document.get('uraian_barang', ''),
                'bagian': document.get('bagian', ''),
                'bab': document.get('bab', 0),
                
                # Hierarchical descriptions
                'bagian_penjelasan': document.get('bagian_penjelasan', []),
                'bab_penjelasan': document.get('bab_penjelasan', []),
                'hs_parent_uraian': document.get('hs_parent_uraian', []),
                
                # Regulation flags
                'has_import_regulations': len(import_regs) > 0,
                'has_export_regulations': len(export_regs) > 0,
                'has_import_border_regulations': len(import_border_regs) > 0,
                'has_post_border_regulations': len(post_border_regs) > 0,
                'regulation_count': len(import_regs) + len(export_regs) + len(import_border_regs) + len(post_border_regs),
                
                # BC documents
                'bc_document_types': bc_types,
                'has_bc_23': 'BC 2.3' in bc_types,
                'has_bc_25': 'BC 2.5' in bc_types,
                'bc_document_count': len(bc_documents),
                
                # Reference data
                'has_ref_satuan': len(document.get('ref_satuan', [])) > 0,
                'link': document.get('link', ''),
                
                # Search and metadata
                'search_text': self._create_search_text(document),
                'lastModifiedDateTime': last_modified or document.get('_file_metadata', {}).get('lastModifiedDateTime', ''),
                
                # Full document for retrieval
                'full_document': json.dumps(document, ensure_ascii=False)
            }
        )
        
        try:
            result = self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            print(f"      Upsert successful for point ID: {point_id}")
        except Exception as e:
            print(f"      Upsert failed: {e}")
            raise
        
        return hs_code
    
    def upsert_documents(self, documents_with_embeddings: List[Dict[str, Any]]) -> List[str]:
        """
        Upsert multiple documents to Qdrant
        
        Args:
            documents_with_embeddings: List of dicts with:
                - hs_code: HS code
                - embedding: Vector embedding
                - document: Document content
                
        Returns:
            List of upserted point IDs
        """
        points = []
        upserted_ids = []
        
        for item in documents_with_embeddings:
            hs_code = item['hs_code']
            embedding = item['embedding']
            document = item['document']
            
            point = PointStruct(
                id=hs_code,
                vector=embedding,
                payload={
                    'hs_code': hs_code,
                    'document': json.dumps(document),
                    'hs_parent_uraian': document.get('hs_parent_uraian', ''),
                    'search_text': self._create_search_text(document)
                }
            )
            
            points.append(point)
            upserted_ids.append(hs_code)
        
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        
        return upserted_ids
    
    def get_document(self, hs_code: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a document by HS code
        
        Args:
            hs_code: HS code identifier
            
        Returns:
            Document content or None if not found
        """
        try:
            point_id = int(hs_code)
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id]
            )
            
            if points:
                payload = points[0].payload
                return json.loads(payload['full_document'])
            return None
        except:
            return None
    
    def get_last_modified(self, hs_code: str) -> Optional[str]:
        """
        Get lastModifiedDateTime for a document in Qdrant
        
        Args:
            hs_code: HS code identifier
            
        Returns:
            lastModifiedDateTime string or None if not found
        """
        try:
            point_id = int(hs_code)
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id]
            )
            
            if points:
                return points[0].payload.get('lastModifiedDateTime')
            return None
        except:
            return None
    
    def search_similar(self, embedding: List[float], top_k: int = 5, 
                      score_threshold: float = 0.0) -> List[Dict[str, Any]]:
        """
        Search for similar documents
        
        Args:
            embedding: Query vector embedding
            top_k: Number of results to return
            score_threshold: Minimum similarity score
            
        Returns:
            List of search results with documents and scores
        """
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=embedding,
            limit=top_k,
            score_threshold=score_threshold
        )
        
        search_results = []
        for point in results:
            payload = point.payload
            search_results.append({
                'hs_code': payload['hs_code'],
                'document': json.loads(payload['full_document']),
                'similarity_score': point.score,
                'search_text': payload['search_text'],
                'deskripsi': payload.get('deskripsi', ''),
                'uraian_barang': payload.get('uraian_barang', ''),
                'has_import_regulations': payload.get('has_import_regulations', False),
                'has_export_regulations': payload.get('has_export_regulations', False),
                'bc_document_types': payload.get('bc_document_types', [])
            })
        
        return search_results
    
    def document_exists(self, hs_code: str) -> bool:
        """
        Check if document exists in store
        
        Args:
            hs_code: HS code identifier
            
        Returns:
            True if document exists
        """
        try:
            point_id = int(hs_code)
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[point_id]
            )
            return len(points) > 0
        except:
            return False
    
    def delete_document(self, hs_code: str) -> bool:
        """
        Delete a document from store
        
        Args:
            hs_code: HS code identifier
            
        Returns:
            True if deletion was successful
        """
        try:
            point_id = int(hs_code)
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[point_id]
            )
            return True
        except:
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics
        
        Returns:
            Collection stats including point count
        """
        collection_info = self.client.get_collection(self.collection_name)
        return {
            'points_count': collection_info.points_count,
            'status': collection_info.status
        }
    
    @staticmethod
    def _create_search_text(document: Dict[str, Any]) -> str:
        """
        Create search text from document fields
        Concatenates hs_parent_uraian (list) and hs_code
        
        Args:
            document: Document content
            
        Returns:
            Combined search text
        """
        hs_parent = document.get('hs_parent_uraian', [])
        if isinstance(hs_parent, list):
            hs_parent_text = ' '.join(hs_parent)
        else:
            hs_parent_text = str(hs_parent)
        
        hs_code = document.get('hs_code', '')
        
        return f"HSCode: {hs_code} {hs_parent_text}".strip()
