export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: ChatSource[];
  /** When false, the assistant message represents a sources-only retrieval (no LLM). */
  hasAnswer?: boolean;
  /** Set on Deep Analysis (agentic) responses — drives the groundedness badge + low-confidence banner. */
  deepAnalysis?: DeepAnalysisMeta;
}

export interface ChatSource {
  documentId: string;
  documentTitle: string;
  segmentContent: string;
  chunkIndex: number;
  relevanceScore: number;
}

export interface ChatCitation {
  sourceIndex: number;
  documentId: string;
  documentTitle: string;
  chunkIndex: number;
}

export interface DeepAnalysisMeta {
  groundednessScore: number;
  lowConfidence: boolean;
  iterations: number;
  llmCalls: number;
  elapsedMs: number;
  citations: ChatCitation[];
  subQueries: string[];
}

export interface ChatQueryResponse {
  answer: string;
  sources: ChatSource[];
  deepAnalysis?: DeepAnalysisMeta;
}
