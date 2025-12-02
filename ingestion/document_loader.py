"""
Document loader module for handling various file formats
Supports: PDF, TXT, DOCX, CSV, JSON, MD
"""

import os
from pathlib import Path
from typing import List, Dict, Any


class DocumentLoader:
    """Load documents from various file formats"""
    
    SUPPORTED_FORMATS = {
        '.pdf': 'pdf',
        '.txt': 'text',
        '.docx': 'docx',
        '.csv': 'csv',
        '.json': 'json',
        '.md': 'markdown'
    }
    
    @staticmethod
    def load_file(file_path: str) -> Dict[str, Any]:
        """
        Load a single file and return content with metadata
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary with 'content' and 'metadata' keys
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_ext = file_path.suffix.lower()
        
        if file_ext not in DocumentLoader.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported file format: {file_ext}")
        
        file_type = DocumentLoader.SUPPORTED_FORMATS[file_ext]
        
        if file_type == 'pdf':
            return DocumentLoader._load_pdf(file_path)
        elif file_type == 'text':
            return DocumentLoader._load_text(file_path)
        elif file_type == 'docx':
            return DocumentLoader._load_docx(file_path)
        elif file_type == 'csv':
            return DocumentLoader._load_csv(file_path)
        elif file_type == 'json':
            return DocumentLoader._load_json(file_path)
        elif file_type == 'markdown':
            return DocumentLoader._load_markdown(file_path)
    
    @staticmethod
    def _load_text(file_path: Path) -> Dict[str, Any]:
        """Load plain text file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            'content': content,
            'metadata': {
                'file_name': file_path.name,
                'file_path': str(file_path),
                'file_type': 'text',
                'file_size': file_path.stat().st_size
            }
        }
    
    @staticmethod
    def _load_pdf(file_path: Path) -> Dict[str, Any]:
        """Load PDF file - requires PyPDF2"""
        try:
            import PyPDF2
        except ImportError:
            raise ImportError("PyPDF2 is required for PDF support. Install with: pip install PyPDF2")
        
        content = []
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                content.append(f"--- Page {page_num + 1} ---\n{text}")
        
        return {
            'content': '\n'.join(content),
            'metadata': {
                'file_name': file_path.name,
                'file_path': str(file_path),
                'file_type': 'pdf',
                'file_size': file_path.stat().st_size,
                'pages': len(reader.pages)
            }
        }
    
    @staticmethod
    def _load_docx(file_path: Path) -> Dict[str, Any]:
        """Load DOCX file - requires python-docx"""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx is required for DOCX support. Install with: pip install python-docx")
        
        doc = Document(file_path)
        content = '\n'.join([para.text for para in doc.paragraphs])
        
        return {
            'content': content,
            'metadata': {
                'file_name': file_path.name,
                'file_path': str(file_path),
                'file_type': 'docx',
                'file_size': file_path.stat().st_size
            }
        }
    
    @staticmethod
    def _load_csv(file_path: Path) -> Dict[str, Any]:
        """Load CSV file - requires pandas"""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for CSV support. Install with: pip install pandas")
        
        df = pd.read_csv(file_path)
        content = df.to_string()
        
        return {
            'content': content,
            'metadata': {
                'file_name': file_path.name,
                'file_path': str(file_path),
                'file_type': 'csv',
                'file_size': file_path.stat().st_size,
                'rows': len(df),
                'columns': list(df.columns)
            }
        }
    
    @staticmethod
    def _load_json(file_path: Path) -> Dict[str, Any]:
        """Load JSON file"""
        import json
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        content = json.dumps(data, indent=2)
        
        return {
            'content': content,
            'metadata': {
                'file_name': file_path.name,
                'file_path': str(file_path),
                'file_type': 'json',
                'file_size': file_path.stat().st_size
            }
        }
    
    @staticmethod
    def _load_markdown(file_path: Path) -> Dict[str, Any]:
        """Load Markdown file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            'content': content,
            'metadata': {
                'file_name': file_path.name,
                'file_path': str(file_path),
                'file_type': 'markdown',
                'file_size': file_path.stat().st_size
            }
        }
    
    @staticmethod
    def load_directory(directory_path: str, recursive: bool = True) -> List[Dict[str, Any]]:
        """
        Load all supported files from a directory
        
        Args:
            directory_path: Path to the directory
            recursive: Whether to search subdirectories
            
        Returns:
            List of loaded documents
        """
        dir_path = Path(directory_path)
        
        if not dir_path.is_dir():
            raise ValueError(f"Not a directory: {directory_path}")
        
        documents = []
        pattern = '**/*' if recursive else '*'
        
        for file_path in dir_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in DocumentLoader.SUPPORTED_FORMATS:
                try:
                    doc = DocumentLoader.load_file(str(file_path))
                    documents.append(doc)
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
        
        return documents
