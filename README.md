# OCR Pipeline

A modular OCR pipeline with document upload interface, FastAPI backend, SQLite database, and CrewAI orchestration for document extraction, summarization, and tracking.

## Features

- Document upload interface (HTML/JavaScript) with drag-and-drop
- Support for multiple formats: PDF, PNG, JPG, JPEG, DOCX, TIFF
- OCR extraction using OpenAI Vision API (gpt-4.1-mini)
- Document summarization using OpenAI LLM (gpt-4)
- Confidence scoring for OCR results (0.0-1.0)
- Retry mechanism with configurable retries (default: 2)
- Failure logging for human review
- Processing history tracking
- Real-time status updates

## Architecture

See [docs/architecture.md](docs/architecture.md) for detailed architecture documentation with Mermaid diagrams.

## Quick Start

### Prerequisites

- Python 3.10 or higher
- `uv` package manager (or use `pip`/`pipenv`/`poetry`)
- OpenAI API key

### Installation & Setup

1. **Clone or navigate to the project directory:**
```bash
cd /path/to/ocr
```

2. **Create a virtual environment:**
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies:**
```bash
uv pip install -r requirements.txt
```

4. **Configure environment variables:**
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key:
# OPENAI_API_KEY=your_actual_api_key_here
```

5. **Initialize the database:**
```bash
python -c "from app.database.db import init_db; init_db()"
```

6. **Start the application:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

7. **Open your browser:**
```
http://localhost:8000
```

## How to Use the Application

### Web Interface

1. **Upload a Document:**
   - Open the web interface at `http://localhost:8000`
   - Click "Choose File" button or drag-and-drop a document
   - Supported formats: PDF, PNG, JPG, JPEG, DOCX, TIFF
   - The file will be uploaded and processing will start automatically

2. **View Processing Status:**
   - Documents appear in the list with status badges:
     - **Pending**: Waiting to be processed
     - **Processing**: Currently being processed
     - **Completed**: Successfully processed (green)
     - **Failed**: Processing failed (red)
   - Confidence scores are displayed for completed documents
   - The page auto-refreshes every 5 seconds to show updates

3. **View Document Details:**
   - Click on any document card to see details
   - Modal shows:
     - **Summary**: AI-generated summary (highlighted at top)
     - **Confidence Score**: OCR quality score (color-coded)
     - **Extracted Text**: Full text extracted from document
   - Summary is displayed prominently with expanded text area

4. **Filter Documents:**
   - Use the status filter dropdown to filter by status
   - Click "Refresh" to manually reload the document list

### API Usage

#### Upload a Document
```bash
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@your_document.pdf"
```

Response:
```json
{
  "document_id": 1,
  "job_id": 1,
  "filename": "your_document.pdf",
  "status": "pending",
  "message": "Document uploaded successfully. Processing started."
}
```

#### Check Job Status
```bash
curl "http://localhost:8000/api/status/1"
```

Response:
```json
{
  "job_id": 1,
  "document_id": 1,
  "status": "completed",
  "retry_count": 0,
  "created_at": "2025-11-05T18:35:14",
  "completed_at": "2025-11-05T18:40:24",
  "error_message": null
}
```

#### Get Document with Results
```bash
curl "http://localhost:8000/api/document/1"
```

Response:
```json
{
  "document_id": 1,
  "filename": "your_document.pdf",
  "file_type": "PDF",
  "status": "completed",
  "upload_date": "2025-11-05T18:35:14",
  "extracted_content": {
    "id": 1,
    "raw_text": "Full extracted text...",
    "summary": "AI-generated summary...",
    "confidence_score": 0.984,
    "metadata": "{\"model\": \"gpt-4.1-mini\", ...}",
    "created_at": "2025-11-05T18:40:24"
  }
}
```

#### Get Processing History
```bash
curl "http://localhost:8000/api/history?skip=0&limit=10"
```

#### Get Failure Logs
```bash
curl "http://localhost:8000/api/failures?reviewed=pending&limit=50"
```

#### Health Check
```bash
curl "http://localhost:8000/health"
```

## API Endpoints

- `POST /api/upload` - Upload a document
- `GET /api/status/{job_id}` - Get processing job status
- `GET /api/document/{document_id}` - Get document with extracted content
- `GET /api/history` - Get processing history
- `GET /api/failures` - Get failure logs for review
- `GET /health` - Health check

## Configuration

### Environment Variables

Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

**Required:**
- `OPENAI_API_KEY` - Your OpenAI API key (required for OCR and summarization)

**Optional (with defaults):**
- `DATABASE_URL` - SQLite database path (default: `sqlite:///./ocr_pipeline.db`)
- `MAX_RETRIES` - Maximum retry attempts (default: `2`)
- `RETRY_BACKOFF_MULTIPLIER` - Exponential backoff multiplier (default: `2.0`)
- `UPLOAD_DIR` - Upload directory (default: `./uploads`)
- `PROCESSED_DIR` - Processed files directory (default: `./processed`)
- `REPORTS_DIR` - Failure reports directory (default: `./reports`)
- `HOST` - Server host (default: `0.0.0.0`)
- `PORT` - Server port (default: `8000`)

### Logging

Logs are automatically written to:
- **Console**: All log messages
- **File**: `logs/ocr_pipeline.log` (rotates when > 10MB, keeps 5 backups)

Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## Project Structure

```
ocr/
├── frontend/          # HTML/JavaScript frontend
├── app/               # Python application
│   ├── api/          # FastAPI routes and schemas
│   ├── database/     # Database models and connection
│   ├── services/     # Business logic services
│   └── crew/         # CrewAI agents and tasks
├── uploads/          # Uploaded documents
├── processed/        # Processed files
├── reports/         # Failure reports
└── docs/            # Documentation
```

## Understanding Results

### Confidence Scores

Confidence scores range from **0.0 (low) to 1.0 (high)** and indicate OCR quality:
- **High (0.7-1.0)**: Green badge - Excellent extraction quality
- **Medium (0.4-0.7)**: Orange badge - Good quality, may have minor errors
- **Low (0.0-0.4)**: Red badge - Poor quality, manual review recommended

Scores are calculated based on:
- Text length and quality
- Common OCR error patterns
- Word quality metrics
- Punctuation and capitalization indicators

### Processing Status

- **Pending**: Document uploaded, waiting to be processed
- **Processing**: Currently extracting text or generating summary
- **Completed**: Successfully processed with results available
- **Failed**: Processing failed after all retries (check failure logs)

### Summaries

- **AI-Generated**: Full summary created by OpenAI LLM (gpt-4)
- **Fallback**: If summarization fails, shows first 500 characters of extracted text
- Summaries are displayed prominently in the UI with expanded text area

## Retry Mechanism

The pipeline includes automatic retry logic:
- **Default**: 2 retries per operation (OCR and summarization)
- **Backoff**: Exponential backoff between retries (2^attempt seconds)
- **Failure Handling**: Failed jobs after all retries are logged to:
  - Database table: `failure_logs`
  - Report files: `reports/failure_{job_id}.txt`

## File Processing Details

### Supported Formats

| Format | Processing Method | OpenAI Used? |
|--------|------------------|--------------|
| **DOCX** | Direct text extraction (python-docx) | ❌ No |
| **PDF** | Converted to images → OpenAI Vision API | ✅ Yes |
| **PNG/JPEG/TIFF** | Direct → OpenAI Vision API | ✅ Yes |

**All formats** use OpenAI for summarization (gpt-4 LLM).

### Processing Time

- **DOCX**: Fastest (direct extraction, no OCR)
- **PDF**: Slower (page conversion + OCR per page)
- **Images**: Moderate (OCR per image)

Processing time depends on:
- Document size and number of pages
- OpenAI API response time
- Network latency

## Troubleshooting

### Common Issues

1. **"Upload failed" error:**
   - Check file size (large files may take longer)
   - Verify file format is supported
   - Check server logs: `logs/ocr_pipeline.log`

2. **"Processing stuck":**
   - Check OpenAI API key is valid
   - Verify API quota/limits
   - Check logs for detailed error messages

3. **"Summarization failed":**
   - Document may be too long
   - OpenAI API may be rate-limited
   - Check logs for specific error

4. **Low confidence scores:**
   - Document may have poor image quality
   - Try higher resolution scanning
   - Check extracted text manually

### Checking Logs

```bash
# View recent logs
tail -f logs/ocr_pipeline.log

# Search for errors
grep ERROR logs/ocr_pipeline.log

# View specific document processing
grep "document_id: 1" logs/ocr_pipeline.log
```

### Database Management

```bash
# Access SQLite database
sqlite3 ocr_pipeline.db

# View documents
SELECT id, filename, status FROM documents;

# View failures
SELECT * FROM failure_logs WHERE reviewed = 'pending';
```

## Development

### Project Structure

```
ocr/
├── frontend/          # HTML/JavaScript UI
│   ├── index.html
│   └── static/
│       ├── css/
│       └── js/
├── app/               # Python application
│   ├── api/          # FastAPI routes
│   ├── database/     # Database models
│   ├── services/     # Business logic
│   ├── crew/         # CrewAI
│   ├── utils/        # Utilities (logging)
│   └── main.py       # Application entry point
├── uploads/          # Uploaded documents
├── processed/        # Processed files
├── reports/          # Failure reports
├── logs/             # Application logs
└── docs/             # Documentation
```

### Running Tests

```bash
# Run with hot reload for development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## License

MIT

