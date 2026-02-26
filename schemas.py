"""
Pydantic v2 schemas for request/response validation.

Separates API contracts from database models.
All schemas are Pydantic v2 compatible with proper field configuration.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr = Field(..., description="User email address")


class UserCreate(UserBase):
    """Schema for creating a new user."""

    pass


class UserResponse(UserBase):
    """Schema for user response."""

    id: int = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Account creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class AnalysisStatusResponse(BaseModel):
    """Schema for analysis status check."""

    task_id: str = Field(..., description="Unique task identifier (UUID)")
    status: str = Field(
        ...,
        description="Task status",
        pattern="^(pending|running|completed|failed)$",
    )
    progress: Optional[int] = Field(
        default=None,
        description="Progress percentage (0-100)",
        ge=0,
        le=100,
    )


class AnalysisResultResponse(BaseModel):
    """Schema for completed analysis result."""

    id: str = Field(..., description="Analysis ID")
    user_id: Optional[int] = Field(default=None, description="User ID")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Analysis status")
    result: Optional[dict] = Field(
        default=None,
        description="Structured analysis result",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if failed",
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Completion timestamp",
    )

    model_config = ConfigDict(from_attributes=True)


class AnalysisRequestResponse(BaseModel):
    """Schema for successful analysis submission."""

    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(
        default="pending",
        description="Initial status",
    )
    message: str = Field(
        default="Analysis queued for processing",
        description="Status message",
    )
    status_url: str = Field(..., description="URL to check analysis status")


class CrewAIOutput(BaseModel):
    """Schema for CrewAI structured output."""

    revenue_analysis: str = Field(..., description="Revenue and growth analysis")
    profitability_analysis: str = Field(
        ...,
        description="Profitability metrics and trends",
    )
    cash_flow_analysis: str = Field(
        ...,
        description="Cash flow and liquidity analysis",
    )
    risk_assessment: str = Field(..., description="Financial risks identified")
    recommendation: str = Field(
        ...,
        description="Investment recommendation",
        pattern="^(BUY|HOLD|SELL)$",
    )
    confidence_score: int = Field(
        ...,
        description="Confidence in recommendation",
        ge=0,
        le=100,
    )
    cited_sources: list[str] = Field(
        default_factory=list,
        description="Document excerpts cited in analysis",
    )
    reasoning: str = Field(..., description="Detailed reasoning for recommendation")

    model_config = ConfigDict(from_attributes=True)
