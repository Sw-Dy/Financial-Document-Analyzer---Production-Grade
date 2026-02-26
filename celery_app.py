"""
Celery application configuration for background task processing.

This module initializes Celery with Redis or SQLAlchemy backend.
All long-running CrewAI operations are executed as background tasks via this worker.

For production: Use Redis as broker/backend
For development: Uses SQLAlchemy with SQLite (no Redis required)
"""

import os
import logging
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize Celery app
celery_app = Celery("financial_analyzer")

# Configuration - use environment or sensible defaults
ENV = os.getenv("ENV", "development").lower()
logger.info(f"[Celery] Initializing with ENV={ENV}")

if ENV == "production":
    # Production: Redis broker with optimal settings
    BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    logger.info("[Celery] Using Redis broker/backend (production mode)")
    print("[Celery] Using Redis broker/backend (production mode)")
else:
    # Development: SQLAlchemy broker and database result backend
    # This avoids requiring Redis during development
    os.makedirs("celery_data", exist_ok=True)
    BROKER_URL = "sqla+sqlite:///celery_data/celery_broker.db"
    RESULT_BACKEND = "db+sqlite:///celery_data/celery_results.db"
    logger.info("[Celery] Using SQLAlchemy/SQLite backend (development mode - no Redis required)")
    print("[Celery] Using SQLAlchemy/SQLite backend (development mode - no Redis required)")

# Celery configuration
celery_app.conf.update(
    broker_url=BROKER_URL,
    result_backend=RESULT_BACKEND,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task settings
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Result settings
    result_expires=3600,  # Results expire after 1 hour
)



@celery_app.task(bind=True)
def analyze_document_task(
    self,
    task_id: str,
    file_path: str,
    query: str,
    user_id: int = None,
):
    """
    Background task to analyze financial document using CrewAI.

    This task:
    1. Updates database status to "running"
    2. Executes CrewAI analysis
    3. Stores result in database
    4. Updates completed_at timestamp
    5. Handles errors gracefully with rollback

    Args:
        self: Celery task instance (for bind=True)
        task_id: Analysis ID (UUID) from database
        file_path: Path to uploaded PDF file
        query: User's analysis query
        user_id: Optional user ID for tracking

    Returns:
        dict: Analysis result with structured output

    Raises:
        Exception: Re-raised after database update for Celery tracking
    """
    logger.info(f"[Task {task_id}] Starting analysis task")
    logger.info(f"[Task {task_id}] Parameters: file_path={file_path}, query={query}, user_id={user_id}")
    
    session = None
    try:
        # Import here to avoid circular imports
        from main import run_crew_analysis
        from db import SessionLocal
        from crud import update_analysis_status, update_analysis_result
        import json

        # Create a NEW session for this task (important for Celery)
        session = SessionLocal()
        logger.info(f"[Task {task_id}] Database session created")

        # Step 1: Update task status to "running" in database
        logger.info(f"[Task {task_id}] Updating status to 'running'")
        update_analysis_status(session, task_id, "running")
        logger.info(f"[Task {task_id}] Status updated to 'running'")

        # Step 2: Execute CrewAI analysis
        logger.info(f"[Task {task_id}] Starting CrewAI analysis")
        analysis_result = run_crew_analysis(query=query, file_path=file_path)
        logger.info(f"[Task {task_id}] CrewAI analysis completed")

        # Step 3: Parse result to JSON
        try:
            result_json = json.loads(analysis_result)
            logger.info(f"[Task {task_id}] Result parsed as JSON")
        except json.JSONDecodeError as json_err:
            logger.warning(f"[Task {task_id}] Could not parse result as JSON: {json_err}")
            result_json = {"raw_analysis": str(analysis_result)}

        # Step 4: Update task status to "completed" with results in database
        logger.info(f"[Task {task_id}] Updating status to 'completed' with results")
        update_analysis_result(
            session,
            task_id,
            "completed",
            result_json,
        )
        logger.info(f"[Task {task_id}] Status updated to 'completed'")
        logger.info(f"[Task {task_id}] Analysis task completed successfully")

        return {
            "status": "completed",
            "task_id": task_id,
            "result": result_json,
        }

    except Exception as exc:
        # Error occurred - update database to reflect failure
        error_msg = str(exc)
        logger.error(f"[Task {task_id}] Analysis failed with error: {error_msg}", exc_info=True)
        
        if session:
            try:
                logger.info(f"[Task {task_id}] Updating status to 'failed' in database")
                update_analysis_status(
                    session,
                    task_id,
                    "failed",
                    error_message=error_msg,
                )
                logger.info(f"[Task {task_id}] Status updated to 'failed'")
            except Exception as db_err:
                logger.error(f"[Task {task_id}] Failed to update database with error status: {db_err}", exc_info=True)

        # Mark task as failed in Celery
        self.update_state(
            state="FAILURE",
            meta={"error": error_msg, "task_id": task_id},
        )
        
        # Re-raise to mark task as failed in Celery
        raise

    finally:
        # Always close session
        if session:
            try:
                session.close()
                logger.info(f"[Task {task_id}] Database session closed")
            except Exception as close_err:
                logger.error(f"[Task {task_id}] Error closing session: {close_err}", exc_info=True)


if __name__ == "__main__":
    celery_app.start()
