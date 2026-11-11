import { useEffect, useState } from 'react';
import axios from 'axios';

const api = axios.create({ baseURL: 'http://localhost:8000/api' });

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [statsRes, docsRes] = await Promise.all([api.get('/dashboard'), api.get('/documents')]);
        setStats(statsRes.data);
        setDocuments(docsRes.data);

        if (docsRes.data.length > 0) {
          const firstDocumentId = docsRes.data[0].document_id;
          const connectionsRes = await api.get(`/documents/${firstDocumentId}/connections`);
          setConnections(connectionsRes.data);
        }
      } catch (error) {
        console.error('Failed to load dashboard data', error);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  if (loading) {
    return <div className="card">Loading real document data…</div>;
  }

  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          ['Total uploaded documents', stats?.total_documents ?? 0],
          ['Processing jobs', stats?.processing_jobs ?? 0],
          ['Completed extractions', stats?.completed_extractions ?? 0],
          ['Pending reviews', stats?.pending_reviews ?? 0],
        ].map(([label, value]) => (
          <div key={label} className="card">
            <div className="text-sm text-slate-400">{label}</div>
            <div className="mt-2 text-3xl font-semibold">{value}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <h3 className="mb-4 text-lg font-semibold">Recent documents</h3>
        {documents.length === 0 ? (
          <p className="text-sm text-slate-400">No uploaded documents yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-slate-400">
                <tr>
                  <th>Filename</th>
                  <th>Status</th>
                  <th>Type</th>
                  <th>Pages</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.document_id} className="border-t border-slate-800">
                    <td className="py-3">{doc.filename}</td>
                    <td>{doc.status}</td>
                    <td>{doc.document_type}</td>
                    <td>{doc.page_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <h3 className="mb-4 text-lg font-semibold">Extraction results</h3>
        {connections.length === 0 ? (
          <p className="text-sm text-slate-400">No extraction results yet for the selected document.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-slate-400">
                <tr>
                  <th>Source</th>
                  <th>Destination</th>
                  <th>Wire</th>
                  <th>Confidence</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {connections.map((connection) => (
                  <tr key={connection.connection_id} className="border-t border-slate-800">
                    <td>{connection.from_component || '—'} / {connection.from_pin || '—'}</td>
                    <td>{connection.to_component || '—'} / {connection.to_pin || '—'}</td>
                    <td>{connection.wire_colour || 'unknown'}</td>
                    <td>{connection.confidence ?? 'n/a'}</td>
                    <td>{connection.extraction_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
