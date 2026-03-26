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
  return res.data;
}

export async function triggerAnalysis(documentId: string): Promise<{ jobId: string; status: string }> {
  if (USE_MOCK) {
    await delay(500);
    return { jobId: `ca-mock-${Date.now()}`, status: 'Pending' };
  }
  const res = await api.post('/api/compliance/analyze', { documentId });
  return res.data;
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
