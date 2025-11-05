"""Document summarization using OpenAI LLM."""
import re
from openai import OpenAI
from typing import Optional
from app.config import settings
from app.utils.logger import get_logger


class Summarizer:
    """Summarizes extracted document content using OpenAI LLM."""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
    
    def summarize(self, text: str, max_length: int = 4000) -> str:
        """Generate summary of extracted text.
        
        Args:
            text: Extracted text to summarize
            max_length: Maximum length of summary in characters
            
        Returns:
            Summary text
        """
        if not text or len(text.strip()) == 0:
            return "No content available to summarize."
        
        try:
            import time
            summarization_start = time.time()
            logger = get_logger(__name__)
            logger.info(f"Starting summarization for text of length {len(text)}")
            
            # Token budget: gpt-4o has 128k token context window
            # System prompt: ~200 tokens, user prompt: ~300 tokens, completion: 2000 tokens
            # For safety, limit to 80k characters (~20k tokens) leaving room for prompt and response
            max_text_length = 80000
            if len(text) > max_text_length:
                # Truncate but try to keep important parts
                # Keep first 60k and last 20k to capture intro and conclusion
                first_part = text[:60000]
                last_part = text[-20000:] if len(text) > 80000 else ""
                text = first_part + "\n\n[... middle content truncated ...]\n\n" + last_part
                logger = get_logger(__name__)
                logger.info(f"Text truncated from {len(text)} to fit token limits")
            
            # Clean OCR artifacts from text (remove code blocks, formatting markers)
            cleaned_text = text
            # Remove markdown code blocks
            cleaned_text = re.sub(r'```\w*\s*', '', cleaned_text)
            cleaned_text = re.sub(r'```\s*', '', cleaned_text)
            # Remove excessive whitespace
            cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
            # Remove leading/trailing whitespace from lines
            lines = [line.strip() for line in cleaned_text.split('\n')]
            cleaned_text = '\n'.join(lines)
            
            prompt = f"""You are an expert document analyst. First, CLASSIFY the document type, then create a comprehensive, structured summary that maximizes information with impact.

STEP 1: CLASSIFY the document type (e.g., Resume/CV, Business Plan, Technical Report, Research Paper, Marketing Document, Legal Document, Contract, Proposal, etc.)

STEP 2: Based on the document type, create a structured summary that covers all major areas with maximum impact:

Document text to summarize:
{cleaned_text}

For RESUMES/CVs, structure your summary as:
## Document Classification
- Type: Resume/CV
- Professional Level: [Senior/Executive/Mid-level/Entry-level]
- Industry/Field: [e.g., Technology, Finance, Healthcare]

## Professional Profile
- Current/Target Role: [Job title and level]
- Years of Experience: [Total years]
- Core Expertise Areas: [Key domains/specializations]

## Career Summary & Impact
- Professional positioning and value proposition
- Key achievements and measurable impact
- Career progression highlights

## Key Skills & Competencies
- Technical Skills: [List major technical skills]
- Domain Expertise: [Industry-specific knowledge]
- Leadership & Soft Skills: [Management, communication, etc.]

## Notable Achievements & Impact
- Quantifiable results and accomplishments
- Major projects and their outcomes
- Awards, recognitions, or certifications

## Education & Credentials
- Educational background
- Professional certifications
- Relevant training

## Career Highlights by Experience
- Major roles and responsibilities
- Key contributions and impact at each position
- Technologies/tools used and achievements

## Overall Assessment
- Strengths and unique value proposition
- Career trajectory and positioning
- Key differentiators

For BUSINESS DOCUMENTS (Plans, Reports, Proposals), structure as:
## Document Classification
- Type: [Business Plan/Report/Proposal/etc.]
- Purpose: [Main objective]
- Target Audience: [Intended readers]

## Executive Summary
- Core purpose and objectives
- Main value proposition or key message
- Critical context and significance

## Key Strategic Elements
- Main strategies, initiatives, or approaches
- Business objectives and goals
- Key value drivers

## Critical Findings & Insights
- Important discoveries or conclusions
- Key insights and implications
- Strategic recommendations

## Key Metrics & Data
- Important numbers, metrics, KPIs
- Performance indicators
- Financial data (if applicable)

## Stakeholders & Entities
- Key people, organizations, companies
- Roles and relationships
- Decision-makers and influencers

## Timeline & Milestones
- Important dates and deadlines
- Project phases or stages
- Key milestones

## Recommendations & Next Steps
- Actionable recommendations
- Implementation priorities
- Required next steps

## Impact & Implications
- Business impact and value
- Risks and opportunities
- Strategic importance

For TECHNICAL/RESEARCH DOCUMENTS, structure as:
## Document Classification
- Type: [Technical Report/Research Paper/White Paper/etc.]
- Domain: [Technical field or research area]
- Purpose: [Research question or objective]

## Abstract & Overview
- Core problem or research question
- Methodology or approach
- Key findings and conclusions

## Technical Content
- Main technical concepts and innovations
- Architecture, design, or methodology
- Key technical contributions

## Key Findings & Results
- Important discoveries or results
- Data analysis and insights
- Experimental or analytical outcomes

## Implications & Applications
- Practical applications
- Industry impact
- Future research directions

## Technical Details
- Technologies, tools, or frameworks used
- Key metrics and measurements
- Technical specifications

For OTHER DOCUMENT TYPES, adapt the structure based on document characteristics while covering:
- Document classification and purpose
- Main content areas and themes
- Key information and findings
- Important entities and stakeholders
- Timeline and chronology
- Recommendations and implications
- Overall impact and significance

CRITICAL REQUIREMENTS:
- First classify the document type, then adapt your summary structure accordingly
- Synthesize information - don't just extract sentences. Understand and convey meaning
- Focus on IMPACT and VALUE - highlight what matters most
- Use clear, structured sections with headings for easy navigation
- Maximize information density while maintaining clarity
- Prioritize completeness and accuracy over brevity
- Keep total summary under {max_length} characters, but be comprehensive"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Use gpt-4o for larger context window (128k tokens) and better quality
                messages=[
                    {"role": "system", "content": """You are an expert document analyst specializing in creating comprehensive, contextual, and structured summaries. 
                    
Your process:
1. FIRST: Classify the document type (Resume, Business Plan, Technical Report, etc.)
2. THEN: Adapt your summary structure to match the document type
3. FINALLY: Create a detailed summary that maximizes information with impact

Your summaries:
- Classify documents accurately based on content and structure
- Adapt summary format to document type (resumes get resume-specific sections, business docs get business sections, etc.)
- Capture all major areas with maximum information density
- Highlight impact, achievements, and value propositions
- Use clear, structured sections with headings for easy navigation
- Synthesize information rather than extracting sentences
- Focus on what matters most - impact, value, and key differentiators

IMPORTANT: 
- Always classify the document first, then structure the summary accordingly
- Produce clean, well-formatted summaries in natural language
- Never output raw OCR text or code blocks
- Extract and synthesize information, don't just copy text
- Prioritize completeness and impact over brevity"""},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,  # Increased significantly for comprehensive, structured summaries
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            summarization_time = time.time() - summarization_start
            logger.info(f"Summarization completed in {summarization_time:.2f}s")
            return summary
            
        except Exception as e:
            raise Exception(f"Summarization failed: {str(e)}")
    
    def summarize_with_context(self, text: str, context: Optional[str] = None) -> str:
        """Generate summary with additional context.
        
        Args:
            text: Extracted text to summarize
            context: Additional context to consider
            
        Returns:
            Summary text
        """
        if context:
            prompt = f"""Summarize the following document content. Consider the context provided.
            
            Context: {context}
            
            Document content:
            {text}
            
            Summary:"""
        else:
            prompt = f"""Summarize the following document content.
            
            Document content:
            {text}
            
            Summary:"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Use gpt-4o for consistency with main summarize method
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates clear and concise summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"Summarization failed: {str(e)}")

