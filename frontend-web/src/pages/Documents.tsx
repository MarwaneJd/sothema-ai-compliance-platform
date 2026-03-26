import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { SearchInput } from '@/components/ui/SearchInput';
import { Pagination } from '@/components/ui/Pagination';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { useDebounce } from '@/hooks/useDebounce';
import { getDocuments, searchDocuments } from '@/services/documentService';
import type { Document, PaginatedResponse } from '@/types';

export default function Documents() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedResponse<Document> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  useEffect(() => {
    setLoading(true);
    const fetch = debouncedSearch
      ? searchDocuments(debouncedSearch, page, 10)
      : getDocuments(page, 10);

    fetch.then(setData).finally(() => setLoading(false));
  }, [debouncedSearch, page]);

  const columns: Column<Document>[] = [
    {
      key: 'title',
      header: 'Title',
      render: (doc) => <span className="font-medium text-sothema-dark">{doc.title}</span>,
    },
    {
      key: 'fileType',
      header: 'Type',
      render: (doc) => <Badge>{doc.fileType.toUpperCase()}</Badge>,
      className: 'w-24',
    },
    {
      key: 'uploadedAt',
      header: 'Uploaded',
      render: (doc) => (
        <span className="text-gray-500">
          {new Date(doc.uploadedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
        </span>
      ),
      className: 'w-36',
    },
  ];

  return (
    <div className="space-y-8 animate-in mt-2 mb-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gradient pb-1">Documents</h1>
          <p className="text-slate-500 mt-1">Manage and upload your regulatory documents here.</p>
        </div>
      </div>

      <Card>
        <div className="mb-4">
          <SearchInput value={search} onChange={setSearch} placeholder="Search documents..." />
        </div>

        {loading ? (
          <LoadingSpinner />
        ) : !data || data.items.length === 0 ? (
          <EmptyState title="No documents found" description="Try adjusting your search query." />
        ) : (
          <>
            <DataTable columns={columns} data={data.items} onRowClick={(doc) => navigate(`/documents/${doc.id}`)} />
            <Pagination page={data.page} totalPages={data.totalPages} onPageChange={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
