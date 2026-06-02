import type { ChatCitation, ChatQueryResponse, ChatSource, DeepAnalysisMeta } from '@/types';
import api, { USE_MOCK } from './api';
import { getMockChatResponse } from '@/mocks/chat';

export async function queryCompliance(
  question: string,
  options?: { includeAnswer?: boolean },
): Promise<ChatQueryResponse> {
  const includeAnswer = options?.includeAnswer ?? true;

  if (USE_MOCK) {
    await delay(800 + Math.random() * 1200);
    const mock = getMockChatResponse(question);
    return includeAnswer ? mock : { answer: '', sources: mock.sources };
  }

  const res = await api.post('/api/search', {
    query: question,
    topK: 6, // Fast mode: tighter context (Deep Analysis keeps 10)
    includeAnswer,
  });

  const sources = mapSources(res.data.results || []);

  if (!includeAnswer) {
    return { answer: '', sources };
  }

  let answer = res.data.answer || '';
  if (!answer && sources.length > 0) {
    answer = `Based on ${sources.length} relevant document segment(s) found:\n\n` +
      sources.slice(0, 3).map((s, i) =>
        `**${i + 1}. ${s.documentTitle}**\n${s.segmentContent.substring(0, 300)}${s.segmentContent.length > 300 ? '...' : ''}`
      ).join('\n\n');
  } else if (!answer) {
    answer = 'No relevant documents were found for your query. Please try rephrasing your question.';
  }

  return { answer, sources };
}

/**
 * Deep Analysis — calls the agentic RAG endpoint. Higher latency (5–15s) but
 * does iterative retrieval, reflection, generation, and groundedness verification.
 */
export async function queryDeepAnalysis(
  question: string,
): Promise<ChatQueryResponse> {
  if (USE_MOCK) {
    await delay(2500 + Math.random() * 2000);
    const mock = getMockChatResponse(question);
    return {
      answer: mock.answer,
      sources: mock.sources,
      deepAnalysis: {
        groundednessScore: 0.95,
        lowConfidence: false,
        iterations: 0,
        llmCalls: 4,
        elapsedMs: 4500,
        citations: [],
        subQueries: [question],
      },
    };
  }

  const res = await api.post('/api/search/agentic', {
    query: question,
    topK: 10,
    maxIterations: 2,
  });

  const sources = mapSources(res.data.results || []);
  const rawCitations: unknown[] = res.data.citations || [];
  const citations: ChatCitation[] = rawCitations.map((c) => {
    const r = c as Record<string, unknown>;
    return {
      sourceIndex: (r.sourceIndex ?? r.source_index) as number,
      documentId: String(r.documentId ?? r.document_id ?? ''),
      documentTitle: (r.documentTitle ?? r.document_title) as string,
      chunkIndex: (r.chunkIndex ?? r.chunk_index) as number,
    };
  });

  const deepAnalysis: DeepAnalysisMeta = {
    groundednessScore: Number(res.data.groundednessScore ?? res.data.groundedness_score ?? 0),
    lowConfidence: Boolean(res.data.lowConfidence ?? res.data.low_confidence ?? false),
    iterations: Number(res.data.iterations ?? 0),
    llmCalls: Number(res.data.llmCalls ?? res.data.llm_calls ?? 0),
    elapsedMs: Number(res.data.elapsedMs ?? res.data.elapsed_ms ?? 0),
    citations,
    subQueries: (res.data.subQueries ?? res.data.sub_queries ?? []) as string[],
  };

  return {
    answer: res.data.answer || '',
    sources,
    deepAnalysis,
  };
}

function mapSources(results: unknown[]): ChatSource[] {
  return results.map((raw) => {
    const r = raw as Record<string, unknown>;
    return {
      documentId: String(r.documentId ?? r.document_id ?? ''),
      documentTitle: (r.documentTitle ?? r.document_title) as string,
      segmentContent: (r.segmentContent ?? r.segment_content) as string,
      chunkIndex: (r.chunkIndex ?? r.chunk_index) as number,
      relevanceScore: (r.relevanceScore ?? r.relevance_score) as number,
    };
  });
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
