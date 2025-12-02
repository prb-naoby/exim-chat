"""
Vectorization module for converting documents to embeddings using Google Gemini
"""

from typing import List, Dict, Any


class Vectorizer:
    """Convert documents to vector embeddings using Google Gemini"""
    
    def __init__(self, model_name: str = 'models/text-embedding-004', api_key: str = None):
        """
        Initialize vectorizer
        
        Args:
            model_name: Name of the Gemini embedding model to use
            api_key: Google AI Studio API key (required)
        """
        self.model_name = model_name
        self.api_key = api_key
        self.client = None
        self._load_model()
    
    def _load_model(self):
        """Load Gemini client"""
        try:
            import google.genai as genai
        except ImportError:
            raise ImportError(
                "google-genai is required for Gemini embeddings. "
                "Install with: pip install google-genai"
            )
        
        if not self.api_key:
            raise ValueError("API key is required for Gemini embeddings")
        
        self.client = genai.Client(api_key=self.api_key)
    
    def vectorize_text(self, text: str) -> List[float]:
        """
        Convert text to embedding vector
        
        Args:
            text: Text to vectorize
            
        Returns:
            Embedding vector as list
        """
        if self.client is None:
            raise RuntimeError("Client not loaded. Call _load_model() first.")
        
        result = self.client.models.embed_content(
            model=self.model_name,
            contents=text
        )
        return result.embeddings[0].values
    
    def vectorize_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Vectorize an INSW document
        Uses concatenation of hs_parent_uraian (list) and hs_code for search text
        
        Args:
            document: Document content
            
        Returns:
            Document with 'embedding' key added
        """
        # Create search text from concat of hs_parent_uraian and hs_code
        # hs_parent_uraian can be a list of strings
        hs_parent = document.get('hs_parent_uraian', [])
        if isinstance(hs_parent, list):
            hs_parent_text = ' '.join(hs_parent)
        else:
            hs_parent_text = str(hs_parent)
        
        hs_code = document.get('hs_code', '')
        search_text = f"HSCode: {hs_code} {hs_parent_text}".strip()
        
        # Vectorize the search text
        embedding = self.vectorize_text(search_text)
        
        # Add embedding to document
        document_copy = document.copy()
        document_copy['embedding'] = embedding
        document_copy['search_text'] = search_text
        
        return document_copy
    
    def vectorize_documents(self, documents: List[Dict[str, Any]], 
                           batch_size: int = 32) -> List[Dict[str, Any]]:
        """
        Vectorize multiple INSW documents
        
        Args:
            documents: List of documents
            batch_size: Batch size for processing (unused with Gemini API)
            
        Returns:
            List of documents with embeddings
        """
        # Create search texts for all documents
        search_texts = []
        for doc in documents:
            hs_parent = doc.get('hs_parent_uraian', [])
            if isinstance(hs_parent, list):
                hs_parent_text = ' '.join(hs_parent)
            else:
                hs_parent_text = str(hs_parent)
            
            hs_code = doc.get('hs_code', '')
            search_text = f"{hs_parent_text} {hs_code}".strip()
            search_texts.append(search_text)
        
        # Vectorize with Gemini
        embeddings = []
        for text in search_texts:
            result = self.client.models.embed_content(
                model=self.model_name,
                contents=text
            )
            embeddings.append(result.embeddings[0].values)
        
        # Add embeddings to documents
        result = []
        for doc, embedding, search_text in zip(documents, embeddings, search_texts):
            doc_copy = doc.copy()
            doc_copy['embedding'] = embedding
            doc_copy['search_text'] = search_text
            result.append(doc_copy)
        
        return result
    
    def vectorize_query(self, query: str) -> List[float]:
        """
        Vectorize a search query
        
        Args:
            query: Search query text
            
        Returns:
            Query embedding as list
        """
        return self.vectorize_text(query)
    
    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return float(dot_product / (magnitude1 * magnitude2))
