import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { SearchInput } from '@/components/ui/SearchInput';
import { Pagination } from '@/components/ui/Pagination';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { useDebounce } from '@/hooks/useDebounce';
import { deleteDocument, getDocuments, searchDocuments } from '@/services/documentService';
import type { Document, PaginatedResponse } from '@/types';

export default function Documents() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedResponse<Document> | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Document | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchDocs = () => {
    setLoading(true);
    const fetch = debouncedSearch
      ? searchDocuments(debouncedSearch, page, 10)
      : getDocuments(page, 10);
    fetch.then(setData).finally(() => setLoading(false));
  };

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch]);

  useEffect(() => {
    fetchDocs();
  }, [debouncedSearch, page]);

  const handleConfirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await deleteDocument(pendingDelete.id);
      setActionMsg({ kind: 'success', text: `"${pendingDelete.title}" deleted from platform.` });
      setPendingDelete(null);
      fetchDocs();
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : typeof err === 'object' && err !== null && 'message' in err
            ? String((err as { message: unknown }).message)
            : 'Delete failed';
      setActionMsg({ kind: 'error', text: msg });
    } finally {
      setDeleting(false);
    }
  };

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
    {
      key: 'actions',
      header: '',
      render: (doc) => (
        <button
          type="button"
          // Stop propagation so the row's onRowClick (navigate to detail)
          // doesn't fire when the user clicks the trash icon.
          onClick={(e) => {
            e.stopPropagation();
            setPendingDelete(doc);
          }}
          className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
          aria-label={`Delete ${doc.title}`}
          title="Delete document"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      ),
      className: 'w-12 text-right',
    },
  ];

  return (
    <div className="space-y-8 animate-in mt-2 mb-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gradient pb-1">Documents</h1>
          <p className="text-slate-500 mt-1">Manage your regulatory documents here.</p>
        </div>
      </div>

      {actionMsg && (
        <div
          className={`text-sm px-4 py-2 rounded-lg ${
            actionMsg.kind === 'error' ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-700'
          }`}
        >
          {actionMsg.text}
        </div>
      )}

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

      <Modal
        open={pendingDelete !== null}
        onClose={() => (deleting ? null : setPendingDelete(null))}
        title="Delete document?"
      >
        <p className="text-sm text-gray-600 mb-2">
          You are about to permanently delete{' '}
          <span className="font-medium text-sothema-dark">{pendingDelete?.title}</span>.
        </p>
        <p className="text-sm text-gray-500 mb-6">
          This removes the document, all its indexed text segments, and the associated vectors from
          the search index. This action cannot be undone.
        </p>
        <div className="flex items-center justify-end gap-3">
          <Button variant="ghost" onClick={() => setPendingDelete(null)} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleConfirmDelete} disabled={deleting}>
            {deleting ? 'Deleting...' : 'Delete'}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
