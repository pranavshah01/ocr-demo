"""File storage management service."""
import os
import shutil
from pathlib import Path
from typing import Optional
from app.config import settings


class StorageService:
    """Handles file storage operations."""
    
    def __init__(self):
        self.upload_dir = Path(settings.upload_dir)
        self.processed_dir = Path(settings.processed_dir)
        self.reports_dir = Path(settings.reports_dir)
        
        # Ensure directories exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def save_upload(self, file_content: bytes, filename: str) -> str:
        """Save uploaded file and return file path."""
        file_path = self.upload_dir / filename
        with open(file_path, "wb") as f:
            f.write(file_content)
        return str(file_path)
    
    def get_upload_path(self, filename: str) -> Path:
        """Get path to uploaded file."""
        return self.upload_dir / filename
    
    def save_processed(self, content: str, document_id: int, suffix: str = ".txt") -> str:
        """Save processed content."""
        file_path = self.processed_dir / f"{document_id}{suffix}"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return str(file_path)
    
    def save_failure_report(self, report_content: str, job_id: int) -> str:
        """Save failure report for human review."""
        file_path = self.reports_dir / f"failure_{job_id}.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        return str(file_path)
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file."""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                return True
            return False
        except Exception:
            return False


# Global storage service instance
storage_service = StorageService()

