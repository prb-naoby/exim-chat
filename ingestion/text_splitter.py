"""
Text splitting module for chunking documents into manageable pieces
"""

from typing import List, Dict, Any


class TextSplitter:
    """Split text into chunks with optional overlap"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        Initialize text splitter
        
        Args:
            chunk_size: Size of each chunk in characters
            chunk_overlap: Number of overlapping characters between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def split_text(self, text: str) -> List[str]:
        """
        Split text into chunks
        
        Args:
            text: Text to split
            
        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Get chunk
            end = min(start + self.chunk_size, len(text))
            chunk = text[start:end]
            
            chunks.append(chunk)
            
            # Move start position, accounting for overlap
            start = end - self.chunk_overlap
            
            # Prevent infinite loop if chunk_overlap >= chunk_size
            if start <= chunks[-1].__len__() - self.chunk_overlap:
                break
        
        return chunks
    
    def split_by_sentences(self, text: str) -> List[str]:
        """
        Split text by sentence boundaries
        
        Args:
            text: Text to split
            
        Returns:
            List of sentence chunks
        """
        import re
        
        # Split by common sentence endings
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def split_document(self, document: Dict[str, Any], method: str = 'character') -> List[Dict[str, Any]]:
        """
        Split a document into chunks
        
        Args:
            document: Document dict with 'content' and 'metadata' keys
            method: Splitting method - 'character' or 'sentence'
            
        Returns:
            List of document chunks with metadata
        """
        content = document.get('content', '')
        metadata = document.get('metadata', {})
        
        if method == 'sentence':
            chunks = self.split_by_sentences(content)
        else:
            chunks = self.split_text(content)
        
        result = []
        for i, chunk in enumerate(chunks):
            result.append({
                'content': chunk,
                'metadata': {
                    **metadata,
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'chunk_size': len(chunk)
                }
            })
        
        return result
