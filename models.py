"""
SQLAlchemy ORM models for the financial document analyzer.

Models:
  - User: User account information
  - AnalysisResult: Stores analysis results with status tracking
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from db import Base


class User(Base):
    """
    User model for tracking analysis owners.

    Attributes:
        id: Primary key
        email: User email address (unique)
        created_at: Account creation timestamp
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    analyses = relationship(
        "AnalysisResult",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"


class AnalysisResult(Base):
    """
    Analysis result model for storing document analysis outputs.

    Attributes:
        id: Primary key (also Celery task_id)
        user_id: Foreign key to User
        filename: Original uploaded filename
        status: Task status (pending, running, completed, failed)
        result_json: Structured JSON output from CrewAI
        error_message: Error details if status is failed
        created_at: Submission timestamp
        completed_at: Completion timestamp
    """

    __tablename__ = "analysis_results"

    id = Column(String(36), primary_key=True, index=True)  # UUID as task_id
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    filename = Column(String(255), nullable=False)
    status = Column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
    )  # pending, running, completed, failed
    result_json = Column(JSON, nullable=True)  # Structured output
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="analyses")

    def __repr__(self):
        return f"<AnalysisResult(id={self.id}, status={self.status}, filename={self.filename})>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "filename": self.filename,
            "status": self.status,
            "result": self.result_json,
            "error": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }
