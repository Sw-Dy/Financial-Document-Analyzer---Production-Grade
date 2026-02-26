"""
CRUD operations for database models.

Provides clean, reusable functions for creating, reading, updating
analysis results and user data.
"""

import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from models import User, AnalysisResult

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_or_create_user(session: Session, email: str) -> User:
    """
    Get existing user by email or create new user.

    Args:
        session: SQLAlchemy session
        email: User email address

    Returns:
        User: Existing or newly created user
    """
    user = session.query(User).filter(User.email == email).first()
    if not user:
        logger.info(f"[CRUD] Creating new user with email: {email}")
        user = User(email=email)
        session.add(user)
        session.commit()
        session.refresh(user)
        logger.info(f"[CRUD] User created with id: {user.id}")
    else:
        logger.info(f"[CRUD] Found existing user: {user.id} ({email})")
    return user


def create_analysis(
    session: Session,
    task_id: str,
    filename: str,
    user_id: Optional[int] = None,
) -> AnalysisResult:
    """
    Create new analysis record in database.

    Args:
        session: SQLAlchemy session
        task_id: Unique task ID (UUID string)
        filename: Original filename
        user_id: Optional user ID

    Returns:
        AnalysisResult: Created analysis record
    """
    logger.info(f"[CRUD] Creating analysis: task_id={task_id}, filename={filename}, user_id={user_id}")
    
    analysis = AnalysisResult(
        id=task_id,
        filename=filename,
        user_id=user_id,
        status="pending",
    )
    
    session.add(analysis)
    logger.info(f"[CRUD] Analysis added to session: {task_id}")
    
    session.commit()
    logger.info(f"[CRUD] Committed to database: {task_id}")
    
    session.refresh(analysis)
    logger.info(f"[CRUD] Refreshed analysis: {task_id} | status={analysis.status} | created_at={analysis.created_at}")
    
    # Verify we can query it back immediately
    verify = session.query(AnalysisResult).filter(AnalysisResult.id == task_id).first()
    if verify:
        logger.info(f"[CRUD] ✓ VERIFIED: Analysis persisted in database: {task_id}")
    else:
        logger.error(f"[CRUD] ✗ ERROR: Analysis NOT found after creation: {task_id}")
    
    return analysis


def get_analysis(session: Session, task_id: str) -> Optional[AnalysisResult]:
    """
    Retrieve analysis by task ID.

    Args:
        session: SQLAlchemy session
        task_id: Task ID to retrieve

    Returns:
        AnalysisResult: Analysis record or None if not found
    """
    analysis = session.query(AnalysisResult).filter(AnalysisResult.id == task_id).first()
    if analysis:
        logger.info(f"[CRUD] Retrieved analysis: {task_id} (status={analysis.status})")
    else:
        logger.warning(f"[CRUD] Analysis not found: {task_id}")
    return analysis


def update_analysis_status(
    session: Session,
    task_id: str,
    status: str,
    error_message: Optional[str] = None,
) -> Optional[AnalysisResult]:
    """
    Update analysis status.

    Args:
        session: SQLAlchemy session
        task_id: Task ID to update
        status: New status (pending, running, completed, failed)
        error_message: Optional error message if failed

    Returns:
        AnalysisResult: Updated analysis record or None if not found
    """
    analysis = get_analysis(session, task_id)
    if analysis:
        logger.info(f"[CRUD] Updating status for {task_id}: {analysis.status} -> {status}")
        analysis.status = status
        if error_message:
            analysis.error_message = error_message
            logger.info(f"[CRUD] Error message set: {error_message}")
        if status == "completed":
            analysis.completed_at = datetime.utcnow()
            logger.info(f"[CRUD] Marked as completed at {analysis.completed_at}")
        session.commit()
        session.refresh(analysis)
        logger.info(f"[CRUD] Status update committed for {task_id}")
    else:
        logger.error(f"[CRUD] Could not update status - analysis not found: {task_id}")
    return analysis


def update_analysis_result(
    session: Session,
    task_id: str,
    status: str,
    result_json: dict,
) -> Optional[AnalysisResult]:
    """
    Update analysis with result and mark as completed.

    Args:
        session: SQLAlchemy session
        task_id: Task ID to update
        status: New status
        result_json: Structured result from CrewAI

    Returns:
        AnalysisResult: Updated analysis record or None if not found
    """
    analysis = get_analysis(session, task_id)
    if analysis:
        logger.info(f"[CRUD] Updating result for {task_id} with status={status}")
        analysis.status = status
        analysis.result_json = result_json
        analysis.completed_at = datetime.utcnow()
        session.commit()
        session.refresh(analysis)
        logger.info(f"[CRUD] Result update committed for {task_id}")
    else:
        logger.error(f"[CRUD] Could not update result - analysis not found: {task_id}")
    return analysis


def get_user_analyses(
    session: Session,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[AnalysisResult]:
    """
    Get all analyses for a user with pagination.

    Args:
        session: SQLAlchemy session
        user_id: User ID
        limit: Number of results to return
        offset: Number of results to skip

    Returns:
        list: List of analysis records
    """
    return (
        session.query(AnalysisResult)
        .filter(AnalysisResult.user_id == user_id)
        .order_by(AnalysisResult.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def delete_old_analyses(session: Session, days: int = 7) -> int:
    """
    Delete analyses older than specified days.

    Useful for cleanup of old completed tasks.

    Args:
        session: SQLAlchemy session
        days: Delete analyses older than this many days

    Returns:
        int: Number of deleted records
    """
    from datetime import timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days)
    result = session.query(AnalysisResult).filter(
        AnalysisResult.completed_at < cutoff_date
    )
    count = result.count()
    result.delete()
    session.commit()
    return count
