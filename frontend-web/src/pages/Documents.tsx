import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { SearchInput } from '@/components/ui/SearchInput';
import { Pagination } from '@/components/ui/Pagination';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { useDebounce } from '@/hooks/useDebounce';
import { getDocuments, searchDocuments, uploadDocument } from '@/services/documentService';
import type { Document, PaginatedResponse } from '@/types';

export default function Documents() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PaginatedResponse<Document> | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg('');
    try {
      const result = await uploadDocument(file);
      setUploadMsg(`"${result.title}" uploaded and indexed. Open it to trigger analysis.`);
      fetchDocs();
      // Navigate to the new document after a brief delay
      setTimeout(() => navigate(`/documents/${result.id}`), 1500);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : typeof err === 'object' && err !== null && 'message' in err
            ? String((err as { message: unknown }).message)
            : 'Upload failed';
      setUploadMsg(msg);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
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
  ];

  return (
    <div className="space-y-8 animate-in mt-2 mb-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gradient pb-1">Documents</h1>
          <p className="text-slate-500 mt-1">Manage and upload your regulatory documents here.</p>
        </div>
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.pptx,.txt,.md"
            className="hidden"
            onChange={handleUpload}
          />
          <Button onClick={() => fileInputRef.current?.click()} disabled={uploading} className="shadow-md">
            <Upload className="h-4 w-4 mr-2" />
            {uploading ? 'Uploading...' : 'Upload Document'}
          </Button>
        </div>
      </div>

      {uploadMsg && (
        <div className={`text-sm px-4 py-2 rounded-lg ${uploadMsg.includes('failed') ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-700'}`}>
          {uploadMsg}
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
    </div>
  );
}
