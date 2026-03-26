export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: ChatSource[];
}

export interface ChatSource {
  documentId: string;
  documentTitle: string;
  segmentContent: string;
  chunkIndex: number;
  relevanceScore: number;
}

export interface ChatQueryResponse {
  answer: string;
  sources: ChatSource[];
}
