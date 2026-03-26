import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { Pagination } from '@/components/ui/Pagination';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { getAnalyses } from '@/services/complianceService';
import type { ComplianceAnalysis, AnalysisStatus, PaginatedResponse } from '@/types';

const statusTabs: (AnalysisStatus | 'All')[] = ['All', 'Completed', 'Processing', 'Pending', 'Failed'];

export default function ComplianceAnalyses() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<string>('All');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedResponse<ComplianceAnalysis> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setPage(1);
  }, [activeTab]);

  useEffect(() => {
    setLoading(true);
    const status = activeTab === 'All' ? undefined : activeTab;
    getAnalyses(page, 10, status).then(setData).finally(() => setLoading(false));
  }, [activeTab, page]);

  const columns: Column<ComplianceAnalysis>[] = [
    {
      key: 'document',
      header: 'Document',
      render: (a) => <span className="font-medium text-sothema-dark">{a.documentTitle}</span>,
    },
    {
      key: 'score',
      header: 'Score',
      render: (a) => a.status === 'Completed' ? <ScoreBadge score={a.score} size="sm" /> : <span className="text-gray-400">—</span>,
      className: 'w-24',
    },
    {
      key: 'status',
      header: 'Status',
      render: (a) => <Badge variant="status">{a.status}</Badge>,
      className: 'w-28',
    },
    {
      key: 'date',
      header: 'Analyzed',
      render: (a) => (
        <span className="text-gray-500">
          {new Date(a.analyzedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
        </span>
      ),
      className: 'w-36',
    },
  ];

  return (
    <div className="space-y-8 animate-in mt-2 mb-8">
      <div>
        <h1 className="text-3xl font-bold text-gradient pb-1">Compliance Analyses</h1>
        <p className="text-slate-500 mt-1">Review AI-generated compliance reports across all documents.</p>
      </div>

      <Card>
        {/* Status tabs */}
        <div className="flex gap-1 mb-4 border-b border-gray-200 -mx-6 -mt-6 px-6 pt-4">
          {statusTabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? 'border-sothema-primary text-sothema-primary'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {loading ? (
          <LoadingSpinner />
        ) : !data || data.items.length === 0 ? (
          <EmptyState title="No analyses found" description={`No ${activeTab !== 'All' ? activeTab.toLowerCase() : ''} analyses.`} />
        ) : (
          <>
            <DataTable columns={columns} data={data.items} onRowClick={(a) => navigate(`/compliance/${a.id}`)} />
            <Pagination page={data.page} totalPages={data.totalPages} onPageChange={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
