"""Pydantic models for API request/response."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class UploadResponse(BaseModel):
    """Response model for document upload."""
    document_id: int
    job_id: int
    filename: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: int
    document_id: int
    status: str
    current_stage: Optional[str] = None  # preprocessing, ocr_extraction, summarization, saving_results, failed
    retry_count: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class DocumentResponse(BaseModel):
    """Response model for document retrieval."""
    document_id: int
    filename: str
    file_type: str
    status: str
    upload_date: datetime
    extracted_content: Optional['ExtractedContentResponse'] = None


class ExtractedContentResponse(BaseModel):
    """Response model for extracted content."""
    id: int
    raw_text: str
    summary: Optional[str] = None
    confidence_score: Optional[float] = None
    metadata: Optional[str] = None
    created_at: datetime


class HistoryItemResponse(BaseModel):
    """Response model for history item."""
    document_id: int
    job_id: int
    filename: str
    status: str
    current_stage: Optional[str] = None  # preprocessing, ocr_extraction, summarization, saving_results, failed
    confidence_score: Optional[float] = None
    summary: Optional[str] = None
    upload_date: datetime
    completed_at: Optional[datetime] = None


class HistoryResponse(BaseModel):
    """Response model for history list."""
    items: List[HistoryItemResponse]
    total: int


class FailureLogResponse(BaseModel):
    """Response model for failure log."""
    id: int
    job_id: int
    document_id: int
    error_message: str
    error_type: Optional[str] = None
    retry_count: int
    created_at: datetime
    reviewed: str
    review_notes: Optional[str] = None


class FailureListResponse(BaseModel):
    """Response model for failure list."""
    items: List[FailureLogResponse]
    total: int


# Update forward references
DocumentResponse.model_rebuild()
ExtractedContentResponse.model_rebuild()

