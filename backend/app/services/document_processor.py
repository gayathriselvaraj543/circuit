from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

from sqlmodel import Session, select

from app.db import engine
from app.models import (
    Component,
    Connection,
    ConnectionEvidence,
    Document,
    DocumentPage,
    ProcessingJob,
    ValidationIssue,
    ValidationRun,
)

COMPONENT_RE = re.compile(r'(?P<id>[A-Z]\d+[A-Z0-9\-./]*)\s*(?:-|–|:)\s*(?P<desc>[A-Za-z0-9 /&()]+)')
CONNECTOR_RE = re.compile(r'(?P<connector>(?:X|Y|P|Q|K|T)\d+[A-Z0-9\-]*)')
PIN_LINK_RE = re.compile(
    r'(?P<from_component>[A-Z]\d+[A-Z0-9\-./]*)\s*(?P<from_connector>(?:X|Y|P|Q|K|T)\d+[A-Z0-9\-]*)\s*[-:]\s*(?P<from_pin>\d+)\s*(?:->|to|=)\s*(?P<to_component>[A-Z]\d+[A-Z0-9\-./]*)\s*(?P<to_connector>(?:X|Y|P|Q|K|T)\d+[A-Z0-9\-]*)\s*[-:]\s*(?P<to_pin>\d+)'
)
WIRE_RE = re.compile(r'(?P<colour>black|brown|blue|green|grey|gray|white|red|yellow|orange|pink|violet|brown|bk|br|gn|wh|rd|bl|yl|or|pk|gy)\s+wire', re.I)
SIZE_RE = re.compile(r'(?P<size>\d+(?:\.\d+)?)\s*mm\s*\^?2?', re.I)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    Image = ImageDraw = ImageFont = None


def _utcnow():
    return datetime.now(timezone.utc)


def _extract_components_from_text(text: str):
    components = []
    seen = set()
    for line in text.splitlines():
        match = COMPONENT_RE.search(line)
        if not match:
            continue
        component_id = match.group('id').strip()
        description = match.group('desc').strip()
        if component_id in seen:
            continue
        seen.add(component_id)
        components.append({'component_id': component_id, 'description': description})
    return components


def _extract_connectors_from_text(text: str):
    connectors = []
    seen = set()
    for token in CONNECTOR_RE.findall(text):
        if token not in seen:
            connectors.append(token)
            seen.add(token)
    return connectors


def _extract_connections_from_text(text: str):
    candidates = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = PIN_LINK_RE.search(line)
        if not match:
            continue

        from_component = match.group('from_component')
        from_connector = match.group('from_connector')
        from_pin = match.group('from_pin')
        to_component = match.group('to_component')
        to_connector = match.group('to_connector')
        to_pin = match.group('to_pin')

        wire_match = WIRE_RE.search(line)
        size_match = SIZE_RE.search(line)
        wire_colour = wire_match.group('colour').lower() if wire_match else None
        wire_cross_section = float(size_match.group('size')) if size_match else None
        electrical_function = None
        if 'ground' in line.lower() or 'earth' in line.lower():
            electrical_function = 'ground'
        elif 'signal' in line.lower() or 'control' in line.lower():
            electrical_function = 'signal'

        candidates.append({
            'connection_id': f'CONN_{len(candidates) + 1:03d}',
            'from_component': from_component,
            'from_connector': from_connector,
            'from_pin': from_pin,
            'to_component': to_component,
            'to_connector': to_connector,
            'to_pin': to_pin,
            'wire_colour': wire_colour,
            'wire_cross_section_mm2': wire_cross_section,
            'electrical_function': electrical_function,
            'confidence': 0.75,
            'status': 'uncertain',
            'uncertainty_reason': 'Connection inferred from explicit source text references and requires human review.',
        })

    return candidates


def _raw_pdf_text(file_path: Path) -> str:
    raw = file_path.read_bytes()
    decoded = raw.decode('latin-1', errors='ignore')
    matches = re.findall(r'\(([^()\\]*(?:\\.[^()\\]*)*)\)', decoded)
    extracted = []
    for candidate in matches:
        value = candidate.replace('\\(', '(').replace('\\)', ')').replace('\\n', '\n').replace('\\r', '\n')
        extracted.append(value)
    return '\n'.join(extracted)


def _create_preview_image(preview: Path, text: str):
    if Image is not None:
        image = Image.new('RGB', (1000, 600), 'white')
        draw = ImageDraw.Draw(image)
        draw.text((40, 40), text[:200], fill='black')
        preview.parent.mkdir(parents=True, exist_ok=True)
        image.save(preview)
        return

    if cv2 is not None:
        preview.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(preview), 255 * __import__('numpy').ones((600, 1000, 3), dtype='uint8'))


def _extract_pages(document: Document):
    file_path = Path(document.storage_path)
    pages = []

    if file_path.suffix.lower() == '.pdf':
        if fitz is not None:
            pdf = fitz.open(file_path)
            for index, page in enumerate(pdf, start=1):
                text = page.get_text('text')
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                preview = Path('backend/storage/previews') / f'{document.id}_{index}.png'
                preview.parent.mkdir(parents=True, exist_ok=True)
                pix.save(str(preview))
                pages.append({'page_number': index, 'text': text or '', 'preview_path': str(preview)})
            pdf.close()
            return pages

        text = _raw_pdf_text(file_path)
        preview = Path('backend/storage/previews') / f'{document.id}_1.png'
        _create_preview_image(preview, text)
        pages.append({'page_number': 1, 'text': text or 'PDF text extraction fallback used due to missing PyMuPDF runtime.', 'preview_path': str(preview)})
        return pages

    if file_path.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
        image = cv2.imread(str(file_path)) if cv2 is not None else None
        if image is not None:
            preview = Path('backend/storage/previews') / f'{document.id}_1.png'
            preview.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(preview), image)
            text = pytesseract.image_to_string(image) if pytesseract is not None else 'OCR unavailable'
            pages.append({'page_number': 1, 'text': text, 'preview_path': str(preview)})
            return pages

    fallback_text = 'Document uploaded; no usable text or OCR output was available.'
    preview = Path('backend/storage/previews') / f'{document.id}_1.txt'
    preview.parent.mkdir(parents=True, exist_ok=True)
    preview.write_text(fallback_text, encoding='utf-8')
    pages.append({'page_number': 1, 'text': fallback_text, 'preview_path': str(preview)})
    return pages


def process_document(document_id: str):
    with Session(engine) as session:
        doc = session.get(Document, document_id)
        if not doc:
            return

        job = ProcessingJob(
            id=str(uuid.uuid4()),
            document_id=document_id,
            status='running',
            progress=10,
            message='Reading uploaded file and extracting page text.',
        )
        session.add(job)
        session.commit()

        pages = _extract_pages(doc)
        doc.page_count = len(pages)
        doc.status = 'processing'
        session.add(doc)
        session.commit()

        combined_text = '\n\n'.join(page['text'] for page in pages if page.get('text'))
        components = _extract_components_from_text(combined_text)
        connectors = _extract_connectors_from_text(combined_text)
        connections = _extract_connections_from_text(combined_text)

        for page in pages:
            session.add(
                DocumentPage(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    page_number=page['page_number'],
                    file_path=page['preview_path'],
                    extracted_text=page['text'],
                    ocr_text=page['text'],
                    status='processed',
                    page_type='diagram' if 'diagram' in combined_text.lower() or 'x001' in combined_text.lower() else 'reference',
                )
            )

        for item in components:
            session.add(
                Component(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    component_id=item['component_id'],
                    description=item['description'],
                    component_type='unit',
                )
            )

        for connector in connectors:
            session.add(
                Component(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    component_id=connector,
                    description='connector reference',
                    component_type='connector',
                )
            )

        if not connections:
            connections = [{
                'connection_id': 'CONN_001',
                'from_component': None,
                'from_connector': None,
                'from_pin': None,
                'to_component': None,
                'to_connector': None,
                'to_pin': None,
                'wire_colour': None,
                'wire_cross_section_mm2': None,
                'electrical_function': None,
                'confidence': 0.2,
                'status': 'failed',
                'uncertainty_reason': 'No explicit pin-to-pin connection references were found in the uploaded document.',
            }]

        for connection in connections:
            if connection.get('status') is None:
                connection['status'] = 'uncertain'
            if connection.get('confidence') is None:
                connection['confidence'] = 0.5

        for connection in connections:
            existing = session.exec(
                select(Connection).where(Connection.document_id == document_id, Connection.connection_id == connection['connection_id'])
            ).first()
            if existing is not None:
                continue

            page_number = 1
            source_text = combined_text[:1200]
            for page in pages:
                page_text = page.get('text') or ''
                if (connection['from_component'] and connection['from_component'] in page_text) or (connection['to_component'] and connection['to_component'] in page_text):
                    page_number = page['page_number']
                    source_text = page_text[:1200]
                    break

            conn = Connection(
                id=str(uuid.uuid4()),
                document_id=document_id,
                connection_id=connection['connection_id'],
                from_component=connection['from_component'],
                from_connector=connection['from_connector'],
                from_pin=connection['from_pin'],
                to_component=connection['to_component'],
                to_connector=connection['to_connector'],
                to_pin=connection['to_pin'],
                wire_colour=connection['wire_colour'],
                wire_cross_section_mm2=connection['wire_cross_section_mm2'],
                electrical_function=connection['electrical_function'],
                extraction_status=connection['status'],
                approval_status='pending',
                confidence=connection['confidence'],
                uncertainty_reason=connection['uncertainty_reason'],
            )
            session.add(conn)
            session.flush()
            session.add(
                ConnectionEvidence(
                    id=str(uuid.uuid4()),
                    connection_id=conn.id,
                    page=page_number,
                    source_text=source_text,
                    processing_method='rule_based_pdf_text_analysis',
                    confidence=connection['confidence'],
                )
            )

        doc.status = 'processed' if connections and any(c['status'] != 'failed' for c in connections) else 'review_required'
        doc.extraction_summary = f'Extracted {len(components)} component labels and {len(connections)} connection candidates from the uploaded document.'
        doc.updated_at = _utcnow()
        session.add(doc)

        job.status = 'completed' if doc.status in {'processed', 'review_required'} else 'failed'
        job.progress = 100
        job.completed_at = _utcnow()
        job.message = 'Extraction completed. Review required when connection confidence is low or uncertain.'
        session.add(job)
        session.commit()


def validate_document(document_id: str):
    with Session(engine) as session:
        document = session.get(Document, document_id)
        if not document:
            raise ValueError('Document not found')

        validation_run = ValidationRun(
            id=str(uuid.uuid4()),
            document_id=document_id,
            validation_status='in_progress',
            summary='Independent source evidence validation started.',
        )
        session.add(validation_run)
        session.commit()

        issues = []
        connections = session.exec(select(Connection).where(Connection.document_id == document_id)).all()

        for connection in connections:
            if connection.from_component is None or connection.to_component is None:
                issues.append({
                    'connection_id': connection.id,
                    'severity': 'medium',
                    'category': 'connection_mapping',
                    'description': 'A connection is missing one or more source/destination references.',
                    'recommended_action': 'Review the original document and resolve the missing endpoints.',
                })
            if connection.wire_colour is None:
                issues.append({
                    'connection_id': connection.id,
                    'severity': 'low',
                    'category': 'wire_validation',
                    'description': 'Wire colour could not be verified in the extracted source evidence.',
                    'recommended_action': 'Confirm the colour using the original diagram reference.',
                })
            if connection.confidence is not None and connection.confidence < 0.5:
                issues.append({
                    'connection_id': connection.id,
                    'severity': 'medium',
                    'category': 'evidence_validation',
                    'description': 'Connection confidence is below the minimum threshold for trusted extraction.',
                    'recommended_action': 'Request manual review of the page and surrounding evidence.',
                })
            if connection.extraction_status in {'uncertain', 'failed'}:
                issues.append({
                    'connection_id': connection.id,
                    'severity': 'medium' if connection.extraction_status == 'uncertain' else 'high',
                    'category': 'reference_validation',
                    'description': 'The connection was extracted with limited or incomplete source evidence and must be reviewed before approval.',
                    'recommended_action': 'Request human review of the source page and confirm the pin-to-pin mapping.',
                })

        for issue in issues:
            session.add(
                ValidationIssue(
                    id=str(uuid.uuid4()),
                    validation_run_id=validation_run.id,
                    connection_id=issue['connection_id'],
                    severity=issue['severity'],
                    category=issue['category'],
                    description=issue['description'],
                    recommended_action=issue['recommended_action'],
                )
            )

        validation_run.validation_status = 'requires_review' if issues else 'passed'
        validation_run.summary = f'{len(issues)} validation issues identified from the source evidence.'
        session.add(validation_run)
        session.commit()

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
                for issue in session.exec(select(ValidationIssue).where(ValidationIssue.validation_run_id == validation_run.id)).all()
            ],
        }
