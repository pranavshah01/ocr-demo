"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from app.api.routes import router
from app.database.db import init_db
from app.utils.logger import setup_logging, get_logger
from app.config import settings

# Setup logging
setup_logging(log_level="INFO", log_file="logs/ocr_pipeline.log")
logger = get_logger(__name__)

app = FastAPI(
    title="OCR Pipeline API",
    description="Document OCR pipeline with CrewAI orchestration",
    version="1.0.0"
)

# Initialize database
logger.info("Initializing database...")
init_db()
logger.info("Database initialized successfully")

# Include API routes
app.include_router(router)

# Serve frontend files
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path / "static")), name="static")
    
    @app.get("/")
    async def read_root():
        """Serve main frontend page."""
        return FileResponse(str(frontend_path / "index.html"))


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("OCR Pipeline application starting up...")
    logger.info(f"Server will run on {settings.host}:{settings.port}")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("OCR Pipeline application shutting down...")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

