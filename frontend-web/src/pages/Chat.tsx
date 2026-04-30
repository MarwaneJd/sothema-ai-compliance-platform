import { useState, useRef, useEffect } from 'react';
import { Send, Bot, FileText, ChevronDown, ChevronUp, Sparkles, Search } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
import { queryCompliance } from '@/services/chatService';
import { suggestedQuestions } from '@/mocks/chat';
import type { ChatMessage, ChatSource } from '@/types';

type SearchMode = 'ai' | 'sources';

const MODE_STORAGE_KEY = 'sothema:chat-mode';

export default function Chat() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hello! I'm your AI Compliance Assistant. I can answer questions about pharmaceutical regulations, GMP requirements, ICH guidelines, and your organization's compliance documents.\n\nTry asking me about a specific topic or choose one of the suggested questions below.",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<SearchMode>(() => {
    const stored = localStorage.getItem(MODE_STORAGE_KEY);
    return stored === 'sources' ? 'sources' : 'ai';
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    localStorage.setItem(MODE_STORAGE_KEY, mode);
  }, [mode]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (question?: string) => {
    const q = question || input.trim();
    if (!q || loading) return;

    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: q,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await queryCompliance(q, { includeAnswer: mode === 'ai' });
      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now()}-reply`,
        role: 'assistant',
        content: response.answer,
        timestamp: new Date().toISOString(),
        sources: response.sources,
        hasAnswer: mode === 'ai',
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch {
      const errorMessage: ChatMessage = {
        id: `msg-${Date.now()}-error`,
        role: 'assistant',
        content: 'Sorry, I encountered an error while processing your question. Please try again.',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const initials = user?.displayName
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'U';

  const showSuggestions = messages.length <= 1 && !loading;

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] animate-in mt-2 mb-4">
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-gradient pb-1">Compliance Assistant</h1>
          <p className="text-sm text-slate-500 mt-1">Ask questions about regulations, GMP, and compliance documents</p>
        </div>
        <ModeToggle mode={mode} onChange={setMode} />
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto rounded-lg bg-white border border-gray-100 shadow-sm">
        <div className="p-4 space-y-4">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} userInitials={initials} />
          ))}

          {loading && (
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-sothema-navy text-white flex items-center justify-center flex-shrink-0">
                <Bot className="h-4 w-4" />
              </div>
              <div className="bg-gray-50 rounded-lg px-4 py-3">
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-sothema-cyan rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-sothema-cyan rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-sothema-cyan rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                  {mode === 'ai' ? 'Searching compliance documents…' : 'Retrieving ranked sources…'}
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Suggested questions */}
      {showSuggestions && (
        <div className="mt-3 flex flex-wrap gap-2">
          {suggestedQuestions.map((q) => (
            <button
              key={q}
              onClick={() => handleSend(q)}
              className="px-3 py-1.5 text-xs rounded-full border border-sothema-cyan/30 text-sothema-cyan hover:bg-sothema-cyan-light transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input area */}
      <div className="mt-4 flex gap-3 items-end">
        <div className="flex-1 relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              mode === 'ai'
                ? 'Ask about compliance regulations, GMP, ICH guidelines...'
                : 'Search keywords or describe what you’re looking for...'
            }
            rows={1}
            className="w-full resize-none rounded-xl border border-slate-200 shadow-sm px-4 py-3 pr-12 text-sm focus:outline-none focus:ring-2 focus:ring-sothema-primary/20 focus:border-sothema-primary transition-all"
            style={{ minHeight: '48px', maxHeight: '120px' }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = '48px';
              target.style.height = `${Math.min(target.scrollHeight, 120)}px`;
            }}
          />
        </div>
        <Button onClick={() => handleSend()} disabled={!input.trim() || loading} className="h-12 w-12 !p-0 rounded-xl shadow-md">
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function MessageBubble({ message, userInitials }: { message: ChatMessage; userInitials: string }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-white text-xs font-semibold ${
          isUser ? 'bg-sothema-cyan' : 'bg-sothema-navy'
        }`}
      >
        {isUser ? userInitials : <Bot className="h-4 w-4" />}
      </div>

      <div className={`max-w-[85%] ${isUser ? 'text-right' : 'w-full'}`}>
        {/* User bubble OR assistant in AI mode renders the answer text */}
        {(isUser || message.hasAnswer !== false) && message.content && (
          <div
            className={`rounded-lg px-4 py-3 text-sm leading-relaxed ${
              isUser ? 'bg-sothema-cyan text-white inline-block' : 'bg-gray-50 text-sothema-dark'
            }`}
          >
            <FormattedContent content={message.content} isUser={isUser} />
          </div>
        )}

        {/* Sources-only mode → big polished ranked list */}
        {!isUser && message.hasAnswer === false && (
          <RetrievalResults sources={message.sources ?? []} />
        )}

        {/* AI mode → small accordion below the answer */}
        {!isUser && message.hasAnswer !== false && message.sources && message.sources.length > 0 && (
          <SourcesAccordion sources={message.sources} />
        )}

        <p className={`text-[10px] text-gray-400 mt-1 ${isUser ? 'text-right' : ''}`}>
          {new Date(message.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    </div>
  );
}

function ModeToggle({ mode, onChange }: { mode: SearchMode; onChange: (m: SearchMode) => void }) {
  return (
    <div className="inline-flex items-center bg-slate-100 rounded-full p-1 shadow-inner">
      <button
        type="button"
        onClick={() => onChange('ai')}
        className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all ${
          mode === 'ai'
            ? 'bg-white text-sothema-primary shadow-sm'
            : 'text-slate-500 hover:text-slate-700'
        }`}
        aria-pressed={mode === 'ai'}
        title="AI-generated answer with citations (uses LLM)"
      >
        <Sparkles className="h-3.5 w-3.5" />
        AI Answer
      </button>
      <button
        type="button"
        onClick={() => onChange('sources')}
        className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all ${
          mode === 'sources'
            ? 'bg-white text-sothema-primary shadow-sm'
            : 'text-slate-500 hover:text-slate-700'
        }`}
        aria-pressed={mode === 'sources'}
        title="Ranked excerpts only — fast, no LLM, fully transparent"
      >
        <Search className="h-3.5 w-3.5" />
        Sources only
      </button>
    </div>
  );
}

function RetrievalResults({ sources }: { sources: ChatSource[] }) {
  if (sources.length === 0) {
    return (
      <div className="rounded-lg bg-slate-50 border border-slate-200 px-4 py-6 text-center">
        <FileText className="h-6 w-6 mx-auto text-slate-300 mb-2" />
        <p className="text-sm text-slate-500">No matching excerpts found.</p>
        <p className="text-xs text-slate-400 mt-1">Try different keywords or upload more documents.</p>
      </div>
    );
  }

  const maxScore = Math.max(...sources.map((s) => s.relevanceScore), 0.0001);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-slate-500 px-1">
        <span className="font-semibold uppercase tracking-wide">
          {sources.length} ranked excerpt{sources.length !== 1 ? 's' : ''}
        </span>
        <span className="text-[10px]">RRF score · vector + BM25 fusion</span>
      </div>
      {sources.map((source, i) => (
        <RetrievalCard
          key={`${source.documentId}-${source.chunkIndex}-${i}`}
          rank={i + 1}
          source={source}
          relativeScore={source.relevanceScore / maxScore}
        />
      ))}
    </div>
  );
}

function RetrievalCard({
  rank,
  source,
  relativeScore,
}: {
  rank: number;
  source: ChatSource;
  relativeScore: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const preview = source.segmentContent.length > 240 && !expanded
    ? source.segmentContent.slice(0, 240) + '…'
    : source.segmentContent;

  return (
    <Card className="!p-0 !shadow-none border border-slate-200 hover:border-sothema-cyan/40 hover:shadow-sm transition-all overflow-hidden">
      <div className="flex">
        <div className="flex flex-col items-center justify-center bg-slate-50 border-r border-slate-200 px-3 py-3 min-w-[56px]">
          <span className="text-xs text-slate-400 font-mono">#{rank}</span>
          <span className="text-base font-bold text-sothema-primary mt-0.5">
            {(source.relevanceScore * 100).toFixed(1)}
          </span>
          <span className="text-[9px] text-slate-400 uppercase tracking-wider">score</span>
        </div>

        <div className="flex-1 p-3 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1.5">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-sothema-dark truncate" title={source.documentTitle}>
                {source.documentTitle}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">Chunk {source.chunkIndex}</p>
            </div>
          </div>

          {/* Relevance bar */}
          <div className="h-1 bg-slate-100 rounded-full overflow-hidden mb-2">
            <div
              className="h-full bg-gradient-to-r from-sothema-cyan to-sothema-primary transition-all"
              style={{ width: `${Math.max(relativeScore * 100, 4)}%` }}
            />
          </div>

          <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap">{preview}</p>

          {source.segmentContent.length > 240 && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="text-[11px] text-sothema-cyan hover:text-sothema-navy mt-1.5 font-medium"
            >
              {expanded ? 'Show less' : 'Show full excerpt'}
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}

function FormattedContent({ content, isUser }: { content: string; isUser: boolean }) {
  // Simple markdown-like rendering for assistant messages
  if (isUser) return <>{content}</>;

  const lines = content.split('\n');
  return (
    <div className="space-y-2">
      {lines.map((line, i) => {
        if (!line.trim()) return <br key={i} />;

        // Headers
        if (line.startsWith('**') && line.endsWith('**')) {
          return <p key={i} className="font-semibold">{line.replace(/\*\*/g, '')}</p>;
        }

        // Bold within text
        const parts = line.split(/(\*\*.*?\*\*)/g);
        const rendered = parts.map((part, j) => {
          if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={j}>{part.slice(2, -2)}</strong>;
          }
          return <span key={j}>{part}</span>;
        });

        // List items
        if (line.match(/^\d+\.\s/) || line.startsWith('- ')) {
          return <p key={i} className="ml-4">{rendered}</p>;
        }

        // Table rows
        if (line.startsWith('|')) {
          return <p key={i} className="font-mono text-xs">{line}</p>;
        }

        return <p key={i}>{rendered}</p>;
      })}
    </div>
  );
}

function SourcesAccordion({ sources }: { sources: ChatSource[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-sothema-cyan hover:text-sothema-navy transition-colors"
      >
        <FileText className="h-3 w-3" />
        {sources.length} source{sources.length !== 1 ? 's' : ''} referenced
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {sources.map((source, i) => (
            <Card key={i} className="!p-3 !shadow-none border border-gray-200">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-sothema-dark truncate">{source.documentTitle}</p>
                  <p className="text-[11px] text-gray-400 mt-0.5">Chunk {source.chunkIndex} — Relevance: {(source.relevanceScore * 100).toFixed(0)}%</p>
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-1.5 line-clamp-2">{source.segmentContent}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
