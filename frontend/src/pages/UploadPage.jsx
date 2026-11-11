import { useState } from 'react';
import axios from 'axios';

const api = axios.create({ baseURL: 'http://localhost:8000/api' });

export default function UploadPage() {
  const [status, setStatus] = useState('idle');
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [connections, setConnections] = useState([]);
  const [validation, setValidation] = useState([]);
  const [pages, setPages] = useState([]);
  const [selectedPage, setSelectedPage] = useState(null);
  const [documentId, setDocumentId] = useState(null);
  const [reviewer, setReviewer] = useState('reviewer');

  async function loadDocumentData(documentId) {
    const [connectionsResponse, validationResponse, pagesResponse] = await Promise.all([
      api.get(`/documents/${documentId}/connections`),
      api.get(`/documents/${documentId}/validation`),
      api.get(`/documents/${documentId}/pages`),
    ]);

    setConnections(connectionsResponse.data);
    setValidation(validationResponse.data.issues || []);
    setPages(pagesResponse.data.pages || []);
    setSelectedPage((pagesResponse.data.pages || [])[0] || null);
    setStatus(validationResponse.data.validation_status || 'processed');
  }

  async function handleReviewAction(connectionId, action) {
    try {
      const response = await api.post(`/connections/${connectionId}/review`, {
        reviewer,
        action,
        comment: action === 'approve' ? 'Approved after manual review.' : 'Rejected after manual review.',
      });

      setConnections((current) =>
        current.map((connection) =>
          connection.connection_id === connectionId
            ? { ...connection, approval_status: response.data.approval_status, extraction_status: response.data.approval_status }
            : connection,
        ),
      );
      setStatus(response.data.approval_status);
    } catch (error) {
      setStatus('error');
      setResult({ error: error.response?.data?.detail || error.message });
    }
  }

  async function handleExport(format) {
    if (!documentId) return;

    try {
      const response = await api.get(`/documents/${documentId}/export/${format}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: response.headers['content-type'] }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `connections.${format === 'json' ? 'json' : format === 'csv' ? 'csv' : 'xlsx'}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      setStatus('export_error');
      setResult({ error: error.response?.data?.detail || error.message });
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    setStatus('uploading');

    try {
      const uploadResponse = await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const documentIdValue = uploadResponse.data.document_id;
      setDocumentId(documentIdValue);
      const processResponse = await api.post(`/documents/${documentIdValue}/process`);
      setResult(processResponse.data);
      await loadDocumentData(documentIdValue);
    } catch (error) {
      setStatus('error');
      setResult({ error: error.response?.data?.detail || error.message });
    }
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div className="card">
        <h2 className="mb-6 text-2xl font-semibold">Document upload</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
            className="block w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
          <button type="submit" className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-500">
            Upload and process document
          </button>
        </form>
      </div>

      <div className="card">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm text-slate-400">Status</div>
            <div className="mt-2 font-medium">{status}</div>
          </div>
          <div className="w-48">
            <label className="mb-1 block text-xs text-slate-400">Reviewer</label>
            <input
              value={reviewer}
              onChange={(event) => setReviewer(event.target.value)}
              className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
            />
          </div>
        </div>
        {documentId && (
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" onClick={() => handleExport('json')} className="rounded bg-slate-700 px-3 py-1.5 text-xs text-white hover:bg-slate-600">Export JSON</button>
            <button type="button" onClick={() => handleExport('csv')} className="rounded bg-slate-700 px-3 py-1.5 text-xs text-white hover:bg-slate-600">Export CSV</button>
            <button type="button" onClick={() => handleExport('excel')} className="rounded bg-slate-700 px-3 py-1.5 text-xs text-white hover:bg-slate-600">Export Excel</button>
          </div>
        )}
        {result && (
          <pre className="mt-4 overflow-auto rounded bg-slate-950 p-4 text-xs text-slate-300">
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </div>

      {pages.length > 0 && (
        <div className="card">
          <div className="mb-4 flex items-center justify-between gap-4">
            <h3 className="text-lg font-semibold">Document evidence</h3>
            <div className="flex flex-wrap gap-2">
              {pages.map((page) => (
                <button
                  key={page.page_number}
                  type="button"
                  onClick={() => setSelectedPage(page)}
                  className={`rounded px-2 py-1 text-xs ${selectedPage?.page_number === page.page_number ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-300'}`}
                >
                  Page {page.page_number}
                </button>
              ))}
            </div>
          </div>

          {selectedPage && (
            <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
              <div className="rounded border border-slate-700 bg-slate-950 p-3">
                {selectedPage.preview_url ? (
                  <img
                    src={`http://localhost:8000${selectedPage.preview_url}`}
                    alt={`Page ${selectedPage.page_number} preview`}
                    className="max-h-[420px] w-full rounded object-contain"
                  />
                ) : (
                  <div className="flex min-h-[240px] items-center justify-center text-sm text-slate-400">No preview available</div>
                )}
              </div>

              <div className="rounded border border-slate-700 bg-slate-950 p-3">
                <div className="mb-2 text-xs uppercase tracking-wide text-slate-400">Extracted text</div>
                <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap text-xs text-slate-300">
                  {selectedPage.extracted_text || 'No page text extracted.'}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h3 className="mb-4 text-lg font-semibold">Extracted connections</h3>
        {connections.length === 0 ? (
          <p className="text-sm text-slate-400">No real extraction results yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-slate-400">
                <tr>
                  <th>Source</th>
                  <th>Destination</th>
                  <th>Wire</th>
                  <th>Function</th>
                  <th>Confidence</th>
                  <th>Status</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {connections.map((conn) => (
                  <tr key={conn.connection_id} className="border-t border-slate-800">
                    <td>{conn.from_component || '—'} / {conn.from_pin || '—'}</td>
                    <td>{conn.to_component || '—'} / {conn.to_pin || '—'}</td>
                    <td>{conn.wire_colour || 'unknown'}</td>
                    <td>{conn.electrical_function || 'not specified'}</td>
                    <td>{conn.confidence ?? 'n/a'}</td>
                    <td>{conn.approval_status || conn.extraction_status}</td>
                    <td className="space-x-2">
                      <button
                        type="button"
                        onClick={() => handleReviewAction(conn.connection_id, 'approve')}
                        className="rounded bg-green-600 px-2 py-1 text-xs text-white hover:bg-green-500"
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        onClick={() => handleReviewAction(conn.connection_id, 'reject')}
                        className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-500"
                      >
                        Reject
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h3 className="mb-4 text-lg font-semibold">Validation findings</h3>
        {validation.length === 0 ? (
          <p className="text-sm text-slate-400">No validation issues were raised for this extraction.</p>
        ) : (
          <ul className="space-y-2 text-sm text-slate-300">
            {validation.map((issue) => (
              <li key={issue.issue_id} className="rounded border border-slate-700 p-3">
                <div className="font-medium">{issue.severity}: {issue.category}</div>
                <div>{issue.description}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
