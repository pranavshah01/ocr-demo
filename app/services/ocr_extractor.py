"""OCR extraction using OpenAI Vision API."""
import base64
import concurrent.futures
import time
from typing import List, Dict, Tuple
from openai import OpenAI
from app.config import settings
from app.services.confidence_scorer import ConfidenceScorer
from app.utils.logger import get_logger


class OCRExtractor:
    """Extracts text from documents using OpenAI Vision API."""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.confidence_scorer = ConfidenceScorer()
    
    def extract_from_multiple_pages(self, page_contents: List[bytes], file_type: str, progress_callback=None) -> Tuple[str, float, Dict]:
        """Extract text from multiple pages/images (parallel processing).

        Args:
            page_contents: List of file contents as bytes (PDFs sent as single file, images as separate items)
            file_type: Type of document
            progress_callback: Optional callback function(page_num, total_pages) called after each page

        Returns:
            Tuple of (combined_text, average_confidence, metadata)
        """
        logger = get_logger(__name__)
        
        # For DOCX, process synchronously (already text)
        if file_type == 'DOCX':
            docx_start = time.time()
            logger.info("Processing DOCX file (direct text extraction - no OCR needed)")
            all_texts = []
            all_confidences = []
            for page_content in page_contents:
                text = page_content.decode('utf-8') if isinstance(page_content, bytes) else page_content
                confidence = self.confidence_scorer.calculate_confidence(text)
                all_texts.append(text)
                all_confidences.append(confidence)
            docx_time = time.time() - docx_start
            logger.info(f"DOCX text extraction completed in {docx_time:.2f}s")
        
        # For PDFs, process as images (pages converted to images)
        elif file_type == 'PDF':
            logger.info(f"Processing {len(page_contents)} PDF pages as images with OpenAI Vision API")
            # PDF pages are converted to images, process them like regular images

            # Process up to 8 pages concurrently (balance between speed and API rate limits)
            max_workers = min(len(page_contents), 8)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all pages for processing
                futures = {
                    executor.submit(self._process_single_image_sync, idx, page_content, logger): idx 
                    for idx, page_content in enumerate(page_contents)
                }
                
                # Collect results as they complete
                results = []
                for future in concurrent.futures.as_completed(futures):
                    idx = futures[future]
                    try:
                        result = future.result()
                        results.append(result)
                        logger.info(f"Completed PDF page {result[0] + 1}/{len(page_contents)}")

                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(result[0] + 1, len(page_contents))
                    except Exception as e:
                        logger.error(f"Error processing PDF page {idx + 1}: {e}")
                        results.append((idx, f"[Error: {str(e)}]", 0.0))

                        # Still report progress even on error
                        if progress_callback:
                            progress_callback(idx + 1, len(page_contents))
            
            # Sort results by index to maintain order
            results.sort(key=lambda x: x[0])
            all_texts = [result[1] for result in results]
            all_confidences = [result[2] for result in results]
        
        else:
            # For images, process in parallel using ThreadPoolExecutor
            logger.info(f"Processing {len(page_contents)} images in parallel with OpenAI Vision API")

            # Process up to 8 images concurrently (balance between speed and API rate limits)
            max_workers = min(len(page_contents), 8)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all images for processing
                futures = {
                    executor.submit(self._process_single_image_sync, idx, page_content, logger): idx 
                    for idx, page_content in enumerate(page_contents)
                }
                
                # Collect results as they complete
                results = []
                for future in concurrent.futures.as_completed(futures):
                    idx = futures[future]
                    try:
                        result = future.result()
                        results.append(result)
                        logger.info(f"Completed image {result[0] + 1}/{len(page_contents)}")

                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(result[0] + 1, len(page_contents))
                    except Exception as e:
                        logger.error(f"Error processing image {idx + 1}: {e}")
                        results.append((idx, f"[Error: {str(e)}]", 0.0))

                        # Still report progress even on error
                        if progress_callback:
                            progress_callback(idx + 1, len(page_contents))
            
            # Sort results by index to maintain order
            results.sort(key=lambda x: x[0])
            all_texts = [result[1] for result in results]
            all_confidences = [result[2] for result in results]
        
        # Combine all texts
        combined_text = "\n\n--- Page Break ---\n\n".join(all_texts)
        
        # Calculate average confidence
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        
        # Prepare metadata
        metadata = {
            "model": "gpt-4o",
            "file_type": file_type,
            "page_count": len(page_contents),
            "text_length": len(combined_text),
            "word_count": len(combined_text.split()) if combined_text else 0,
            "page_confidences": all_confidences,
            "processing_method": "pdf_to_image_ocr" if file_type == 'PDF' else "image_ocr"
        }
        
        return combined_text, avg_confidence, metadata
    
    def _process_single_image_sync(self, idx: int, image_content: bytes, logger) -> Tuple[int, str, float]:
        """Process a single image synchronously (for thread pool executor)."""
        try:
            image_start = time.time()
            logger.info(f"Processing image {idx + 1} with OpenAI Vision API")
            base64_image = base64.b64encode(image_content).decode('utf-8')

            # Detect image format (PNG or JPEG)
            # JPEG starts with FFD8, PNG starts with 89504E47
            image_format = "jpeg" if image_content[:2] == b'\xff\xd8' else "png"

            api_start = time.time()
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract all text from this image. Preserve the formatting and structure as much as possible."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{image_format};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096
            )

            text = response.choices[0].message.content
            api_time = time.time() - api_start
            confidence = self.confidence_scorer.calculate_confidence(text)
            image_total = time.time() - image_start
            logger.info(f"Image {idx + 1} ({image_format.upper()}) processed in {image_total:.2f}s (API: {api_time:.2f}s). Text length: {len(text)}")
            return (idx, text, confidence)
        except Exception as e:
            logger.error(f"Error processing image {idx + 1}: {e}")
            return (idx, f"[Error extracting text from image {idx + 1}: {str(e)}]", 0.0)
    

