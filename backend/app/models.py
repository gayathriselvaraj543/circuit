from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class Document(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    filename: str
    storage_path: str
    content_type: str
    status: str = 'uploaded'
    document_type: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    model_year: Optional[str] = None
    engine: Optional[str] = None
    variant: Optional[str] = None
    revision: Optional[str] = None
    page_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    extraction_summary: Optional[str] = Field(default=None, sa_column=Column(Text))


class DocumentPage(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    document_id: str = Field(foreign_key='document.id')
    page_number: int
    file_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    extracted_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    ocr_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    status: str = 'pending'
    page_type: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Component(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    document_id: str = Field(foreign_key='document.id')
    component_id: str
    description: Optional[str] = None
    component_type: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Connector(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    document_id: str = Field(foreign_key='document.id')
    component_id: Optional[str] = None
    connector_id: str
    location: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ConnectorPin(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    connector_id: str = Field(foreign_key='connector.id')
    pin_number: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Connection(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    document_id: str = Field(foreign_key='document.id')
    connection_id: str
    from_component: Optional[str] = None
    from_connector: Optional[str] = None
    from_pin: Optional[str] = None
    to_component: Optional[str] = None
    to_connector: Optional[str] = None
    to_pin: Optional[str] = None
    wire_colour: Optional[str] = None
    wire_cross_section_mm2: Optional[float] = None
    electrical_function: Optional[str] = None
    applicability: Optional[str] = Field(default=None, sa_column=Column(Text))
    extraction_status: str = 'extracted'
    approval_status: str = 'pending'
    confidence: Optional[float] = None
    uncertainty_reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ConnectionEvidence(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    connection_id: str = Field(foreign_key='connection.id')
    page: int
    region: Optional[str] = None
    source_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    processing_method: str = 'heuristic'
    confidence: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VehicleApplicability(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    document_id: str = Field(foreign_key='document.id')
    applicability_text: str
    normalized_value: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ValidationRun(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    document_id: str = Field(foreign_key='document.id')
    validation_status: str = 'pending'
    summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ValidationIssue(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    validation_run_id: str = Field(foreign_key='validationrun.id')
    connection_id: Optional[str] = None
    severity: str = 'medium'
    category: str = 'general'
    description: str
    recommended_action: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Approval(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    connection_id: str = Field(foreign_key='connection.id')
    reviewer: str = 'system'
    action: str = 'pending'
    comment: Optional[str] = None
    original_value: Optional[str] = Field(default=None, sa_column=Column(Text))
    corrected_value: Optional[str] = Field(default=None, sa_column=Column(Text))
    approved_at: datetime = Field(default_factory=datetime.utcnow)


class ProcessingJob(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    document_id: str = Field(foreign_key='document.id')
    status: str = 'queued'
    progress: int = 0
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
