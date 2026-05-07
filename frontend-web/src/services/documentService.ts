import type { Document, PaginatedResponse } from '@/types';
import api, { USE_MOCK, paginateMock } from './api';
import { mockDocuments } from '@/mocks/documents';

export async function getDocuments(page = 1, pageSize = 10): Promise<PaginatedResponse<Document>> {
  if (USE_MOCK) {
    await delay(300);
    return paginateMock(mockDocuments, page, pageSize);
  }
  const res = await api.get('/api/documents', { params: { page, pageSize } });
  return res.data;
}

export async function getDocument(id: string): Promise<Document> {
  if (USE_MOCK) {
    await delay(200);
    const doc = mockDocuments.find((d) => d.id === id);
    if (!doc) throw { message: 'Document not found', status: 404 };
    return doc;
  }
  const res = await api.get(`/api/documents/${id}`);
  return res.data;
}

export async function searchDocuments(query: string, page = 1, pageSize = 10): Promise<PaginatedResponse<Document>> {
  if (USE_MOCK) {
    await delay(300);
    const q = query.toLowerCase();
    const filtered = mockDocuments.filter((d) => d.title.toLowerCase().includes(q));
    return paginateMock(filtered, page, pageSize);
  }
  const res = await api.get('/api/documents/search', { params: { q: query, page, pageSize } });
  // Backend search returns an array of results, wrap in pagination if needed
  const data = res.data;
  if (Array.isArray(data)) {
    return paginateMock(data, page, pageSize);
  }
  return data;
}

export async function uploadDocument(file: File): Promise<{ id: string; title: string; fileType: string; ingestionJob: { jobId: string; status: string } }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await api.post('/api/dev/ingest', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

// Cascades on the backend: AI service drops vectors/BM25 entries,
// TextSegments are deleted, Document row removed. Returns void on
// success (HTTP 204), throws on failure.
export async function deleteDocument(id: string): Promise<void> {
  if (USE_MOCK) {
    await delay(200);
    const idx = mockDocuments.findIndex((d) => d.id === id);
    if (idx === -1) throw { message: 'Document not found', status: 404 };
    mockDocuments.splice(idx, 1);
    return;
  }
  await api.delete(`/api/documents/${id}`);
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
