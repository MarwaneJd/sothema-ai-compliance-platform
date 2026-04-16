import type { ComplianceAnalysis, PaginatedResponse } from '@/types';
import api, { USE_MOCK, paginateMock } from './api';
import { mockAnalyses } from '@/mocks/analyses';

export async function getAnalyses(page = 1, pageSize = 10, status?: string): Promise<PaginatedResponse<ComplianceAnalysis>> {
  if (USE_MOCK) {
    await delay(300);
    const filtered = status ? mockAnalyses.filter((a) => a.status === status) : mockAnalyses;
    return paginateMock(filtered, page, pageSize);
  }
  const res = await api.get('/api/compliance', { params: { page, pageSize, status } });
  return res.data;
}

export async function getAnalysis(id: string): Promise<ComplianceAnalysis> {
  if (USE_MOCK) {
    await delay(200);
    const analysis = mockAnalyses.find((a) => a.id === id);
    if (!analysis) throw { message: 'Analysis not found', status: 404 };
    return analysis;
  }
  const res = await api.get(`/api/compliance/${id}`);
  const data = res.data;

  data.details = parseDetails(data.details);
  return data;
}

export async function getAnalysesByDocument(documentId: string): Promise<ComplianceAnalysis[]> {
  if (USE_MOCK) {
    await delay(200);
    return mockAnalyses.filter((a) => a.documentId === documentId);
  }
  const res = await api.get(`/api/compliance/document/${documentId}`);
  const items = Array.isArray(res.data) ? res.data : res.data.items ?? [];
  return items.map((d: ComplianceAnalysis) => {
    d.details = parseDetails(d.details);
    return d;
  });
}

export async function triggerAnalysis(documentId: string): Promise<{ jobId: string; status: string }> {
  if (USE_MOCK) {
    await delay(500);
    return { jobId: `ca-mock-${Date.now()}`, status: 'Pending' };
  }
  const res = await api.post('/api/compliance/analyze', { documentId });
  return res.data;
}

function parseDetails(raw: unknown): ComplianceAnalysis['details'] {
  let obj = raw;
  if (typeof obj === 'string' && obj) {
    try { obj = JSON.parse(obj); } catch { return null; }
  }
  if (!obj || typeof obj !== 'object') return null;
  // API returns { categories: { documentation, ... } } — unwrap to match frontend type
  const record = obj as Record<string, unknown>;
  if (record.categories && typeof record.categories === 'object') {
    return record.categories as ComplianceAnalysis['details'];
  }
  return obj as ComplianceAnalysis['details'];
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
