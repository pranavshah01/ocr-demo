"""SQLAlchemy models for OCR pipeline."""
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.db import Base


class Document(Base):
    """Document metadata model."""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    jobs = relationship("ProcessingJob", back_populates="document")
    extracted_content = relationship("ExtractedContent", back_populates="document", uselist=False)


class ProcessingJob(Base):
    """Processing job tracking model."""
    __tablename__ = "processing_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    current_stage = Column(String, nullable=True)  # preprocessing, ocr_extraction, summarization, saving_results, failed
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    document = relationship("Document", back_populates="jobs")
    failure_log = relationship("FailureLog", back_populates="job", uselist=False)


class ExtractedContent(Base):
    """OCR extraction results model."""
    __tablename__ = "extracted_content"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, unique=True)
    raw_text = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)  # Overall confidence score
    extraction_metadata = Column(Text, nullable=True)  # JSON string for additional metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    document = relationship("Document", back_populates="extracted_content")


class FailureLog(Base):
    """Failure logs for human review."""
    __tablename__ = "failure_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("processing_jobs.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    error_message = Column(Text, nullable=False)
    error_type = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed = Column(String, default="pending")  # pending, reviewed, resolved
    review_notes = Column(Text, nullable=True)
    
    # Relationships
    job = relationship("ProcessingJob", back_populates="failure_log")

