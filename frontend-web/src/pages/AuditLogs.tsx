import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Pagination } from '@/components/ui/Pagination';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { Badge } from '@/components/ui/Badge';
import { getAuditLogs } from '@/services/auditService';
import type { AuditLog, PaginatedResponse } from '@/types';

const actionFilters = ['All', 'DocumentIngested', 'AnalysisTriggered', 'AnalysisCompleted', 'AnalysisFailed', 'DocumentViewed', 'UserLoggedIn'];

export default function AuditLogs() {
  const [action, setAction] = useState('All');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedResponse<AuditLog> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setPage(1);
  }, [action]);

  useEffect(() => {
    setLoading(true);
    const filter = action === 'All' ? undefined : action;
    getAuditLogs(page, 10, filter).then(setData).finally(() => setLoading(false));
  }, [action, page]);

  const columns: Column<AuditLog>[] = [
    {
      key: 'timestamp',
      header: 'Time',
      render: (log) => (
        <span className="text-gray-500 text-xs">
          {new Date(log.timestamp).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
        </span>
      ),
      className: 'w-40',
    },
    {
      key: 'user',
      header: 'User',
      render: (log) => <span className="font-medium text-sothema-dark">{log.userName || log.userId}</span>,
      className: 'w-40',
    },
    {
      key: 'action',
      header: 'Action',
      render: (log) => <Badge>{formatAction(log.action)}</Badge>,
      className: 'w-40',
    },
    {
      key: 'entity',
      header: 'Entity',
      render: (log) => (
        <span className="text-gray-500">
          {log.entityType} <span className="text-gray-300">/ {log.entityId}</span>
        </span>
      ),
    },
    {
      key: 'details',
      header: 'Details',
      render: (log) => <span className="text-gray-400 text-xs">{log.details || '—'}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-sothema-dark">Audit Logs</h1>

      <Card>
        {/* Filter */}
        <div className="mb-4">
          <select
            value={action}
            onChange={(e) => setAction(e.target.value)}
            className="px-3 py-2 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-sothema-cyan/50"
          >
            {actionFilters.map((f) => (
              <option key={f} value={f}>{f === 'All' ? 'All Actions' : formatAction(f)}</option>
            ))}
          </select>
        </div>

        {loading ? (
          <LoadingSpinner />
        ) : !data || data.items.length === 0 ? (
          <EmptyState title="No audit logs found" />
        ) : (
          <>
            <DataTable columns={columns} data={data.items} />
            <Pagination page={data.page} totalPages={data.totalPages} onPageChange={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}

function formatAction(action: string): string {
  return action.replace(/([A-Z])/g, ' $1').trim();
}
