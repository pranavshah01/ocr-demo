"""Main pipeline coordinator using CrewAI."""
import asyncio
import time
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any, Optional
import json

from app.database.models import Document, ProcessingJob, ExtractedContent
from app.services.document_processor import DocumentProcessor
from app.services.ocr_extractor import OCRExtractor
from app.services.summarizer import Summarizer
from app.services.retry_handler import RetryHandler
from app.services.failure_logger import FailureLogger
from app.crew.crew_manager import CrewManager
from app.crew.tasks import TaskFactory
from app.crew.tools import set_service_instances
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OCRPipeline:
    """Main OCR pipeline orchestrator."""
    
    def __init__(self):
        self.document_processor = DocumentProcessor()
        self.ocr_extractor = OCRExtractor()
        self.summarizer = Summarizer()
        self.retry_handler = RetryHandler()
        self.failure_logger = FailureLogger()
        self.crew_manager = CrewManager()
        self.task_factory = TaskFactory()
    
    async def process_document(
        self,
        db: Session,
        document_id: int,
        job_id: int
    ) -> Dict[str, Any]:
        """Process a document through the OCR pipeline using CrewAI orchestrator.
        
        The pipeline always delegates to CrewAI orchestrator agent, which decides
        which processing methods to use based on document characteristics.
        
        Args:
            db: Database session
            document_id: Document ID
            job_id: Processing job ID
            
        Returns:
            Dictionary with processing result
        """
        # Get document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document {document_id} not found")
            return {"success": False, "error": "Document not found"}
        
        # Update job status
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found for document {document_id}")
            return {"success": False, "error": "Job not found"}
        
        logger.info(f"Starting CrewAI orchestrated processing for document {document_id}, job {job_id}, file: {document.filename}")

        try:
            # Update job status to processing
            job.status = "processing"
            job.started_at = datetime.utcnow()
            job.current_stage = "preprocessing"
            db.commit()
            # Stage 1: Preprocessing - Detect document format
            preprocessing_start = time.time()
            logger.info(f"Stage: Preprocessing - Format detection")
            try:
                file_type, mime_type = self.document_processor.detect_format(document.file_path)
            except Exception as e:
                raise Exception(f"Format detection failed: {str(e)}")

            # Stage 1: Preprocessing - Extract pages
            logger.info(f"Stage: Preprocessing - Page extraction for {file_type}")
            try:
                page_contents = self.document_processor.preprocess_for_ocr(
                    document.file_path,
                    file_type
                )
            except Exception as e:
                error_msg = f"Page extraction failed for {file_type}: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)

            preprocessing_time = time.time() - preprocessing_start
            logger.info(f"Document preprocessed in {preprocessing_time:.2f}s. Type: {file_type}, Pages: {len(page_contents)}")
            
            # Set service instances for CrewAI tools
            set_service_instances(
                ocr_extractor=self.ocr_extractor,
                summarizer=self.summarizer,
                failure_logger=self.failure_logger,
                db_session=db,
                page_contents=page_contents
            )
            
            # Update stage: OCR Extraction (includes both OCR and summarization via orchestrator)
            job.current_stage = "ocr_extraction"
            db.commit()
            logger.info(f"Stage: OCR Extraction - Starting CrewAI orchestration")
            
            # Execute CrewAI orchestration with retry
            async def execute_orchestration_task():
                orchestration_start = time.time()
                logger.info("Delegating to CrewAI orchestrator agent for OCR extraction and summarization")

                task_creation_start = time.time()
                try:
                    # Create master orchestration task
                    orchestration_task = self.task_factory.create_orchestration_task(
                        document_path=document.file_path,
                        file_type=file_type,
                        document_id=document_id,
                        job_id=job_id,
                        page_contents=page_contents,
                        max_retries=settings.max_retries
                    )
                    task_creation_time = time.time() - task_creation_start
                    logger.info(f"Task creation took {task_creation_time:.2f}s")
                except Exception as e:
                    raise Exception(f"Task creation failed: {str(e)}")
                
                crew_creation_start = time.time()
                try:
                    # Create crew with orchestration task
                    crew = self.crew_manager.create_crew([orchestration_task])
                    crew_creation_time = time.time() - crew_creation_start
                    logger.info(f"Crew creation took {crew_creation_time:.2f}s")
                except Exception as e:
                    raise Exception(f"Crew initialization failed: {str(e)}")
                
                crew_execution_start = time.time()
                try:
                    # Execute crew (async, runs in thread pool)
                    logger.info("Starting CrewAI execution...")
                    crew_result = await self.crew_manager.execute_crew(crew)
                    crew_execution_time = time.time() - crew_execution_start
                    logger.info(f"CrewAI execution took {crew_execution_time:.2f}s")
                except Exception as e:
                    raise Exception(f"Agent execution failed: {str(e)}")
                
                orchestration_total = time.time() - orchestration_start
                logger.info(f"Total orchestration time: {orchestration_total:.2f}s (task: {task_creation_time:.2f}s, crew: {crew_creation_time:.2f}s, execution: {crew_execution_time:.2f}s)")
                
                if not crew_result["success"]:
                    error_detail = crew_result.get('error', 'Unknown error')
                    raise Exception(f"Document processing failed: {error_detail}")
                
                # Note: The orchestrator handles both OCR and summarization in one task
                # Stage updates are handled outside this function for better DB session management
                
                # Parse result from crew output
                crew_output = str(crew_result["result"])
                logger.info(f"CrewAI output length: {len(crew_output)} chars")

                # Try to parse as JSON
                import re
                try:
                    # First, try direct JSON parse
                    result_dict = json.loads(crew_output)
                    if "raw_text" in result_dict and "summary" in result_dict:
                        return {
                            "raw_text": result_dict.get("raw_text", ""),
                            "summary": result_dict.get("summary", ""),
                            "confidence_score": result_dict.get("confidence_score", 0.0),
                            "metadata": result_dict.get("metadata", {}),
                            "success": True
                        }
                except json.JSONDecodeError:
                    pass

                # Try to extract JSON from markdown code blocks or surrounding text
                json_patterns = [
                    r'```json\s*(\{.*?\})\s*```',  # JSON in markdown code block
                    r'```\s*(\{.*?\})\s*```',       # JSON in code block without language
                    r'(\{[^{}]*"raw_text"[^{}]*"summary"[^{}]*\})',  # Inline JSON with both fields
                ]

                for pattern in json_patterns:
                    match = re.search(pattern, crew_output, re.DOTALL)
                    if match:
                        try:
                            result_dict = json.loads(match.group(1))
                            if "raw_text" in result_dict and "summary" in result_dict:
                                logger.info("Successfully parsed JSON from crew output")
                                return {
                                    "raw_text": result_dict.get("raw_text", ""),
                                    "summary": result_dict.get("summary", ""),
                                    "confidence_score": result_dict.get("confidence_score", 0.0),
                                    "metadata": result_dict.get("metadata", {}),
                                    "success": True
                                }
                        except json.JSONDecodeError:
                            continue

                # Fallback: Extract structured content
                logger.warning("Could not parse as JSON, attempting structured extraction")
                raw_text = ""
                summary = ""
                confidence_score = 0.0

                # Look for markdown headings (summary structure)
                if '##' in crew_output:
                    # Extract everything with markdown headers as summary
                    summary = crew_output.strip()
                    logger.info("Using full output as structured summary")
                else:
                    # Try to split by common delimiters
                    parts = crew_output.split('\n\n', 1)
                    if len(parts) > 1:
                        summary = parts[1].strip()
                    else:
                        summary = crew_output.strip()
                    logger.warning("No structured format detected, using output as summary")

                return {
                    "raw_text": raw_text,
                    "summary": summary,
                    "confidence_score": confidence_score,
                    "metadata": {"parsing_method": "fallback"},
                    "success": True
                }
            
            # Execute with retry
            try:
                result, success, error = await self.retry_handler.execute_with_retry(
                    execute_orchestration_task
                )

                # Update stage immediately after orchestration completes
                # (orchestration does both OCR and summarization, but we update here for UI visibility)
                if success and result:
                    job.current_stage = "summarization"
                    db.commit()
                    logger.info(f"Stage: Summarization - Orchestration complete, parsing results")

            except Exception as e:
                logger.error(f"Orchestration execution error: {e}")
                success = False
                error = str(e)
                result = None
            
            if not success:
                # Update job status and retry count
                logger.error(f"Document processing failed after retries for document {document_id}, job {job_id}: {error}")
                job.status = "failed"
                job.current_stage = "failed"
                job.error_message = str(error) if error else "Unknown error"
                job.retry_count = settings.max_retries
                job.completed_at = datetime.utcnow()
                db.commit()
                logger.info(f"Job {job_id} status updated to failed")
                
                # Log failure
                self.failure_logger.log_failure(
                    db=db,
                    job_id=job_id,
                    document_id=document_id,
                    error_message=error or "Unknown error",
                    error_type="orchestration_error",
                    retry_count=settings.max_retries
                )
                
                return {"success": False, "error": error}
            
            # Extract results
            raw_text = result.get("raw_text", "")
            summary_text = result.get("summary", "")
            confidence_score = result.get("confidence_score", 0.0)
            metadata = result.get("metadata", {})
            
            logger.info(f"Processing completed. Text length: {len(raw_text)}, Summary length: {len(summary_text)}, Confidence: {confidence_score:.3f}")
            
            # Update stage: Saving Results
            job.current_stage = "saving_results"
            db.commit()
            
            # Validate results
            if not raw_text and not summary_text:
                logger.error(f"No content extracted for document {document_id}")
                raise Exception("Extraction failed: No text or summary generated")

            if not raw_text:
                logger.warning(f"No raw text extracted for document {document_id}, using summary as fallback")
                # Use summary as fallback if raw_text is missing
                if summary_text:
                    raw_text = summary_text[:1000]

            if not summary_text:
                logger.warning(f"No summary generated for document {document_id}, using truncated text as fallback")
                # Generate a basic summary if missing
                summary_text = raw_text[:500] + "..." if raw_text else "No summary available"
            
            # Save extracted content
            extracted_content = ExtractedContent(
                document_id=document_id,
                raw_text=raw_text,
                summary=summary_text,
                confidence_score=confidence_score,
                extraction_metadata=json.dumps(metadata)
            )
            db.add(extracted_content)
            
            # Update document and job status
            document.status = "completed"
            job.status = "completed"
            job.current_stage = None  # Clear stage when completed
            job.completed_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Processing completed successfully for document {document_id}, job {job_id}")
            
            return {
                "success": True,
                "document_id": document_id,
                "job_id": job_id,
                "confidence_score": confidence_score,
                "text_length": len(raw_text),
                "summary_length": len(summary_text) if summary_text else 0
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Unexpected error in pipeline for document {document_id}, job {job_id}: {error_msg}")

            # Update job status
            try:
                job.status = "failed"
                job.current_stage = "failed"
                job.error_message = error_msg
                job.completed_at = datetime.utcnow()
                db.commit()
                logger.info(f"Job {job_id} status updated to failed")
            except Exception as db_error:
                logger.error(f"Failed to update job status: {db_error}")
                # Try with a fresh query as last resort
                try:
                    fresh_job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
                    if fresh_job:
                        fresh_job.status = "failed"
                        fresh_job.current_stage = "failed"
                        fresh_job.error_message = error_msg
                        fresh_job.completed_at = datetime.utcnow()
                        db.commit()
                        logger.info(f"Job {job_id} status updated using fresh query")
                except Exception as final_error:
                    logger.error(f"Critical: Could not update job status: {final_error}")
            
            # Log failure
            self.failure_logger.log_failure(
                db=db,
                job_id=job_id,
                document_id=document_id,
                error_message=error_msg,
                error_type="pipeline_error",
                retry_count=job.retry_count
            )
            
            return {"success": False, "error": error_msg}

