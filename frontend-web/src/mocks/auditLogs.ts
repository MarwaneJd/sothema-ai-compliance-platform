import type { AuditLog } from '@/types';

export const mockAuditLogs: AuditLog[] = [
  { id: 'al-001', userId: 'u-002', userName: 'Youssef El Fassi', action: 'DocumentIngested', entityType: 'Document', entityId: 'doc-001', timestamp: '2025-02-20T09:30:00Z', details: 'Ingested SOP-QC-001, 15 segments created' },
  { id: 'al-002', userId: 'u-002', userName: 'Youssef El Fassi', action: 'AnalysisTriggered', entityType: 'ComplianceAnalysis', entityId: 'ca-001', timestamp: '2025-02-20T09:35:00Z', details: 'Analysis started for SOP-QC-001' },
  { id: 'al-003', userId: 'u-002', userName: 'Youssef El Fassi', action: 'AnalysisCompleted', entityType: 'ComplianceAnalysis', entityId: 'ca-001', timestamp: '2025-02-20T09:42:00Z', details: 'Score: 87/100' },
  { id: 'al-004', userId: 'u-001', userName: 'Amina Benali', action: 'UserLoggedIn', entityType: 'User', entityId: 'u-001', timestamp: '2025-02-21T08:00:00Z', details: null },
  { id: 'al-005', userId: 'u-001', userName: 'Amina Benali', action: 'DocumentViewed', entityType: 'Document', entityId: 'doc-001', timestamp: '2025-02-21T08:05:00Z', details: null },
  { id: 'al-006', userId: 'u-002', userName: 'Youssef El Fassi', action: 'DocumentIngested', entityType: 'Document', entityId: 'doc-002', timestamp: '2025-02-22T10:00:00Z', details: 'Ingested SOP-QC-002, 12 segments created' },
  { id: 'al-007', userId: 'u-002', userName: 'Youssef El Fassi', action: 'AnalysisTriggered', entityType: 'ComplianceAnalysis', entityId: 'ca-002', timestamp: '2025-02-22T10:05:00Z', details: 'Analysis started for SOP-QC-002' },
  { id: 'al-008', userId: 'u-002', userName: 'Youssef El Fassi', action: 'AnalysisCompleted', entityType: 'ComplianceAnalysis', entityId: 'ca-002', timestamp: '2025-02-22T10:15:00Z', details: 'Score: 72/100' },
  { id: 'al-009', userId: 'u-003', userName: 'Sara Tazi', action: 'UserLoggedIn', entityType: 'User', entityId: 'u-003', timestamp: '2025-02-23T14:00:00Z', details: null },
  { id: 'al-010', userId: 'u-003', userName: 'Sara Tazi', action: 'DocumentViewed', entityType: 'Document', entityId: 'doc-005', timestamp: '2025-02-23T14:10:00Z', details: null },
  { id: 'al-011', userId: 'u-002', userName: 'Youssef El Fassi', action: 'DocumentIngested', entityType: 'Document', entityId: 'doc-005', timestamp: '2025-02-25T09:00:00Z', details: 'Ingested REG-MA-001, 28 segments created' },
  { id: 'al-012', userId: 'u-002', userName: 'Youssef El Fassi', action: 'AnalysisTriggered', entityType: 'ComplianceAnalysis', entityId: 'ca-003', timestamp: '2025-02-25T09:05:00Z', details: 'Analysis started for REG-MA-001' },
  { id: 'al-013', userId: 'u-002', userName: 'Youssef El Fassi', action: 'AnalysisCompleted', entityType: 'ComplianceAnalysis', entityId: 'ca-003', timestamp: '2025-02-25T09:20:00Z', details: 'Score: 91/100' },
  { id: 'al-014', userId: 'u-001', userName: 'Amina Benali', action: 'DocumentViewed', entityType: 'Document', entityId: 'doc-008', timestamp: '2025-03-01T11:00:00Z', details: null },
  { id: 'al-015', userId: 'u-002', userName: 'Youssef El Fassi', action: 'DocumentIngested', entityType: 'Document', entityId: 'doc-008', timestamp: '2025-03-01T11:15:00Z', details: 'Ingested VAL-PR-001, 18 segments created' },
  { id: 'al-016', userId: 'u-002', userName: 'Youssef El Fassi', action: 'AnalysisTriggered', entityType: 'ComplianceAnalysis', entityId: 'ca-004', timestamp: '2025-03-01T11:20:00Z', details: 'Analysis started for VAL-PR-001' },
  { id: 'al-017', userId: 'u-002', userName: 'Youssef El Fassi', action: 'AnalysisCompleted', entityType: 'ComplianceAnalysis', entityId: 'ca-004', timestamp: '2025-03-01T11:35:00Z', details: 'Score: 65/100' },
  { id: 'al-018', userId: 'u-001', userName: 'Amina Benali', action: 'UserLoggedIn', entityType: 'User', entityId: 'u-001', timestamp: '2025-03-05T08:30:00Z', details: null },
  { id: 'al-019', userId: 'u-002', userName: 'Youssef El Fassi', action: 'AnalysisTriggered', entityType: 'ComplianceAnalysis', entityId: 'ca-006', timestamp: '2025-03-10T08:00:00Z', details: 'Analysis started for SOP-QC-003' },
  { id: 'al-020', userId: 'u-002', userName: 'Youssef El Fassi', action: 'AnalysisFailed', entityType: 'ComplianceAnalysis', entityId: 'ca-008', timestamp: '2025-03-08T12:00:00Z', details: 'Document extraction error — image-based PDF' },
];
