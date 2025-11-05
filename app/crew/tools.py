"""Tools for CrewAI agents to interact with OCR services."""
from typing import Dict, Any
import json

# Try to import tool decorator from various possible locations
try:
    from crewai.tools import tool
except ImportError:
    try:
        from crewai import tool
    except ImportError:
        # If tool decorator doesn't exist, create a no-op decorator
        def tool(func):
            """No-op decorator when CrewAI tool is not available."""
            return func

# Global service instances (will be set by pipeline)
_ocr_extractor = None
_summarizer = None
_failure_logger = None
_db_session = None
_page_contents = None
_progress_callback = None

def set_service_instances(ocr_extractor=None, summarizer=None, failure_logger=None, db_session=None, page_contents=None, progress_callback=None):
    """Set service instances for tools to use."""
    global _ocr_extractor, _summarizer, _failure_logger, _db_session, _page_contents, _progress_callback
    _ocr_extractor = ocr_extractor
    _summarizer = summarizer
    _failure_logger = failure_logger
    _db_session = db_session
    _page_contents = page_contents
    _progress_callback = progress_callback


@tool
def extract_text_from_document(document_path: str, file_type: str) -> str:
    """Extract text from a document using OCR services.

    This tool extracts text from documents using the OCR extraction service.
    Call this tool with the document_path and file_type to extract text.

    Args:
        document_path: Path to the document file (e.g., "/path/to/document.pdf")
        file_type: Type of document - one of: PDF, PNG, JPEG, DOCX, TIFF

    Returns:
        A JSON string containing:
        - raw_text: The extracted text content
        - confidence_score: A number between 0.0 and 1.0 indicating extraction quality
        - metadata: Additional information about the extraction
    """
    global _ocr_extractor, _page_contents, _progress_callback
    if not _ocr_extractor:
        return json.dumps({"error": "OCR extractor service not available", "raw_text": "", "confidence_score": 0.0})

    if not _page_contents:
        return json.dumps({"error": "Page contents not available", "raw_text": "", "confidence_score": 0.0})

    try:
        if file_type == 'DOCX' and len(_page_contents) == 1:
            # DOCX is already text
            text = _page_contents[0].decode('utf-8') if isinstance(_page_contents[0], bytes) else _page_contents[0]
            confidence = _ocr_extractor.confidence_scorer.calculate_confidence(text)
            metadata = {
                "model": "direct_extraction",
                "file_type": file_type,
                "text_length": len(text),
                "word_count": len(text.split()) if text else 0
            }
            result = {
                "raw_text": text,
                "confidence_score": float(confidence),
                "metadata": metadata
            }
        else:
            # Use OCR extractor for images/PDF with progress callback
            raw_text, confidence_score, metadata = _ocr_extractor.extract_from_multiple_pages(
                _page_contents,
                file_type,
                progress_callback=_progress_callback
            )
            result = {
                "raw_text": raw_text,
                "confidence_score": float(confidence_score),
                "metadata": metadata
            }

        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        error_msg = str(e)
        return json.dumps({
            "error": error_msg,
            "raw_text": "",
            "confidence_score": 0.0,
            "metadata": {"error": error_msg}
        })


@tool
def summarize_document_text(text: str) -> str:
    """Summarize extracted document text.
    
    This tool creates a clear and concise summary of the provided text.
    
    Args:
        text: Extracted text to summarize
        
    Returns:
        Summary text string
    """
    global _summarizer
    if not _summarizer:
        return "Summarizer service not available"
    
    try:
        return _summarizer.summarize(text)
    except Exception as e:
        return f"Summarization failed: {str(e)}"


@tool
def log_processing_failure(
    job_id: int,
    document_id: int,
    error_message: str,
    error_type: str,
    retry_count: int
) -> str:
    """Log a processing failure for human review.
    
    Args:
        job_id: Processing job ID
        document_id: Document ID
        error_message: Error message
        error_type: Type of error
        retry_count: Number of retries attempted
        
    Returns:
        Success message
    """
    global _failure_logger, _db_session
    if not _failure_logger or not _db_session:
        return "Failure logger or database session not available"
    
    try:
        _failure_logger.log_failure(
            db=_db_session,
            job_id=job_id,
            document_id=document_id,
            error_message=error_message,
            error_type=error_type,
            retry_count=retry_count
        )
        return "Failure logged successfully"
    except Exception as e:
        return f"Failed to log failure: {str(e)}"

