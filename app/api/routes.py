"""FastAPI routes for OCR pipeline."""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import asyncio
import threading

from app.database.db import get_db, init_db
from app.database.models import Document, ProcessingJob, ExtractedContent, FailureLog
from app.api.schemas import (
    UploadResponse,
    JobStatusResponse,
    DocumentResponse,
    ExtractedContentResponse,
    HistoryResponse,
    HistoryItemResponse,
    FailureListResponse,
    FailureLogResponse
)
from app.services.storage import storage_service
from app.services.document_processor import DocumentProcessor
from app.crew.pipeline import OCRPipeline
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["ocr"])

# Initialize database on startup
init_db()

# Initialize services
document_processor = DocumentProcessor()
pipeline = OCRPipeline()


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a document for OCR processing."""
    document_id = None
    job_id = None
    
    try:
        logger.info(f"Received upload request for file: {file.filename}")
        
        # Read file content with timeout protection
        try:
            content = await asyncio.wait_for(file.read(), timeout=60.0)  # 60 second timeout for large files
        except asyncio.TimeoutError:
            raise HTTPException(status_code=408, detail="File upload timeout - file too large or connection too slow")

        # Check file size (100MB limit)
        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large - maximum size is 100MB")
        
        logger.debug(f"File size: {len(content)} bytes")
        
        # Save file (synchronous, fast)
        try:
            file_path = storage_service.save_upload(content, file.filename)
            logger.debug(f"File saved to: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
        # Detect file type (synchronous, fast)
        try:
            file_type, mime_type = document_processor.detect_format(file_path)
            file_size = document_processor.get_file_size(file_path)
        except Exception as e:
            logger.error(f"Failed to detect file format: {e}")
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {str(e)}")
        
        # Create document record (synchronous, fast)
        try:
            document = Document(
                filename=file.filename,
                file_path=file_path,
                file_type=file_type,
                file_size=file_size,
                status="pending"
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            document_id = document.id
            logger.info(f"Document created: ID {document_id}")
        except Exception as e:
            logger.error(f"Failed to create document record: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        # Create processing job (synchronous, fast)
        try:
            job = ProcessingJob(
                document_id=document_id,
                status="pending"
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = job.id
            logger.info(f"Job created: ID {job_id}")
        except Exception as e:
            logger.error(f"Failed to create job record: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        # Prepare response BEFORE starting background processing
        response_data = UploadResponse(
            document_id=document_id,
            job_id=job_id,
            filename=file.filename,
            status="pending",
            message="Document uploaded successfully. Processing started."
        )
        
        # Start processing in background thread (AFTER preparing response)
        def process_in_background():
            from app.database.db import SessionLocal
            import asyncio
            background_db = SessionLocal()
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    logger.info(f"Starting background processing for document {document_id}, job {job_id}")
                    # Run the async pipeline
                    loop.run_until_complete(
                        pipeline.process_document(background_db, document_id, job_id)
                    )
                    logger.info(f"Background processing completed for document {document_id}, job {job_id}")
                finally:
                    # Clean up event loop
                    loop.close()
            except Exception as e:
                logger.exception(f"Background processing task failed for document {document_id}, job {job_id}: {e}")
                # Mark job as failed
                try:
                    job = background_db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
                    if job:
                        job.status = "failed"
                        job.error_message = str(e)
                        job.completed_at = datetime.utcnow()
                        background_db.commit()
                except Exception as db_err:
                    logger.error(f"Failed to update job status: {db_err}")
            finally:
                background_db.close()
        
        # Start background thread (non-daemon so it doesn't get killed on reload)
        thread = threading.Thread(target=process_in_background, daemon=False, name=f"OCR-Processing-{job_id}")
        thread.start()
        logger.info(f"Background thread started for document {document_id}, job {job_id}")
        
        # Return response immediately (processing happens in background)
        return response_data
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Get processing job status."""
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return JobStatusResponse(
            job_id=job.id,
            document_id=job.document_id,
            status=job.status,
            current_stage=job.current_stage,
            retry_count=job.retry_count,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_message=job.error_message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job status: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch job status")


@router.get("/document/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Get document with extracted content."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    extracted_content = db.query(ExtractedContent).filter(
        ExtractedContent.document_id == document_id
    ).first()
    
    extracted_content_response = None
    if extracted_content:
        extracted_content_response = ExtractedContentResponse(
            id=extracted_content.id,
            raw_text=extracted_content.raw_text,
            summary=extracted_content.summary,
            confidence_score=extracted_content.confidence_score,
            metadata=extracted_content.extraction_metadata,
            created_at=extracted_content.created_at
        )
    
    return DocumentResponse(
        document_id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        status=document.status,
        upload_date=document.upload_date,
        extracted_content=extracted_content_response
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get processing history."""
    # Query documents with their jobs and extracted content, ordered by upload_date (newest first)
    documents = db.query(Document).order_by(Document.upload_date.desc()).offset(skip).limit(limit).all()
    
    items = []
    for doc in documents:
        # Get latest job
        job = db.query(ProcessingJob).filter(
            ProcessingJob.document_id == doc.id
        ).order_by(ProcessingJob.created_at.desc()).first()
        
        # Get extracted content for confidence score and summary
        extracted = db.query(ExtractedContent).filter(
            ExtractedContent.document_id == doc.id
        ).first()
        
        items.append(HistoryItemResponse(
            document_id=doc.id,
            job_id=job.id if job else 0,
            filename=doc.filename,
            status=doc.status,
            current_stage=job.current_stage if job else None,
            confidence_score=extracted.confidence_score if extracted else None,
            summary=extracted.summary if extracted else None,
            upload_date=doc.upload_date,
            completed_at=job.completed_at if job else None
        ))
    
    total = db.query(Document).count()
    
    return HistoryResponse(items=items, total=total)


@router.get("/failures", response_model=FailureListResponse)
async def get_failures(
    reviewed: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get failure logs for human review."""
    from app.services.failure_logger import FailureLogger
    failure_logger = FailureLogger()
    
    failures = failure_logger.get_failures(db, reviewed=reviewed, limit=limit)
    
    items = [
        FailureLogResponse(
            id=f.id,
            job_id=f.job_id,
            document_id=f.document_id,
            error_message=f.error_message,
            error_type=f.error_type,
            retry_count=f.retry_count,
            created_at=f.created_at,
            reviewed=f.reviewed,
            review_notes=f.review_notes
        )
        for f in failures
    ]
    
    return FailureListResponse(items=items, total=len(items))

