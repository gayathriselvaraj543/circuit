from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()
engine = create_engine(settings['database_url'], echo=False)


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    from app.models import (
        Approval,
        Component,
        Connection,
        ConnectionEvidence,
        Connector,
        ConnectorPin,
        Document,
        DocumentPage,
        ProcessingJob,
        ValidationIssue,
        ValidationRun,
        VehicleApplicability,
    )

    SQLModel.metadata.create_all(engine)
