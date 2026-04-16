import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FileText, ExternalLink, Play } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Modal } from '@/components/ui/Modal';
import { useAuth } from '@/hooks/useAuth';
import { getDocument } from '@/services/documentService';
import { triggerAnalysis, getAnalysesByDocument } from '@/services/complianceService';
import type { Document, ComplianceAnalysis } from '@/types';

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [doc, setDoc] = useState<Document | null>(null);
  const [analyses, setAnalyses] = useState<ComplianceAnalysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  const fetchAnalyses = useCallback(() => {
    if (!id) return;
    getAnalysesByDocument(id).then(setAnalyses).catch(() => {});
  }, [id]);

  useEffect(() => {
    if (!id) return;
    getDocument(id).then(setDoc).finally(() => setLoading(false));
    fetchAnalyses();
  }, [id, fetchAnalyses]);

  // Poll for updates when any analysis is still processing
  useEffect(() => {
    const hasProcessing = analyses.some(
      (a) => a.status === 'Processing' || a.status === 'Pending'
    );
    if (!hasProcessing) return;
    const interval = setInterval(fetchAnalyses, 5000);
    return () => clearInterval(interval);
  }, [analyses, fetchAnalyses]);

  const canAnalyze = user?.role === 'Admin' || user?.role === 'Analyst';

  const handleAnalyze = async () => {
    if (!id) return;
    setAnalyzing(true);
    try {
      await triggerAnalysis(id);
      setShowModal(false);
      fetchAnalyses();
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!doc) return <div className="text-center py-12 text-gray-500">Document not found.</div>;

  return (
    <div className="space-y-8 animate-in mt-2 mb-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gradient pb-1">{doc.title}</h1>
        {canAnalyze && (
          <Button onClick={() => setShowModal(true)} className="shadow-md">
            <Play className="h-4 w-4 mr-2" /> Trigger Analysis
          </Button>
        )}
      </div>

      {/* Metadata */}
      <Card>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide">File Type</p>
            <Badge>{doc.fileType.toUpperCase()}</Badge>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide">Content Type</p>
            <p className="text-sm text-sothema-dark mt-1">{doc.contentType}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide">Uploaded</p>
            <p className="text-sm text-sothema-dark mt-1">
              {new Date(doc.uploadedAt).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide">SharePoint</p>
            <a href={doc.sharePointUrl} target="_blank" rel="noreferrer" className="text-sm text-sothema-cyan hover:underline inline-flex items-center gap-1 mt-1">
              Open <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </Card>

      {/* Analysis History */}
      <Card>
        <h2 className="text-lg font-semibold text-sothema-dark mb-4">Analysis History</h2>
        {analyses.length === 0 ? (
          <div className="text-sm text-gray-400 py-4 flex items-center gap-2">
            <FileText className="h-4 w-4" /> No analyses yet. Trigger one above.
          </div>
        ) : (
          <div className="space-y-3">
            {analyses.map((a) => (
              <div
                key={a.id}
                onClick={() => a.status === 'Completed' ? navigate(`/compliance/${a.id}`) : undefined}
                className={`flex items-center justify-between p-3 rounded-lg border border-gray-100 ${a.status === 'Completed' ? 'hover:bg-gray-50 cursor-pointer' : ''}`}
              >
                <div className="flex items-center gap-4">
                  {a.status === 'Completed' && <ScoreBadge score={a.score} size="sm" />}
                  <div>
                    <Badge variant="status">{a.status}</Badge>
                    <p className="text-xs text-gray-400 mt-1">
                      {new Date(a.analyzedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </p>
                  </div>
                </div>
                {a.status === 'Processing' && (
                  <span className="text-xs text-blue-500 animate-pulse">Analyzing...</span>
                )}
                {a.summary && <p className="text-sm text-gray-500 max-w-md truncate hidden lg:block">{a.summary.slice(0, 120)}</p>}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Confirm Modal */}
      <Modal open={showModal} onClose={() => setShowModal(false)} title="Trigger Compliance Analysis">
        <p className="text-sm text-gray-600 mb-4">
          This will run a full compliance analysis on <strong>{doc.title}</strong>. The analysis typically takes 1-2 minutes.
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={() => setShowModal(false)}>Cancel</Button>
          <Button onClick={handleAnalyze} disabled={analyzing}>
            {analyzing ? 'Starting...' : 'Start Analysis'}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
