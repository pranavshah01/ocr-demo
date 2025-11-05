"""CrewAI agent definitions."""
from crewai import Agent
from langchain_openai import ChatOpenAI
from app.config import settings
from app.crew.tools import (
    extract_text_from_document, 
    summarize_document_text, 
    log_processing_failure
)


class AgentFactory:
    """Factory for creating CrewAI agents."""
    
    def __init__(self):
        # Use gpt-4o for better instruction following (critical for tool orchestration)
        # gpt-4o-mini was slower because it needed more iterations to follow instructions correctly
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            openai_api_key=settings.openai_api_key,
            timeout=60,
            max_retries=2
        )
    
    def create_orchestrator_agent(self) -> Agent:
        """Create orchestrator agent that decides processing methods."""
        return Agent(
            role='Document Processing Orchestrator',
            goal='Execute 2 tool calls: extract_text_from_document then summarize_document_text, return JSON',
            backstory='Execute tools in order. No analysis. Return JSON.',
            verbose=False,  # Disable verbose for faster execution
            allow_delegation=False,  # Disable delegation for faster execution
            llm=self.llm,
            tools=[extract_text_from_document, summarize_document_text, log_processing_failure],
            max_iter=5,  # Limit iterations but allow enough for tool calls (default is 15)
            memory=False  # Don't store agent memory (reduces overhead)
        )
    
    def create_supervisory_agent(self) -> Agent:
        """Create supervisory agent for monitoring pipeline."""
        return Agent(
            role='Pipeline Supervisor',
            goal='Monitor and coordinate the OCR pipeline, handle retries, and log failures',
            backstory='''You are an experienced pipeline supervisor responsible for ensuring 
            document processing tasks complete successfully. You monitor the entire pipeline,
            coordinate between agents, handle retries when failures occur, and ensure proper
            logging of all operations.
            
            You have access to logging tools to record failures. Use the log_processing_failure
            tool when tasks fail after all retries have been exhausted.''',
            verbose=True,
            allow_delegation=True,
            llm=self.llm,
            tools=[log_processing_failure]
        )
    
    def create_ocr_agent(self) -> Agent:
        """Create OCR agent for text extraction."""
        return Agent(
            role='OCR Specialist',
            goal='Extract text from documents with high accuracy and confidence scoring',
            backstory='''You are an expert in Optical Character Recognition (OCR) with deep
            knowledge of document processing. Your specialty is extracting text from various
            document formats including PDFs, images, and Word documents. You ensure high
            quality extraction and provide confidence scores for the results.
            
            You have access to tools that allow you to extract text from documents. Always use
            the extract_text_from_document tool to perform the actual extraction.''',
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[extract_text_from_document]
        )
    
    def create_summarizer_agent(self) -> Agent:
        """Create summarizer agent for document summarization."""
        return Agent(
            role='Document Summarizer',
            goal='Create comprehensive, structured summaries that capture all essential information including executive overview, key findings, data, entities, timeline, recommendations, and takeaways - enabling complete document understanding without reading the full text',
            backstory='''You are an expert document analyst specializing in creating comprehensive, structured summaries. 
            You excel at extracting and organizing all essential information from documents including:
            - Executive overviews and context
            - Key topics, themes, and subject matter
            - Critical findings, conclusions, and insights
            - Important data, statistics, and quantitative metrics
            - Key stakeholders, entities, and organizations
            - Timeline, chronology, and important dates
            - Recommendations and actionable next steps
            - Essential takeaways and key points
            
            Your summaries are thorough yet organized, allowing readers to understand the complete document context
            without reading the full text. You structure summaries with clear sections, headings, or bullet points
            for maximum clarity and usability.
            
            You have access to tools that allow you to summarize text. Always use the
            summarize_document_text tool to perform the actual summarization.''',
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[summarize_document_text]
        )

