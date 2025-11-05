"""CrewAI task definitions."""
from crewai import Task
from typing import Dict, Any, Optional
from app.crew.agents import AgentFactory
from app.crew.tools import extract_text_from_document, summarize_document_text, log_processing_failure


class TaskFactory:
    """Factory for creating CrewAI tasks."""
    
    def __init__(self):
        self.agent_factory = AgentFactory()
    
    def create_orchestration_task(
        self,
        document_path: str,
        file_type: str,
        document_id: int,
        job_id: int,
        page_contents: list,
        max_retries: int = 2
    ) -> Task:
        """Create master orchestration task that decides and executes the entire document processing workflow."""
        orchestrator_agent = self.agent_factory.create_orchestrator_agent()

        return Task(
            description=f'''Process document {document_path} (type: {file_type}):

STEP 1: Call extract_text_from_document tool with:
- document_path: "{document_path}"
- file_type: "{file_type}"

STEP 2: Call summarize_document_text tool with the raw_text from STEP 1.

STEP 3: Output ONLY valid JSON (no extra text):
{{"raw_text": "<full text from step 1>", "summary": "<full summary from step 2>", "confidence_score": <score from step 1>, "metadata": {{}}, "success": true}}

CRITICAL: Your final answer must be ONLY the JSON object above with actual values. Do not include explanations, markdown formatting, or any text outside the JSON.''',
            agent=orchestrator_agent,
            tools=[extract_text_from_document, summarize_document_text, log_processing_failure],
            expected_output='Pure JSON object with no markdown or extra text: {{"raw_text": "...", "summary": "...", "confidence_score": 0.0, "metadata": {}, "success": true}}'
        )
    
    def create_ocr_task(
        self,
        document_path: str,
        file_type: str,
        document_id: int,
        page_contents: list,
        ocr_extractor,
        document_processor
    ) -> Task:
        """Create OCR extraction task."""
        ocr_agent = self.agent_factory.create_ocr_agent()
        
        # Create tool instance with service
        ocr_tool = extract_text_from_document
        
        return Task(
            description=f'''Extract text from the document located at {document_path}.
            The document type is {file_type}. Document ID: {document_id}.
            
            Use the extract_text_from_document tool to:
            1. Extract all text content from the document
            2. Calculate a confidence score for the extraction quality
            3. Return the results in the expected format
            
            The document has been preprocessed and page contents are ready for extraction.
            Call the extract_text_from_document tool with:
            - document_path: {document_path}
            - file_type: {file_type}
            - page_contents: (preprocessed pages)
            - ocr_extractor: (service instance)''',
            agent=ocr_agent,
            tools=[ocr_tool],
            expected_output='''A dictionary/JSON string containing:
            - "raw_text": The extracted text content (string)
            - "confidence_score": Confidence score between 0.0 and 1.0 (float)
            - "metadata": Additional metadata about the extraction process (dict)'''
        )
    
    def create_summarization_task(
        self,
        extracted_text: str,
        document_id: int,
        summarizer
    ) -> Task:
        """Create document summarization task."""
        summarizer_agent = self.agent_factory.create_summarizer_agent()
        
        # Create tool instance with service
        summary_tool = summarize_document_text
        
        return Task(
            description=f'''Create a comprehensive summary of the extracted document content that captures all essential information.
            Document ID: {document_id}.
            
            Use the summarize_document_text tool to generate a thorough summary that includes:
            1. Executive Overview: Main purpose, objective, and context
            2. Key Topics/Themes: Primary subjects discussed
            3. Critical Findings: Important discoveries, conclusions, or insights
            4. Key Data & Statistics: Significant numbers, metrics, or quantitative information
            5. Important Entities: Key people, organizations, companies, or stakeholders
            6. Timeline/Chronology: Important dates, deadlines, or sequence of events
            7. Recommendations/Actions: Suggested actions, next steps, or recommendations
            8. Key Takeaways: The most important points for the reader
            
            Structure the summary clearly with sections or bullet points.
            Prioritize comprehensiveness - ensure the reader can understand the document's complete context without reading the full text.
            
            Call the summarize_document_text tool with:
            - text: (the extracted text)
            - summarizer: (service instance)''',
            agent=summarizer_agent,
            tools=[summary_tool],
            expected_output='''A comprehensive, well-structured summary that includes:
            - Executive overview with main purpose and context
            - Key topics and themes
            - Critical findings and conclusions
            - Important data, statistics, and metrics
            - Key entities (people, organizations, companies)
            - Timeline and important dates
            - Recommendations and action items
            - Essential takeaways
            The summary should be structured with clear sections or bullet points for easy consumption.''',
            context={
                "extracted_text": extracted_text,
                "document_id": document_id,
                "summarizer": summarizer
            }
        )
    
    def create_supervision_task(
        self,
        job_id: int,
        document_id: int,
        retry_count: int,
        retry_handler,
        failure_logger
    ) -> Task:
        """Create supervision task for monitoring and retry handling."""
        supervisory_agent = self.agent_factory.create_supervisory_agent()
        
        return Task(
            description=f'''Monitor the processing job {job_id} for document {document_id}.
            Current retry count: {retry_count}. Coordinate the OCR and summarization tasks,
            handle any failures, and manage retries according to the configured retry policy.
            If all retries are exhausted, ensure proper failure logging for human review.''',
            agent=supervisory_agent,
            expected_output='''Job status and execution result. If successful, return success
            status. If failed after all retries, ensure failure is logged for human review.''',
            context={
                "job_id": job_id,
                "document_id": document_id,
                "retry_count": retry_count,
                "retry_handler": retry_handler,
                "failure_logger": failure_logger
            }
        )

