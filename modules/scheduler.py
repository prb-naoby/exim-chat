"""
Ingestion Scheduler Module

Schedules and runs the ingestion pipelines every 30 minutes.
Uses APScheduler with skip-if-running logic to prevent overlapping jobs.
Logs ingestion results to database for admin dashboard tracking.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from modules.database import log_ingestion_run, get_db_connection

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None

# Lock flags to prevent concurrent runs
_sop_running = False
_insw_running = False
_cases_running = False
_general_running = False


def log_ingestion_to_db(pipeline_name: str, status: str, summary: dict):
    """Log ingestion run to database for admin dashboard"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ingestion_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                files_processed INTEGER DEFAULT 0,
                files_upserted INTEGER DEFAULT 0,
                files_skipped INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                error_details TEXT,
                summary TEXT
            )
        ''')
        
        import json
        cursor.execute('''
            INSERT INTO ingestion_logs 
            (pipeline_name, status, completed_at, files_processed, files_upserted, files_skipped, errors, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            pipeline_name,
            status,
            datetime.now(ZoneInfo('Asia/Jakarta')).isoformat(),
            summary.get('total_files', 0),
            len(summary.get('upserted', [])),
            len(summary.get('skipped', [])),
            len(summary.get('errors', [])),
            json.dumps(summary)
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Logged ingestion run for {pipeline_name}: {status}")
    except Exception as e:
        logger.error(f"Failed to log ingestion run: {e}")


async def run_sop_ingestion():
    """Run SOP ingestion pipeline"""
    global _sop_running
    
    if _sop_running:
        logger.info("SOP ingestion already running, skipping...")
        return
    
    _sop_running = True
    logger.info("Starting scheduled SOP ingestion...")
    
    try:
        # Import here to avoid circular imports
        import os
        from dotenv import load_dotenv
        from datetime import timezone
        from ingestion.sop.sop_ingestion_pipeline import SOPIngestionPipeline
        
        load_dotenv()
        
        pipeline = SOPIngestionPipeline(
            tenant_id=os.getenv('MS_TENANT_ID'),
            client_id=os.getenv('MS_CLIENT_ID'),
            client_secret=os.getenv('MS_CLIENT_SECRET'),
            drive_id=os.getenv('ONEDRIVE_DRIVE_ID'),
            folder_path=os.getenv('SOP_FOLDER_PATH'),
            qdrant_url=os.getenv('SOP_QDRANT_URL'),
            qdrant_api_key=os.getenv('SOP_QDRANT_API_KEY'),
            embedding_model=os.getenv('EMBEDDING_MODEL'),
            gemini_api_key=os.getenv('GEMINI_API_KEY'),
            llm_model=os.getenv('LLM_MODEL'),
            vector_size=int(os.getenv('VECTOR_SIZE', '768')),
            skip_qdrant_init=False
        )
        
        # Sync from a recent time window (last 24 hours) for incremental updates
        from datetime import timedelta
        last_sync = datetime.now(timezone.utc) - timedelta(hours=24)
        summary = await asyncio.to_thread(pipeline.sync_and_upsert, last_sync_date=last_sync, dry_run=False)
        
        log_ingestion_to_db('SOP', 'success', summary)
        logger.info(f"SOP ingestion completed: {len(summary.get('upserted', []))} upserted, {len(summary.get('skipped', []))} skipped")
        
    except Exception as e:
        logger.error(f"SOP ingestion failed: {e}")
        log_ingestion_to_db('SOP', 'error', {'error': str(e)})
    finally:
        _sop_running = False


async def run_insw_ingestion():
    """Run INSW (HS Code) ingestion pipeline"""
    global _insw_running
    
    if _insw_running:
        logger.info("INSW ingestion already running, skipping...")
        return
    
    _insw_running = True
    logger.info("Starting scheduled INSW ingestion...")
    
    try:
        import os
        from dotenv import load_dotenv
        from datetime import timezone, timedelta
        from ingestion.ingestion_pipeline import IngestionPipeline
        
        load_dotenv()
        
        pipeline = IngestionPipeline(
            tenant_id=os.getenv('MS_TENANT_ID'),
            client_id=os.getenv('MS_CLIENT_ID'),
            client_secret=os.getenv('MS_CLIENT_SECRET'),
            drive_id=os.getenv('ONEDRIVE_DRIVE_ID'),
            folder_path=os.getenv('INSW_FOLDER_PATH'),
            qdrant_url=os.getenv('INSW_QDRANT_URL'),
            qdrant_api_key=os.getenv('INSW_QDRANT_API_KEY'),
            embedding_model=os.getenv('EMBEDDING_MODEL'),
            gemini_api_key=os.getenv('GEMINI_API_KEY'),
            vector_size=int(os.getenv('VECTOR_SIZE', '768')),
            skip_qdrant_init=False
        )
        
        last_sync = datetime.now(timezone.utc) - timedelta(hours=24)
        summary = await asyncio.to_thread(pipeline.sync_and_upsert, last_sync_date=last_sync, dry_run=False)
        
        log_ingestion_to_db('INSW', 'success', summary)
        logger.info(f"INSW ingestion completed: {len(summary.get('upserted', []))} upserted")
        
    except Exception as e:
        logger.error(f"INSW ingestion failed: {e}")
        log_ingestion_to_db('INSW', 'error', {'error': str(e)})
    finally:
        _insw_running = False


async def run_cases_ingestion():
    """Run Cases Q&A ingestion pipeline"""
    global _cases_running
    
    if _cases_running:
        logger.info("Cases ingestion already running, skipping...")
        return
    
    _cases_running = True
    logger.info("Starting scheduled Cases ingestion...")
    
    try:
        import os
        from dotenv import load_dotenv
        from ingestion.cases.cases_ingestion_pipeline import CasesIngestionPipeline
        
        load_dotenv()
        
        pipeline = CasesIngestionPipeline(
            tenant_id=os.getenv('MS_TENANT_ID'),
            client_id=os.getenv('MS_CLIENT_ID'),
            client_secret=os.getenv('MS_CLIENT_SECRET'),
            user_id=os.getenv('ONEDRIVE_DRIVE_ID'),
            folder_path=os.getenv('CASES_FOLDER_PATH', 'AI/Cases'),
            qdrant_url=os.getenv('SOP_QDRANT_URL'),  # Use same Qdrant as SOP
            qdrant_api_key=os.getenv('SOP_QDRANT_API_KEY'),
            collection_name=os.getenv('CASES_QDRANT_COLLECTION_NAME', 'cases_qna'),
            gemini_api_key=os.getenv('GEMINI_API_KEY'),
            embedding_model=os.getenv('EMBEDDING_MODEL', 'models/text-embedding-004'),
            vector_size=int(os.getenv('VECTOR_SIZE', '768')),
            batch_size=int(os.getenv('BATCH_SIZE', '50'))
        )
        
        summary = await asyncio.to_thread(pipeline.sync_and_upsert, dry_run=False)
        
        log_ingestion_to_db('Cases', 'success', summary)
        logger.info(f"Cases ingestion completed: {len(summary.get('upserted', []))} upserted")
        
    except Exception as e:
        logger.error(f"Cases ingestion failed: {e}")
        log_ingestion_to_db('Cases', 'error', {'error': str(e)})
    finally:
        _cases_running = False


async def run_general_ingestion():
    """Run General (formerly Others) ingestion pipeline"""
    global _general_running
    
    if _general_running:
        logger.info("General ingestion already running, skipping...")
        return
    
    _general_running = True
    logger.info("Starting scheduled General ingestion...")
    
    try:
        import os
        from dotenv import load_dotenv
        from datetime import timezone, timedelta
        from ingestion.others.others_ingestion_pipeline import OthersIngestionPipeline
        
        load_dotenv()
        
        folder = os.getenv('GENERAL_FOLDER_PATH', os.getenv('OTHERS_FOLDER_PATH', 'AI/Others'))
        collection = os.getenv('GENERAL_QDRANT_COLLECTION_NAME', os.getenv('OTHERS_QDRANT_COLLECTION_NAME', 'others_documents'))
        
        pipeline = OthersIngestionPipeline(
            tenant_id=os.getenv('MS_TENANT_ID'),
            client_id=os.getenv('MS_CLIENT_ID'),
            client_secret=os.getenv('MS_CLIENT_SECRET'),
            drive_id=os.getenv('ONEDRIVE_DRIVE_ID'),
            folder_path=folder,
            qdrant_url=os.getenv('SOP_QDRANT_URL'),
            qdrant_api_key=os.getenv('SOP_QDRANT_API_KEY'),
            qdrant_collection_name=collection,
            embedding_model=os.getenv('EMBEDDING_MODEL'),
            gemini_api_key=os.getenv('GEMINI_API_KEY'),
            vector_size=int(os.getenv('VECTOR_SIZE', '768')),
            skip_qdrant_init=False
        )
        
        if pipeline.qdrant_client:
            pipeline._init_collection(int(os.getenv('VECTOR_SIZE', '768')))
        
        last_sync = datetime.now(timezone.utc) - timedelta(hours=24)
        summary = await asyncio.to_thread(pipeline.sync_and_upsert, last_sync_date=last_sync, dry_run=False)
        
        log_ingestion_to_db('General', 'success', summary)
        logger.info(f"General ingestion completed: {len(summary.get('upserted', []))} upserted")
        
    except Exception as e:
        logger.error(f"General ingestion failed: {e}")
        log_ingestion_to_db('General', 'error', {'error': str(e)})
    finally:
        _general_running = False


def start_scheduler():
    """Start the ingestion scheduler"""
    global scheduler
    
    if scheduler is not None and scheduler.running:
        logger.warning("Scheduler already running")
        return
    
    scheduler = AsyncIOScheduler(timezone=ZoneInfo('Asia/Jakarta'))
    
    now = datetime.now(ZoneInfo('Asia/Jakarta'))
    
    # Schedule all pipelines to run every 30 minutes
    # All run immediately on startup, staggered by 2 minutes to prevent overload
    
    scheduler.add_job(
        run_sop_ingestion,
        trigger=IntervalTrigger(minutes=30),
        id='sop_ingestion',
        name='SOP Ingestion Pipeline',
        replace_existing=True,
        next_run_time=now  # Run immediately
    )
    
    scheduler.add_job(
        run_insw_ingestion,
        trigger=IntervalTrigger(minutes=30),
        id='insw_ingestion', 
        name='INSW Ingestion Pipeline',
        replace_existing=True,
        next_run_time=now + timedelta(minutes=2)  # 2 min after SOP
    )
    
    scheduler.add_job(
        run_cases_ingestion,
        trigger=IntervalTrigger(minutes=30),
        id='cases_ingestion',
        name='Cases Ingestion Pipeline',
        replace_existing=True,
        next_run_time=now + timedelta(minutes=4)  # 4 min after SOP
    )
    
    scheduler.add_job(
        run_general_ingestion,
        trigger=IntervalTrigger(minutes=30),
        id='general_ingestion',
        name='General Ingestion Pipeline',
        replace_existing=True,
        next_run_time=now + timedelta(minutes=6)  # 6 min after SOP
    )
    
    scheduler.start()
    logger.info("Ingestion scheduler started - running every 30 minutes")


def stop_scheduler():
    """Stop the ingestion scheduler"""
    global scheduler
    
    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Ingestion scheduler stopped")


def get_scheduler_status() -> dict:
    """Get current scheduler status for admin dashboard"""
    global scheduler
    
    if scheduler is None or not scheduler.running:
        return {'running': False, 'jobs': []}
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger)
        })
    
    return {
        'running': True,
        'jobs': jobs,
        'locks': {
            'sop_running': _sop_running,
            'insw_running': _insw_running,
            'cases_running': _cases_running,
            'general_running': _general_running
        }
    }
