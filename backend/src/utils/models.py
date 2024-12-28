"""
Pydantic models for the FDA RAG pipeline
"""
from pydantic import BaseModel, Field
from typing import Optional

class GradeDocuments(BaseModel):
    """Model for document grading results."""
    binary_score: str = Field(description="Relevance score of 'yes' or 'no'")
    comments: Optional[str] = Field(description="Comments explaining the relevance")