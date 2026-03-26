import type { ChatQueryResponse } from '@/types';
import api, { USE_MOCK } from './api';
import { getMockChatResponse } from '@/mocks/chat';

export async function queryCompliance(question: string): Promise<ChatQueryResponse> {
  if (USE_MOCK) {
    await delay(800 + Math.random() * 1200); // Simulate LLM thinking time
    return getMockChatResponse(question);
  }

  // Real mode: call the backend which proxies to the AI service RAG pipeline
  const res = await api.post('/api/search', { query: question, top_k: 10 });
  return {
    answer: res.data.answer || '',
    sources: (res.data.results || []).map((r: Record<string, unknown>) => ({
      documentId: r.document_id,
      documentTitle: r.document_title,
      segmentContent: r.segment_content,
      chunkIndex: r.chunk_index,
      relevanceScore: r.relevance_score,
    })),
  };
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
