from __future__ import annotations

import csv
import io
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from openpyxl import Workbook
from sqlmodel import Session, select

from app.db import engine
from app.models import Approval, Connection, Document, DocumentPage, ProcessingJob, ValidationIssue, ValidationRun
from app.services.document_processor import process_document, validate_document

router = APIRouter(prefix='/api', tags=['documents'])


@router.get('/health')
async def health():
    return {'status': 'ok', 'service': 'wiring-extraction-backend'}


@router.get('/dashboard')
async def dashboard():
    with Session(engine) as session:
        documents = session.exec(select(Document)).all()
        connections = session.exec(select(Connection)).all()
        issues = session.exec(select(ValidationIssue)).all()
        jobs = session.exec(select(ProcessingJob)).all()
        return {
            'total_documents': len(documents),
            'processing_jobs': len(jobs),
            'completed_extractions': sum(1 for doc in documents if doc.status == 'processed'),
            'pending_reviews': sum(1 for connection in connections if connection.approval_status == 'pending'),
            'approved_connections': sum(1 for connection in connections if connection.approval_status == 'approved'),
            'validation_issues': len(issues),
        }


@router.post('/documents/upload')
async def upload_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    if not file.filename:
        raise HTTPException(status_code=400, detail='A filename is required.')

    ext = Path(file.filename).suffix.lower()
    if ext not in {'.pdf', '.png', '.jpg', '.jpeg'}:
        raise HTTPException(status_code=400, detail='Unsupported file type. Use PDF, PNG, JPG, or JPEG.')

    document_id = str(uuid.uuid4())
    upload_dir = Path('backend/storage/uploads')
    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_path = upload_dir / f'{document_id}{ext}'
    content = await file.read()
    storage_path.write_bytes(content)

    doc = Document(
        id=document_id,
        filename=file.filename,
        storage_path=str(storage_path),
        content_type=file.content_type or 'application/octet-stream',
        status='uploaded',
        document_type='pdf' if ext == '.pdf' else 'image',
        page_count=1,
    )

    with Session(engine) as session:
        session.add(doc)
        session.commit()

    process_document(document_id)
    validation = validate_document(document_id)
    return {
        'document_id': document_id,
        'filename': file.filename,
        'status': 'processed',
        'validation_status': validation['validation_status'],
        'issues': validation['issues'],
    }


@router.get('/documents')
async def list_documents():
    with Session(engine) as session:
        docs = session.exec(select(Document)).all()
        return [
            {
                'document_id': doc.id,
                'filename': doc.filename,
                'status': doc.status,
                'document_type': doc.document_type,
                'page_count': doc.page_count,
                'created_at': doc.created_at.isoformat(),
            }
            for doc in docs
        ]


@router.get('/documents/{document_id}')
async def get_document(document_id: str):
    with Session(engine) as session:
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail='Document not found')
        return {
            'document_id': doc.id,
            'filename': doc.filename,
            'status': doc.status,
            'document_type': doc.document_type,
            'manufacturer': doc.manufacturer,
            'model': doc.model,
            'engine': doc.engine,
            'variant': doc.variant,
            'page_count': doc.page_count,
            'extraction_summary': doc.extraction_summary,
            'storage_path': doc.storage_path,
        }


@router.get('/documents/{document_id}/pages')
async def get_document_pages(document_id: str):
    with Session(engine) as session:
        pages = session.exec(select(DocumentPage).where(DocumentPage.document_id == document_id)).all()
        if not pages:
            return {'document_id': document_id, 'pages': []}

        response = []
        for page in pages:
            preview_url = None
            if page.file_path:
                normalized = str(page.file_path).replace('\\', '/')
                if normalized.startswith('backend/storage/'):
                    preview_url = '/' + normalized.replace('backend/', '', 1)
                else:
                    preview_url = '/storage/' + Path(normalized).name
            response.append({
                'page_number': page.page_number,
                'status': page.status,
                'extracted_text': page.extracted_text,
                'ocr_text': page.ocr_text,
                'file_path': page.file_path,
                'preview_url': preview_url,
                'page_type': page.page_type,
            })
        return {'document_id': document_id, 'pages': sorted(response, key=lambda p: p['page_number'])}


@router.get('/documents/{document_id}/pages/{page_number}')
async def get_document_page(document_id: str, page_number: int):
    with Session(engine) as session:
        page = session.exec(
            select(DocumentPage).where(DocumentPage.document_id == document_id, DocumentPage.page_number == page_number)
        ).first()
        if not page:
            raise HTTPException(status_code=404, detail='Document page not found')
        preview_url = None
        if page.file_path:
            normalized = str(page.file_path).replace('\\', '/')
            if normalized.startswith('backend/storage/'):
                preview_url = '/' + normalized.replace('backend/', '', 1)
            else:
                preview_url = '/storage/' + Path(normalized).name
        return {
            'document_id': document_id,
            'page_number': page.page_number,
            'status': page.status,
            'extracted_text': page.extracted_text,
            'ocr_text': page.ocr_text,
            'file_path': page.file_path,
            'preview_url': preview_url,
            'page_type': page.page_type,
        }


@router.post('/documents/{document_id}/process')
async def process_document_endpoint(document_id: str, background_tasks: BackgroundTasks):
    process_document(document_id)
    validation = validate_document(document_id)
    return {
        'document_id': document_id,
        'status': 'processed',
        'validation_status': validation['validation_status'],
        'issues': validation['issues'],
    }


@router.get('/documents/{document_id}/status')
async def get_document_status(document_id: str):
    with Session(engine) as session:
        doc = session.get(Document, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail='Document not found')
        return {'document_id': doc.id, 'status': doc.status, 'extraction_summary': doc.extraction_summary}


@router.get('/documents/{document_id}/components')
async def get_components(document_id: str):
    with Session(engine) as session:
        rows = session.exec(select(Connection).where(Connection.document_id == document_id)).all()
        return [{'id': row.id, 'connection_id': row.connection_id, 'from_component': row.from_component, 'to_component': row.to_component} for row in rows]


@router.get('/documents/{document_id}/connections')
async def get_connections(document_id: str):
    with Session(engine) as session:
        rows = session.exec(select(Connection).where(Connection.document_id == document_id)).all()
        return [
            {
                'connection_id': row.connection_id,
                'from_component': row.from_component,
                'from_connector': row.from_connector,
                'from_pin': row.from_pin,
                'to_component': row.to_component,
                'to_connector': row.to_connector,
                'to_pin': row.to_pin,
                'wire_colour': row.wire_colour,
                'wire_cross_section_mm2': row.wire_cross_section_mm2,
                'electrical_function': row.electrical_function,
                'confidence': row.confidence,
                'extraction_status': row.extraction_status,
                'approval_status': row.approval_status,
                'uncertainty_reason': row.uncertainty_reason,
            }
            for row in rows
        ]


@router.get('/documents/{document_id}/validation')
async def get_validation(document_id: str):
    with Session(engine) as session:
        validation_run = session.exec(select(ValidationRun).where(ValidationRun.document_id == document_id)).first()
        if not validation_run:
            return {'document_id': document_id, 'validation_status': 'pending', 'issues': []}
        issues = session.exec(select(ValidationIssue).where(ValidationIssue.validation_run_id == validation_run.id)).all()
        return {
            'document_id': document_id,
            'validation_status': validation_run.validation_status,
            'issues': [
                {
                    'issue_id': issue.id,
                    'connection_id': issue.connection_id,
                    'severity': issue.severity,
                    'category': issue.category,
                    'description': issue.description,
                    'recommended_action': issue.recommended_action,
                }
                for issue in issues
            ],
        }


@router.post('/documents/{document_id}/validate')
async def validate_document_endpoint(document_id: str):
    try:
        result = validate_document(document_id)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get('/documents/{document_id}/review')
async def get_review_queue(document_id: str):
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail='Document not found')

        rows = session.exec(select(Connection).where(Connection.document_id == document_id)).all()
        pending = [
            {
                'connection_id': row.connection_id,
                'from_component': row.from_component,
                'from_connector': row.from_connector,
                'from_pin': row.from_pin,
                'to_component': row.to_component,
                'to_connector': row.to_connector,
                'to_pin': row.to_pin,
                'wire_colour': row.wire_colour,
                'wire_cross_section_mm2': row.wire_cross_section_mm2,
                'electrical_function': row.electrical_function,
                'confidence': row.confidence,
                'extraction_status': row.extraction_status,
                'approval_status': row.approval_status,
                'uncertainty_reason': row.uncertainty_reason,
            }
            for row in rows
            if row.approval_status in {'pending', 'requires_review'} or row.extraction_status in {'uncertain', 'failed'}
        ]
        return {
            'document_id': document_id,
            'pending_count': len(pending),
            'connections': pending,
        }


@router.patch('/connections/{connection_id}')
async def patch_connection(connection_id: str, payload: dict):
    with Session(engine) as session:
        connection = session.exec(select(Connection).where(Connection.connection_id == connection_id)).first()
        if not connection:
            raise HTTPException(status_code=404, detail='Connection not found')
        for field, value in payload.items():
            if hasattr(connection, field):
                setattr(connection, field, value)
        session.add(connection)
        session.commit()
        return {'connection_id': connection.connection_id, 'status': 'updated'}


@router.post('/connections/{connection_id}/review')
async def review_connection(connection_id: str, payload: dict):
    reviewer = payload.get('reviewer') or 'reviewer'
    action = payload.get('action', 'pending').lower()
    comment = payload.get('comment') or 'Reviewed in UI'
    corrected_fields = payload.get('corrected_fields') or {}

    if action not in {'approve', 'reject'}:
        raise HTTPException(status_code=400, detail='Action must be approve or reject.')

    with Session(engine) as session:
        connection = session.exec(select(Connection).where(Connection.connection_id == connection_id)).first()
        if not connection:
            raise HTTPException(status_code=404, detail='Connection not found')

        for field, value in corrected_fields.items():
            if hasattr(connection, field):
                setattr(connection, field, value)

        connection.approval_status = 'approved' if action == 'approve' else 'rejected'
        connection.extraction_status = 'approved' if action == 'approve' else 'rejected'
        if action == 'approve':
            connection.uncertainty_reason = connection.uncertainty_reason or 'Approved by reviewer after source inspection.'
        else:
            connection.uncertainty_reason = connection.uncertainty_reason or 'Rejected by reviewer after source inspection.'

        session.add(connection)
        session.add(
            Approval(
                id=str(uuid.uuid4()),
                connection_id=connection.id,
                reviewer=reviewer,
                action=action,
                comment=comment,
                original_value=connection.uncertainty_reason,
                corrected_value=comment,
            )
        )
        session.commit()
        return {'connection_id': connection.connection_id, 'approval_status': connection.approval_status}


@router.post('/connections/{connection_id}/approve')
async def approve_connection(connection_id: str, payload: dict | None = None):
    payload = payload or {}
    return await review_connection(connection_id, {'reviewer': payload.get('reviewer', 'reviewer'), 'action': 'approve', 'comment': payload.get('comment', 'Approved in UI')})


@router.post('/connections/{connection_id}/reject')
async def reject_connection(connection_id: str, payload: dict | None = None):
    payload = payload or {}
    return await review_connection(connection_id, {'reviewer': payload.get('reviewer', 'reviewer'), 'action': 'reject', 'comment': payload.get('comment', 'Rejected in UI')})


def _serialize_connections_for_export(connections):
    return [
        {
            'connection_id': conn.connection_id,
            'from_component': conn.from_component,
            'from_connector': conn.from_connector,
            'from_pin': conn.from_pin,
            'to_component': conn.to_component,
            'to_connector': conn.to_connector,
            'to_pin': conn.to_pin,
            'wire_colour': conn.wire_colour,
            'wire_cross_section_mm2': conn.wire_cross_section_mm2,
            'electrical_function': conn.electrical_function,
            'extraction_status': conn.extraction_status,
            'approval_status': conn.approval_status,
            'confidence': conn.confidence,
            'uncertainty_reason': conn.uncertainty_reason,
        }
        for conn in connections
    ]


@router.get('/documents/{document_id}/export/json')
async def export_json(document_id: str):
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail='Document not found')
        connections = session.exec(select(Connection).where(Connection.document_id == document_id)).all()
        payload = {
            'document_id': document_id,
            'filename': document.filename,
            'connections': _serialize_connections_for_export(connections),
        }
        return JSONResponse(content=payload)


@router.get('/documents/{document_id}/export/csv')
async def export_csv(document_id: str):
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail='Document not found')
        connections = session.exec(select(Connection).where(Connection.document_id == document_id)).all()

        output = io.StringIO()
        fieldnames = [
            'connection_id',
            'from_component',
            'from_connector',
            'from_pin',
            'to_component',
            'to_connector',
            'to_pin',
            'wire_colour',
            'wire_cross_section_mm2',
            'electrical_function',
            'extraction_status',
            'approval_status',
            'confidence',
            'uncertainty_reason',
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for conn in connections:
            writer.writerow({
                'connection_id': conn.connection_id,
                'from_component': conn.from_component,
                'from_connector': conn.from_connector,
                'from_pin': conn.from_pin,
                'to_component': conn.to_component,
                'to_connector': conn.to_connector,
                'to_pin': conn.to_pin,
                'wire_colour': conn.wire_colour,
                'wire_cross_section_mm2': conn.wire_cross_section_mm2,
                'electrical_function': conn.electrical_function,
                'extraction_status': conn.extraction_status,
                'approval_status': conn.approval_status,
                'confidence': conn.confidence,
                'uncertainty_reason': conn.uncertainty_reason,
            })

        filename = f'{Path(document.filename).stem}_connections.csv'
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )


@router.get('/documents/{document_id}/export/excel')
async def export_excel(document_id: str):
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail='Document not found')
        connections = session.exec(select(Connection).where(Connection.document_id == document_id)).all()

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'connections'
        headers = [
            'connection_id',
            'from_component',
            'from_connector',
            'from_pin',
            'to_component',
            'to_connector',
            'to_pin',
            'wire_colour',
            'wire_cross_section_mm2',
            'electrical_function',
            'extraction_status',
            'approval_status',
            'confidence',
            'uncertainty_reason',
        ]
        sheet.append(headers)
        for conn in connections:
            sheet.append([
                conn.connection_id,
                conn.from_component,
                conn.from_connector,
                conn.from_pin,
                conn.to_component,
                conn.to_connector,
                conn.to_pin,
                conn.wire_colour,
                conn.wire_cross_section_mm2,
                conn.electrical_function,
                conn.extraction_status,
                conn.approval_status,
                conn.confidence,
                conn.uncertainty_reason,
            ])

        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        filename = f'{Path(document.filename).stem}_connections.xlsx'
        return StreamingResponse(
            output,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )
