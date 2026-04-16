import type { AuditLog, PaginatedResponse } from '@/types';
import api, { USE_MOCK, paginateMock } from './api';
import { mockAuditLogs } from '@/mocks/auditLogs';

export async function getAuditLogs(page = 1, pageSize = 10, action?: string): Promise<PaginatedResponse<AuditLog>> {
  if (USE_MOCK) {
    await delay(300);
    const filtered = action ? mockAuditLogs.filter((l) => l.action === action) : mockAuditLogs;
    return paginateMock(filtered, page, pageSize);
  }
  const res = await api.get('/api/audit', { params: { page, pageSize, entityType: action } });
  return res.data;
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
