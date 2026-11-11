from fastapi.testclient import TestClient

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None

from app.main import app

client = TestClient(app)


def _make_sample_wiring_pdf(path):
    if fitz is not None:
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), 'N47-5 - ESP control unit')
        page.insert_text((72, 96), 'B34 - brake pressure sensor')
        page.insert_text((72, 120), 'N47-5 X001-1 -> B34 X002-2 ; brown wire ; 0.5 mm² ; signal')
        page.insert_text((72, 144), 'B34 X002-3 -> N47-5 X001-5 ; black wire ; 0.5 mm² ; ground')
        page.insert_text((72, 168), 'X001 connector pin 1 to X002 pin 2')
        page.draw_line((90, 220), (220, 220), color=(0, 0, 0), width=2)
        page.draw_line((90, 260), (220, 260), color=(0, 0, 0), width=2)
        document.save(path)
        document.close()
        return

    pdf_text = '''%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 220] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 220 >>
stream
BT
/F1 12 Tf
72 180 Td
(N47-5 - ESP control unit) Tj
0 -24 Td
(B34 - brake pressure sensor) Tj
0 -24 Td
(N47-5 X001-1 -> B34 X002-2 ; brown wire ; 0.5 mm² ; signal) Tj
0 -24 Td
(B34 X002-3 -> N47-5 X001-5 ; black wire ; 0.5 mm² ; ground) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000062 00000 n 
0000000123 00000 n 
0000000245 00000 n 
0000000876 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
953
%%EOF
'''
    path.write_bytes(pdf_text.encode('latin-1'))


def test_health_check():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_document_upload_and_processing(tmp_path):
    sample = tmp_path / 'sample_wiring.pdf'
    _make_sample_wiring_pdf(sample)

    response = client.post(
        '/api/documents/upload',
        files={'file': ('sample_wiring.pdf', sample.read_bytes(), 'application/pdf')},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    document_id = payload['document_id']

    process_response = client.post(f'/api/documents/{document_id}/process')
    assert process_response.status_code == 200, process_response.text

    status_response = client.get(f'/api/documents/{document_id}/status')
    assert status_response.status_code == 200
    assert status_response.json()['status'] in {'processed', 'review_required'}

    connections_response = client.get(f'/api/documents/{document_id}/connections')
    assert connections_response.status_code == 200
    assert len(connections_response.json()) >= 1

    validation_response = client.post(f'/api/documents/{document_id}/validate')
    assert validation_response.status_code == 200
    validation_payload = validation_response.json()
    assert validation_payload['document_id'] == document_id
    assert validation_payload['validation_status'] in {'requires_review', 'passed'}

    connections = client.get(f'/api/documents/{document_id}/connections').json()
    assert len(connections) >= 1
    connection_id = connections[0]['connection_id']

    approve_response = client.post(
        f'/api/connections/{connection_id}/review',
        json={'reviewer': 'qa-reviewer', 'action': 'approve', 'comment': 'Confirmed after manual review.'},
    )
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()['approval_status'] == 'approved'

    review_queue = client.get(f'/api/documents/{document_id}/review')
    assert review_queue.status_code == 200, review_queue.text
