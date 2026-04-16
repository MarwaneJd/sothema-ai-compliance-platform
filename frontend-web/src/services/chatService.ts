import type { ChatQueryResponse } from '@/types';
import api, { USE_MOCK } from './api';
import { getMockChatResponse } from '@/mocks/chat';

export async function queryCompliance(question: string): Promise<ChatQueryResponse> {
  if (USE_MOCK) {
    await delay(800 + Math.random() * 1200); // Simulate LLM thinking time
    return getMockChatResponse(question);
  }

  // Real mode: call the backend which proxies to the AI service RAG pipeline
  const res = await api.post('/api/search', { query: question, topK: 10 });

  const results = res.data.results || [];
  const sources = results.map((r: Record<string, unknown>) => ({
    documentId: r.documentId || r.document_id,
    documentTitle: r.documentTitle || r.document_title,
    segmentContent: r.segmentContent || r.segment_content,
    chunkIndex: r.chunkIndex ?? r.chunk_index,
    relevanceScore: r.relevanceScore ?? r.relevance_score,
  }));

  // Use answer from backend if available, otherwise summarize from results
  let answer = res.data.answer || '';
  if (!answer && sources.length > 0) {
    answer = `Based on ${sources.length} relevant document segment(s) found:\n\n` +
      sources.slice(0, 3).map((s: { documentTitle: string; segmentContent: string }, i: number) =>
        `**${i + 1}. ${s.documentTitle}**\n${s.segmentContent.substring(0, 300)}${s.segmentContent.length > 300 ? '...' : ''}`
      ).join('\n\n');
  } else if (!answer) {
    answer = 'No relevant documents were found for your query. Please try rephrasing your question.';
  }

  return { answer, sources };
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
