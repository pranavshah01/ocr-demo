"""Confidence score calculation for OCR results."""
import re
from typing import Dict, Optional


class ConfidenceScorer:
    """Calculates confidence scores for OCR results."""
    
    def calculate_confidence(self, raw_text: str, metadata: Optional[Dict] = None) -> float:
        """Calculate overall confidence score for OCR extraction.
        
        Args:
            raw_text: Extracted text from OCR
            metadata: Additional metadata from OCR process
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not raw_text or len(raw_text.strip()) == 0:
            return 0.0
        
        score = 0.5  # Base score
        
        # Factor 1: Text length (longer text generally more reliable)
        text_length = len(raw_text.strip())
        if text_length > 100:
            score += 0.1
        elif text_length > 50:
            score += 0.05
        elif text_length < 10:
            score -= 0.1
        
        # Factor 2: Check for common OCR error patterns
        common_errors = [
            r'[|]{2,}',  # Multiple pipes (common OCR error)
            r'[l1]{4,}',  # Multiple l/1 (common confusion)
            r'[o0]{4,}',  # Multiple o/0 (common confusion)
        ]
        
        error_count = sum(len(re.findall(pattern, raw_text)) for pattern in common_errors)
        if error_count == 0:
            score += 0.1
        elif error_count > 5:
            score -= 0.15
        
        # Factor 3: Check for readable words (basic heuristic)
        words = raw_text.split()
        if len(words) > 0:
            # Simple check: words with reasonable length
            reasonable_words = sum(1 for w in words if 2 <= len(w) <= 20)
            word_ratio = reasonable_words / len(words) if words else 0
            score += word_ratio * 0.2
        
        # Factor 4: Check for punctuation and capitalization (indicators of good OCR)
        has_punctuation = bool(re.search(r'[.!?,;:]', raw_text))
        has_capitalization = bool(re.search(r'[A-Z]', raw_text))
        
        if has_punctuation:
            score += 0.05
        if has_capitalization:
            score += 0.05
        
        # Clamp score between 0.0 and 1.0
        score = max(0.0, min(1.0, score))
        
        return round(score, 3)
    
    def format_confidence(self, score: float) -> str:
        """Format confidence score as percentage."""
        return f"{score * 100:.1f}%"

