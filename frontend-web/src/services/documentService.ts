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
  return res.data;
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
