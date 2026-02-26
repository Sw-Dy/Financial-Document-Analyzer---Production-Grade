"""
Production-grade FastAPI application with Celery background task support.

Architecture:
- FastAPI handles HTTP requests
- Celery executes long-running CrewAI tasks in background
- SQLite stores analysis history and task status
- SQLAlchemy ORM for database access

Endpoints:
- POST /analyze - Submit document for analysis
- GET /status/{task_id} - Check analysis status
- GET /analysis/{task_id} - Retrieve completed analysis
- GET /health - Health check
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
import os
import uuid
import json
import logging
from datetime import datetime

from crewai import Crew, Process
from sqlalchemy.orm import Session

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our modules
from db import get_session, init_db
from models import User, AnalysisResult
from schemas import (
    AnalysisRequestResponse,
    AnalysisStatusResponse,
    AnalysisResultResponse,
)
from crud import create_analysis, get_analysis, get_or_create_user
from celery_app import analyze_document_task
from agents import financial_analyst
from task import analyze_financial_document as analyze_task


# ============================================================================
# CORE FUNCTIONS
# ============================================================================


def run_crew_analysis(query: str, file_path: str = "data/sample.pdf") -> str:
    """
    Execute CrewAI analysis workflow synchronously.

    Args:
        query: User's analysis query
        file_path: Path to financial document

    Returns:
        str: Analysis result (should be JSON string)
    """
    try:
        logger.info(f"[CrewAI] Starting analysis for: {file_path}")
        financial_crew = Crew(
            agents=[financial_analyst],
            tasks=[analyze_task],
            process=Process.sequential,
            verbose=True,
        )

        result = financial_crew.kickoff(inputs={"query": query})
        logger.info(f"[CrewAI] Analysis completed successfully")
        return result
    except Exception as e:
        logger.error(f"[CrewAI] Analysis failed: {str(e)}", exc_info=True)
        return json.dumps({"error": str(e), "status": "failed"})


# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context for startup/shutdown events.

    Startup: Initialize database, create required directories
    Shutdown: Cleanup resources
    """
    # Startup
    try:
        logger.info("[App] Starting up...")
        init_db()
        os.makedirs("data", exist_ok=True)
        os.makedirs("outputs", exist_ok=True)
        os.makedirs("celery_data", exist_ok=True)
        logger.info("✓ Database initialized")
        logger.info("✓ Directories created")
        logger.info("✓ Application startup complete")
    except Exception as e:
        logger.error(f"✗ Startup error: {e}", exc_info=True)

    yield

    # Shutdown
    logger.info("[App] Shutting down...")


# ============================================================================
# APP INITIALIZATION
# ============================================================================

app = FastAPI(
    title="Financial Document Analyzer - Production",
    description="Enterprise-grade financial analysis with CrewAI and async task processing",
    version="2.0.0",
    lifespan=lifespan,
)


# ============================================================================
# ENDPOINTS
# ============================================================================


@app.get("/", tags=["Health"])
async def root():
    """
    Root endpoint - API information.

    Returns:
        dict: API metadata
    """
    logger.info("[Endpoint] GET / - root")
    return {
        "status": "operational",
        "service": "Financial Document Analyzer",
        "version": "2.0.0",
        "endpoints": {
            "health": "/health",
            "analyze": "/analyze (POST)",
            "status": "/status/{task_id} (GET)",
            "result": "/analysis/{task_id} (GET)",
        },
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Detailed health check endpoint.

    Returns:
        dict: Health status information
    """
    logger.info("[Endpoint] GET /health")
    return {
        "status": "healthy",
        "service": "financial-analyzer",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "api": "operational",
            "database": "operational",
            "celery": "operational",
        },
    }


@app.post("/analyze", tags=["Analysis"], response_model=AnalysisRequestResponse)
async def submit_analysis(
    file: UploadFile = File(..., description="PDF financial document"),
    query: str = Form(default="Analyze this financial document"),
    email: str = Form(default=None, description="Optional user email"),
    session: Session = Depends(get_session),
):
    """
    Submit financial document for analysis.

    This endpoint:
    1. Validates the uploaded PDF
    2. Saves file to disk
    3. Creates database record
    4. Triggers async Celery task
    5. Returns task_id for status tracking

    Args:
        file: PDF file upload
        query: Analysis instruction
        email: Optional user email for tracking
        session: Database session

    Returns:
        AnalysisRequestResponse: Task ID and status URL

    Raises:
        HTTPException: For validation or processing errors
    """
    file_id = str(uuid.uuid4())
    logger.info(f"[Endpoint] POST /analyze - task_id={file_id}, filename={file.filename}")

    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            logger.warning(f"[Analyze] Invalid file type: {file.filename}")
            raise HTTPException(
                status_code=400, detail="Only PDF files are supported"
            )

        file_path = f"data/financial_document_{file_id}.pdf"

        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)

        # Save uploaded file
        logger.info(f"[Analyze {file_id}] Saving file to: {file_path}")
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        logger.info(f"[Analyze {file_id}] File saved successfully ({len(content)} bytes)")

        # Validate query
        if not query or query.strip() == "":
            query = "Analyze this financial document comprehensively"
        else:
            query = query.strip()

        # Get or create user in database
        user = None
        if email:
            try:
                logger.info(f"[Analyze {file_id}] Creating/retrieving user: {email}")
                user = get_or_create_user(session, email)
                logger.info(f"[Analyze {file_id}] User ID: {user.id}")
            except Exception as e:
                logger.warning(f"[Analyze {file_id}] Could not create user: {e}")

        # Create analysis record in database
        logger.info(f"[Analyze {file_id}] Creating analysis record in database")
        analysis = create_analysis(
            session=session,
            task_id=file_id,
            filename=file.filename,
            user_id=user.id if user else None,
        )
        logger.info(f"[Analyze {file_id}] DB Record created: status={analysis.status}, id={analysis.id}")

        # Verify record exists with a fresh query
        logger.info(f"[Analyze {file_id}] Verifying DB record...")
        verify_analysis = get_analysis(session, file_id)
        if verify_analysis:
            logger.info(f"[Analyze {file_id}] ✓ VERIFIED: DB record accessible via GET: {verify_analysis.id}")
        else:
            logger.error(f"[Analyze {file_id}] ✗ ERROR: DB record NOT accessible immediately after creation!")

        # Trigger async Celery task
        task_id = file_id
        logger.info(f"[Analyze {file_id}] Triggering Celery task with task_id={task_id}")
        celery_task = analyze_document_task.apply_async(
            args=[task_id, file_path, query, user.id if user else None],
            task_id=str(task_id),
            expires=3600,  # Task expires in 1 hour
        )
        logger.info(f"[Analyze {file_id}] Celery task queued: celery_id={celery_task.id}")

        logger.info(f"[Analyze {file_id}] Returning response with task_id={task_id}")
        return AnalysisRequestResponse(
            task_id=task_id,
            status="pending",
            message="Analysis submitted successfully. Use status endpoint to check progress.",
            status_url=f"/status/{task_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Analyze {file_id}] Error: {str(e)}", exc_info=True)
        # Clean up file on error
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"[Analyze {file_id}] Cleaned up file after error")
            except:
                pass

        raise HTTPException(
            status_code=500,
            detail=f"Error submitting analysis: {str(e)}",
        )


@app.get("/status/{task_id}", tags=["Status"], response_model=AnalysisStatusResponse)
async def check_status(
    task_id: str,
    session: Session = Depends(get_session),
):
    """
    Check analysis task status.

    Returns current status:
    - pending: Queued but not started
    - running: Analysis in progress
    - completed: Analysis finished successfully
    - failed: Analysis failed with error

    Args:
        task_id: Task ID from /analyze response
        session: Database session

    Returns:
        AnalysisStatusResponse: Current task status and progress

    Raises:
        HTTPException: If task not found
    """
    logger.info(f"[Endpoint] GET /status/{task_id}")
    logger.info(f"[Status {task_id}] Querying database for task_id (UUID string)...")
    
    try:
        # Get from database for persistent status
        analysis = get_analysis(session, task_id)

        if not analysis:
            # Debug: list all records
            logger.warning(f"[Status {task_id}] Analysis not found!")
            all_records = session.query(AnalysisResult).all()
            logger.warning(f"[Status {task_id}] Total records in DB: {len(all_records)}")
            for rec in all_records:
                logger.warning(f"[Status {task_id}]   Record: id={rec.id}, status={rec.status}")
            
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found",
            )

        logger.info(f"[Status {task_id}] ✓ Found: status={analysis.status}, created_at={analysis.created_at}")

        # Map database status to response
        status_map = {
            "pending": "pending",
            "running": "running",
            "completed": "completed",
            "failed": "failed",
        }

        # Calculate progress
        progress = {"pending": 0, "running": 50, "completed": 100, "failed": 0}.get(
            analysis.status, 0
        )

        return AnalysisStatusResponse(
            task_id=task_id,
            status=analysis.status,
            progress=progress,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Status {task_id}] Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error checking status: {str(e)}",
        )


@app.get("/analysis/{task_id}", tags=["Results"], response_model=AnalysisResultResponse)
async def get_analysis_result(
    task_id: str,
    session: Session = Depends(get_session),
):
    """
    Retrieve completed analysis result.

    Returns full analysis with all details and timestamps.
    Only available after analysis completes (status == completed).

    Args:
        task_id: Task ID from /analyze response
        session: Database session

    Returns:
        AnalysisResultResponse: Complete analysis with structured result

    Raises:
        HTTPException: If task not found or still processing
    """
    logger.info(f"[Endpoint] GET /analysis/{task_id}")
    logger.info(f"[Analysis {task_id}] Querying database for task_id (UUID string)...")
    
    try:
        analysis = get_analysis(session, task_id)

        if not analysis:
            # Debug: list all records
            logger.warning(f"[Analysis {task_id}] Analysis not found!")
            all_records = session.query(AnalysisResult).all()
            logger.warning(f"[Analysis {task_id}] Total records in DB: {len(all_records)}")
            for rec in all_records:
                logger.warning(f"[Analysis {task_id}]   Record: id={rec.id}, status={rec.status}")
            
            raise HTTPException(
                status_code=404,
                detail=f"Analysis {task_id} not found",
            )

        logger.info(f"[Analysis {task_id}] Found record: status={analysis.status}")

        if analysis.status == "pending" or analysis.status == "running":
            logger.info(f"[Analysis {task_id}] Still processing (status={analysis.status})")
            raise HTTPException(
                status_code=202,  # 202 Accepted - Still processing
                detail=f"Analysis still processing. Current status: {analysis.status}. Check /status/{task_id}",
            )

        if analysis.status == "failed":
            logger.warning(f"[Analysis {task_id}] Analysis failed: {analysis.error_message}")
            raise HTTPException(
                status_code=400,
                detail=f"Analysis failed: {analysis.error_message}",
            )

        logger.info(f"[Analysis {task_id}] ✓ Returning completed result")

        # Convert to response schema
        return AnalysisResultResponse(
            id=analysis.id,
            user_id=analysis.user_id,
            filename=analysis.filename,
            status=analysis.status,
            result=analysis.result_json,
            error=analysis.error_message,
            created_at=analysis.created_at,
            completed_at=analysis.completed_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Analysis {task_id}] Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving analysis: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)



# ============================================================================
# APP INITIALIZATION
# ============================================================================

app = FastAPI(
    title="Financial Document Analyzer - Production",
    description="Enterprise-grade financial analysis with CrewAI and async task processing",
    version="2.0.0",
    lifespan=lifespan,
)


# ============================================================================
# ENDPOINTS
# ============================================================================


@app.get("/", tags=["Health"])
async def root():
    """
    Root endpoint - API information.

    Returns:
        dict: API metadata
    """
    logger.info("[Endpoint] GET / - root")
    return {
        "status": "operational",
        "service": "Financial Document Analyzer",
        "version": "2.0.0",
        "endpoints": {
            "health": "/health",
            "analyze": "/analyze (POST)",
            "status": "/status/{task_id} (GET)",
            "result": "/analysis/{task_id} (GET)",
        },
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Detailed health check endpoint.

    Returns:
        dict: Health status information
    """
    return {
        "status": "healthy",
        "service": "financial-analyzer",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "api": "operational",
            "database": "operational",
            "celery": "operational",
        },
    }


@app.post("/analyze", tags=["Analysis"], response_model=AnalysisRequestResponse)
async def submit_analysis(
    file: UploadFile = File(..., description="PDF financial document"),
    query: str = Form(default="Analyze this financial document"),
    email: str = Form(default=None, description="Optional user email"),
    session: Session = Depends(get_session),
):
    """
    Submit financial document for analysis.

    This endpoint:
    1. Validates the uploaded PDF
    2. Saves file to disk
    3. Creates database record
    4. Triggers async Celery task
    5. Returns task_id for status tracking

    Args:
        file: PDF file upload
        query: Analysis instruction
        email: Optional user email for tracking
        session: Database session

    Returns:
        AnalysisRequestResponse: Task ID and status URL

    Raises:
        HTTPException: For validation or processing errors
    """
    file_id = str(uuid.uuid4())

    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400, detail="Only PDF files are supported"
            )

        file_path = f"data/financial_document_{file_id}.pdf"

        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)

        # Save uploaded file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Validate query
        if not query or query.strip() == "":
            query = "Analyze this financial document comprehensively"
        else:
            query = query.strip()

        # Get or create user in database
        user = None
        if email:
            try:
                user = get_or_create_user(session, email)
            except Exception as e:
                print(f"Warning: Could not create user: {e}")

        # Create analysis record in database
        analysis = create_analysis(
            session=session,
            task_id=file_id,
            filename=file.filename,
            user_id=user.id if user else None,
        )

        # Trigger async Celery task
        task_id = file_id
        celery_task = analyze_document_task.apply_async(
            args=[task_id, file_path, query, user.id if user else None],
            task_id=str(task_id),
            expires=3600,  # Task expires in 1 hour
        )

        return AnalysisRequestResponse(
            task_id=task_id,
            status="pending",
            message="Analysis submitted successfully. Use status endpoint to check progress.",
            status_url=f"/status/{task_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        # Clean up file on error
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

        raise HTTPException(
            status_code=500,
            detail=f"Error submitting analysis: {str(e)}",
        )


@app.get("/status/{task_id}", tags=["Status"], response_model=AnalysisStatusResponse)
async def check_status(
    task_id: str,
    session: Session = Depends(get_session),
):
    """
    Check analysis task status.

    Returns current status:
    - pending: Queued but not started
    - running: Analysis in progress
    - completed: Analysis finished successfully
    - failed: Analysis failed with error

    Args:
        task_id: Task ID from /analyze response
        session: Database session

    Returns:
        AnalysisStatusResponse: Current task status and progress

    Raises:
        HTTPException: If task not found
    """
    try:
        # Get from database for persistent status
        analysis = get_analysis(session, task_id)

        if not analysis:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found",
            )

        # Map database status to response
        status_map = {
            "pending": "pending",
            "running": "running",
            "completed": "completed",
            "failed": "failed",
        }

        # Calculate progress
        progress = {"pending": 0, "running": 50, "completed": 100, "failed": 0}.get(
            analysis.status, 0
        )

        return AnalysisStatusResponse(
            task_id=task_id,
            status=analysis.status,
            progress=progress,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking status: {str(e)}",
        )


@app.get("/analysis/{task_id}", tags=["Results"], response_model=AnalysisResultResponse)
async def get_analysis_result(
    task_id: str,
    session: Session = Depends(get_session),
):
    """
    Retrieve completed analysis result.

    Returns full analysis with all details and timestamps.
    Only available after analysis completes (status == completed).

    Args:
        task_id: Task ID from /analyze response
        session: Database session

    Returns:
        AnalysisResultResponse: Complete analysis with structured result

    Raises:
        HTTPException: If task not found or still processing
    """
    try:
        analysis = get_analysis(session, task_id)

        if not analysis:
            raise HTTPException(
                status_code=404,
                detail=f"Analysis {task_id} not found",
            )

        if analysis.status == "pending" or analysis.status == "running":
            raise HTTPException(
                status_code=202,  # 202 Accepted - Still processing
                detail=f"Analysis still processing. Current status: {analysis.status}. Check /status/{task_id}",
            )

        if analysis.status == "failed":
            raise HTTPException(
                status_code=400,
                detail=f"Analysis failed: {analysis.error_message}",
            )

        # Convert to response schema
        return AnalysisResultResponse(
            id=analysis.id,
            user_id=analysis.user_id,
            filename=analysis.filename,
            status=analysis.status,
            result=analysis.result_json,
            error=analysis.error_message,
            created_at=analysis.created_at,
            completed_at=analysis.completed_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving analysis: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)