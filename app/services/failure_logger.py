"""Failure logging service for human review."""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from app.database.models import FailureLog, ProcessingJob, Document
from app.services.storage import storage_service
import json


class FailureLogger:
    """Logs failures for human review."""
    
    def log_failure(
        self,
        db: Session,
        job_id: int,
        document_id: int,
        error_message: str,
        error_type: Optional[str] = None,
        retry_count: int = 0,
        additional_context: Optional[dict] = None
    ) -> FailureLog:
        """Log a failure for human review.
        
        Args:
            db: Database session
            job_id: Processing job ID
            document_id: Document ID
            error_message: Error message
            error_type: Type of error (optional)
            retry_count: Number of retries attempted
            additional_context: Additional context data
            
        Returns:
            Created FailureLog instance
        """
        # Create failure log entry
        failure_log = FailureLog(
            job_id=job_id,
            document_id=document_id,
            error_message=error_message,
            error_type=error_type,
            retry_count=retry_count
        )
        
        db.add(failure_log)
        db.commit()
        db.refresh(failure_log)
        
        # Create failure report file
        report_content = self._generate_report(failure_log, additional_context)
        report_path = storage_service.save_failure_report(report_content, job_id)
        
        return failure_log
    
    def _generate_report(self, failure_log: FailureLog, additional_context: Optional[dict] = None) -> str:
        """Generate failure report content."""
        report_lines = [
            "=" * 80,
            "OCR PIPELINE FAILURE REPORT",
            "=" * 80,
            "",
            f"Failure ID: {failure_log.id}",
            f"Job ID: {failure_log.job_id}",
            f"Document ID: {failure_log.document_id}",
            f"Timestamp: {failure_log.created_at}",
            f"Retry Count: {failure_log.retry_count}",
            "",
            "ERROR DETAILS",
            "-" * 80,
            f"Error Type: {failure_log.error_type or 'Unknown'}",
            f"Error Message: {failure_log.error_message}",
            ""
        ]
        
        if additional_context:
            report_lines.extend([
                "ADDITIONAL CONTEXT",
                "-" * 80,
                json.dumps(additional_context, indent=2),
                ""
            ])
        
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    def get_failures(self, db: Session, reviewed: Optional[str] = None, limit: int = 100) -> list[FailureLog]:
        """Get failure logs, optionally filtered by review status.
        
        Args:
            db: Database session
            reviewed: Filter by review status (pending, reviewed, resolved)
            limit: Maximum number of results
            
        Returns:
            List of FailureLog instances
        """
        query = db.query(FailureLog)
        
        if reviewed:
            query = query.filter(FailureLog.reviewed == reviewed)
        
        return query.order_by(FailureLog.created_at.desc()).limit(limit).all()
    
    def mark_reviewed(self, db: Session, failure_id: int, review_notes: Optional[str] = None) -> FailureLog:
        """Mark a failure as reviewed.
        
        Args:
            db: Database session
            failure_id: Failure log ID
            review_notes: Optional review notes
            
        Returns:
            Updated FailureLog instance
        """
        failure_log = db.query(FailureLog).filter(FailureLog.id == failure_id).first()
        if failure_log:
            failure_log.reviewed = "reviewed"
            if review_notes:
                failure_log.review_notes = review_notes
            db.commit()
            db.refresh(failure_log)
        return failure_log

