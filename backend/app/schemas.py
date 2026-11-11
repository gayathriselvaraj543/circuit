from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ConnectionPayload(BaseModel):
    from_component: Optional[str] = None
    from_connector: Optional[str] = None
    from_pin: Optional[str] = None
    to_component: Optional[str] = None
    to_connector: Optional[str] = None
    to_pin: Optional[str] = None
    wire_colour: Optional[str] = None
    wire_cross_section_mm2: Optional[float] = None
    electrical_function: Optional[str] = None
    confidence: Optional[float] = None
    extraction_status: str = 'extracted'
    approval_status: str = 'pending'
    uncertainty_reason: Optional[str] = None


class DashboardStats(BaseModel):
    total_documents: int
    processing_jobs: int
    completed_extractions: int
    pending_reviews: int
    approved_connections: int
    validation_issues: int
