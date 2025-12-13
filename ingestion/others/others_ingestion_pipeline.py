
"""
Others (Unstructured) ingestion pipeline
Workflow:
1. Get files metadata from OneDrive (AI/Others)
2. Check against Qdrant
3. Download File
4. If PPTX -> Convert to PDF
5. PDF -> OCR Service -> Text
6. Create chunks/vectors
7. Upsert to Qdrant (Others Collection)
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import shutil
import tempfile
import time
import uuid
# from langchain.text_splitter import RecursiveCharacterTextSplitter
import pypdf

# Reuse SOP modules where possible
from ingestion.sop.sop_onedrive_sync import SOPOneDriveSync
from ingestion.vectorizer import Vectorizer

# Custom Qdrant store for Others (simple schema)
from qdrant_client import QdrantClient
from qdrant_client.http import models

# New modules
from modules.ppt_converter import convert_ppt_to_pdf
from modules.ocr_service import OCRService

class OthersIngestionPipeline:
    """Pipeline for AI/Others unstructured document ingestion"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 drive_id: str, folder_path: str,
                 qdrant_url: str, qdrant_api_key: str, qdrant_collection_name: str,
                 embedding_model: str, gemini_api_key: str,
                 vector_size: int,
                 skip_qdrant_init: bool = False):
        
        # Initialize OneDrive sync
        self.onedrive = SOPOneDriveSync(tenant_id, client_id, client_secret, drive_id, folder_path)
        
        # Initialize OCR
        self.ocr_service = OCRService(gemini_api_key=gemini_api_key)
        
        # Initialize vectorizer
        self.vectorizer = Vectorizer(
            model_name=embedding_model,
            api_key=gemini_api_key
        )
        
        self.collection_name = qdrant_collection_name
        
        # Initialize Qdrant
        if not skip_qdrant_init:
            self.qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
            self._init_collection(vector_size)
        else:
            self.qdrant_client = None
            
    def _init_collection(self, vector_size: int):
        try:
            self.qdrant_client.get_collection(self.collection_name)
        except Exception:
            print(f"Creating collection {self.collection_name}...")
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                )
            )
            
        # Ensure index exists (safe to call repeatedly usually, or wrap in try)
        try:
            self.qdrant_client.create_payload_index(
                collection_name=self.collection_name,
                field_name="filename",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            print(f"Verified/Created index on 'filename'")
        except Exception as e:
            # might already exist
            print(f"Index creation note: {e}")
            
    def get_last_modified(self, filename: str) -> Optional[str]:
        """Check if file exists in Qdrant and get its last modified date"""
        if not self.qdrant_client:
            return None
            
        # Search by filename filter
        results = self.qdrant_client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="filename",
                        match=models.MatchValue(value=filename)
                    )
                ]
            ),
            limit=1,
            with_payload=True
        )
        
        if results[0]:
            payload = results[0][0].payload
            return payload.get('last_modified_onedrive')
        return None

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Simple text chunking"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += (chunk_size - overlap)
        return chunks

    def sync_and_upsert(self, last_sync_date: Optional[datetime] = None,
                       dry_run: bool = False, batch_size: int = None) -> Dict[str, Any]:
        
        if batch_size is None:
            batch_size = int(os.getenv('BATCH_SIZE', '50'))
            
        summary = {
            'upserted': [],
            'skipped': [],
            'errors': [],
            'timestamp': datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(),
            'dry_run': dry_run
        }
        
        # Step 1: Get metadata
        print("Fetching file list from OneDrive (AI/Others)...")
        try:
            all_files_metadata = self.onedrive.get_files_metadata()
            print(f"Found {len(all_files_metadata)} files")
            summary['total_files'] = len(all_files_metadata)
        except Exception as e:
            summary['errors'].append({'error': f"Metadata fetch failed: {e}"})
            return summary
            
        # Create temp dir for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            
            # Step 2: Iterate
            total_processed = 0
            
            for file_meta in all_files_metadata:
                filename = file_meta['name']
                file_id = file_meta['id']
                onedrive_last_modified = file_meta['lastModifiedDateTime']
                
                # Filter extensions
                ext = os.path.splitext(filename)[1].lower()
                if ext not in ['.pdf', '.ppt', '.pptx']:
                    continue
                    
                # Check Qdrant
                if self.qdrant_client:
                    qdrant_mod = self.get_last_modified(filename)
                    if qdrant_mod and onedrive_last_modified <= qdrant_mod:
                        summary['skipped'].append(filename)
                        print(f"Skipping {filename} (up to date)")
                        continue
                
                print(f"Processing {filename}...")
                total_processed += 1
                
                try:
                    # Download
                    content = self.onedrive.get_file_content(file_id)
                    local_path = os.path.join(temp_dir, filename)
                    with open(local_path, 'wb') as f:
                        f.write(content)
                        
                    # Conversion for PPT
                    pdf_path = local_path
                    if ext in ['.ppt', '.pptx']:
                        print(f"  Converting {filename} to PDF...")
                        pdf_filename = os.path.splitext(filename)[0] + '.pdf'
                        pdf_path = os.path.join(temp_dir, pdf_filename)
                        success = convert_ppt_to_pdf(local_path, pdf_path)
                        if not success:
                            raise Exception("PPT conversion failed")
                    
                    # Page-by-Page OCR using pypdf splitting
                    print(f"  Processing pages for {filename}...")
                    try:
                        reader = pypdf.PdfReader(pdf_path)
                        num_pages = len(reader.pages)
                        print(f"  Found {num_pages} pages.")
                    except Exception as e:
                         print(f"Error reading PDF {filename}: {e}")
                         # Fallback to full doc processing if pypdf fails
                         reader = None
                         num_pages = 1
                    
                    points_to_upsert = []
                    
                    if reader and num_pages > 0:
                        # Iterate pages
                        for page_idx, page in enumerate(reader.pages):
                            page_num = page_idx + 1
                            print(f"    OCR Processing Page {page_num}/{num_pages}...")
                            
                            # Save single page to debug folder for inspection
                            debug_filename = f"{os.path.splitext(filename)[0]}_page_{page_num}.pdf"
                            debug_path = os.path.join(os.getenv("DEBUG_PAGES_DIR", "debug_pages"), debug_filename)
                            
                            # Ensure directory exists (redundant if mkdir run, but safe)
                            os.makedirs(os.path.dirname(debug_path), exist_ok=True)
                            
                            try:
                                writer = pypdf.PdfWriter()
                                writer.add_page(page)
                                with open(debug_path, "wb") as f_out:
                                    writer.write(f_out)
                                    
                                # OCR this page using GenAI
                                ocr_result = self.ocr_service.process_with_genai(debug_path, model_name="gemini-2.5-flash")
                                
                                # GenAI returns string directly
                                page_text = ocr_result if ocr_result else ""
                                
                                if not page_text or not page_text.strip():
                                    print(f"    Warning: No text for page {page_num}")
                                    continue
                                    
                                # Chunking disabled per user request (one chunk per page)
                                page_chunks = [page_text]
                                
                                for i, chunk_text in enumerate(page_chunks):
                                    chunk_id = f"{file_id}_p{page_num}_{i}"
                                    
                                    payload = {
                                        "filename": filename,
                                        "content": chunk_text,
                                        "onedrive_id": file_meta['id'],
                                        "webUrl": file_meta.get('webUrl', ''),
                                        "last_modified_onedrive": onedrive_last_modified,
                                        "page_number": page_num,
                                        "chunk_index": i,
                                        "total_pages": num_pages
                                    }
                                    
                                    # Vectorize
                                    vector = self.vectorizer.vectorize_text(chunk_text)
                                    
                                    points_to_upsert.append(models.PointStruct(
                                        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id)),
                                        vector=vector,
                                        payload=payload
                                    ))
                                
                            except Exception as pe:
                                print(f"    Error processing page {page_num}: {pe}")
                            # Do NOT delete debug file
                            # finally:
                            #    if os.path.exists(temp_page_path):
                            #        os.remove(temp_page_path)
                                    
                    else:
                        # Fallback for failed PDF splitting - process whole file
                        print(f"  Processing whole file using GenAI OCR...")
                        ocr_result = self.ocr_service.process_with_genai(pdf_path, model_name="gemini-2.5-flash")
                        if ocr_result:
                            chunk_id = f"{file_id}_full_0"
                            payload = {
                                "filename": filename,
                                "content": ocr_result,
                                "onedrive_id": file_meta['id'],
                                "webUrl": file_meta.get('webUrl', ''),
                                "last_modified_onedrive": onedrive_last_modified,
                                "page_number": 1,
                                "chunk_index": 0,
                                "total_pages": 1
                            }
                            vector = self.vectorizer.vectorize_text(ocr_result)
                            points_to_upsert.append(models.PointStruct(
                                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id)),
                                vector=vector,
                                payload=payload
                            ))

                    
                    # Upsert all points for the file in one go
                    if not dry_run and self.qdrant_client and points_to_upsert:
                        self.qdrant_client.upsert(
                            collection_name=self.collection_name,
                            points=points_to_upsert,
                            wait=True
                        )
                        summary['upserted'].append(filename)
                        print(f"  Upserted {len(points_to_upsert)} chunks for {filename} (across {num_pages} pages)")
                    elif dry_run:
                        summary['upserted'].append(filename)
                        print(f"  Dry run: Would upsert {len(points_to_upsert)} chunks for {filename}")
                    
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
                    summary['errors'].append({'filename': filename, 'error': str(e)})
                    
        return summary

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search the Others collection"""
        if not self.qdrant_client:
            raise Exception("Qdrant not initialized")
            
        print(f"Vectorizing query: {query}")
        query_vector = self.vectorizer.vectorize_text(query)
        
        print(f"Searching Qdrant collection: {self.collection_name}")
        results = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True
        )
        
        # Map Qdrant models to plain dicts
        mapped_results = []
        for hit in results:
            mapped_results.append({
                'score': hit.score,
                'content': hit.payload.get('content'),
                'filename': hit.payload.get('filename'),
                'webUrl': hit.payload.get('webUrl')
            })
            
        return mapped_results
