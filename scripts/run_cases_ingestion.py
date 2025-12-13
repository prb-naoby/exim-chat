"""
Run Cases Q&A Ingestion

Production script to ingest historical cases Q&A from Excel spreadsheet
into Qdrant vector store.
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv

from ingestion.cases.cases_ingestion_pipeline import CasesIngestionPipeline


def main():
    # Load environment variables
    load_dotenv()
    
    # Configuration
    config = {
        # OneDrive
        'tenant_id': os.getenv('MS_TENANT_ID'),
        'client_id': os.getenv('MS_CLIENT_ID'),
        'client_secret': os.getenv('MS_CLIENT_SECRET'),
        'user_id': os.getenv('ONEDRIVE_DRIVE_ID'),
        'folder_path': os.getenv('CASES_FOLDER_PATH', 'AI/Cases'),
        
        # Qdrant
        'qdrant_url': os.getenv('CASES_QDRANT_URL'),
        'qdrant_api_key': os.getenv('CASES_QDRANT_API_KEY'),
        'collection_name': os.getenv('CASES_QDRANT_COLLECTION_NAME', 'cases_qna'),
        
        # Gemini
        'gemini_api_key': os.getenv('GEMINI_API_KEY'),
        'embedding_model': os.getenv('EMBEDDING_MODEL', 'models/gemini-embedding-001'),
        'vector_size': int(os.getenv('VECTOR_SIZE', '3072')),
        
        # Processing
        'batch_size': int(os.getenv('BATCH_SIZE', '50'))
    }
    
    print("=== Cases Q&A Ingestion Configuration ===")
    print(f"OneDrive Folder: {config['folder_path']}")
    print(f"Qdrant Collection: {config['collection_name']}")
    print(f"Embedding Model: {config['embedding_model']}")
    print(f"Vector Size: {config['vector_size']}")
    print(f"Batch Size: {config['batch_size']}")
    print("=" * 50)
    
    # Initialize pipeline
    pipeline = CasesIngestionPipeline(**config)
    
    # Run ingestion
    print("\nStarting cases Q&A ingestion...")
    start_time = datetime.now()
    
    try:
        stats = pipeline.sync_and_upsert()
        
        # Save log
        log_filename = f"ingestion_log_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_filename, 'w') as f:
            json.dump(stats, f, indent=2)
        
        print(f"\nIngestion log saved to: {log_filename}")
        
        # Calculate duration
        duration = datetime.now() - start_time
        print(f"Total duration: {duration}")
        
        print("\n✓ Cases Q&A ingestion completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Ingestion failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
