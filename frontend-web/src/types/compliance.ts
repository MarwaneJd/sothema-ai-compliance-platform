export type AnalysisStatus = 'Pending' | 'Processing' | 'Completed' | 'Failed';

export interface CategoryScore {
  score: number;
  max: number;
  findings: string[];
}

export interface ComplianceDetails {
  documentation: CategoryScore;
  regulatory: CategoryScore;
  quality: CategoryScore;
  traceability: CategoryScore;
}

export interface ComplianceAnalysis {
  id: string;
  documentId: string;
  score: number;
  summary: string;
  details: ComplianceDetails | null;
  status: AnalysisStatus;
  analyzedAt: string;
  documentTitle?: string;
}
