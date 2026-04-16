import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import Markdown from 'react-markdown';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ScoreBadge, getScoreLabel } from '@/components/ui/ScoreBadge';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { CategoryBreakdownChart } from '@/components/charts/CategoryBreakdownChart';
import { getAnalysis } from '@/services/complianceService';
import type { ComplianceAnalysis, CategoryScore } from '@/types';

export default function ComplianceDetail() {
  const { analysisId } = useParams<{ analysisId: string }>();
  const [analysis, setAnalysis] = useState<ComplianceAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!analysisId) return;
    getAnalysis(analysisId).then(setAnalysis).finally(() => setLoading(false));
  }, [analysisId]);

  if (loading) return <LoadingSpinner />;
  if (!analysis) return <div className="text-center py-12 text-gray-500">Analysis not found.</div>;

  const hasDetails = analysis.details?.documentation && analysis.details?.regulatory
    && analysis.details?.quality && analysis.details?.traceability;

  const categories = hasDetails
    ? [
        { name: 'Documentation', data: analysis.details!.documentation },
        { name: 'Regulatory', data: analysis.details!.regulatory },
        { name: 'Quality', data: analysis.details!.quality },
        { name: 'Traceability', data: analysis.details!.traceability },
      ]
    : [];

  return (
    <div className="space-y-6">
      <Link to="/compliance" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-sothema-cyan">
        <ArrowLeft className="h-4 w-4" /> Back to Analyses
      </Link>

      {/* Header */}
      <Card>
        <div className="flex flex-col md:flex-row md:items-center gap-6">
          <ScoreBadge score={analysis.score} size="lg" />
          <div className="flex-1">
            <h1 className="text-xl font-bold text-sothema-dark">{analysis.documentTitle}</h1>
            <div className="flex items-center gap-3 mt-2">
              <Badge variant="status">{analysis.status}</Badge>
              <span className="text-sm text-gray-500">
                {new Date(analysis.analyzedAt).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
              </span>
            </div>
            <p className="text-sm font-medium mt-2" style={{ color: getScoreColor(analysis.score) }}>
              {getScoreLabel(analysis.score)} — {analysis.score}/100
            </p>
          </div>
        </div>
      </Card>

      {hasDetails && (
        <>
          {/* Category breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <h2 className="text-lg font-semibold text-sothema-dark mb-4">Category Breakdown</h2>
              <CategoryBreakdownChart details={analysis.details!} />
            </Card>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {categories.map((cat) => (
                <CategoryCard key={cat.name} name={cat.name} data={cat.data} />
              ))}
            </div>
          </div>
        </>
      )}

      {/* Summary */}
      {analysis.summary && (
        <Card>
          <h2 className="text-lg font-semibold text-sothema-dark mb-3">AI Summary</h2>
          <div className="text-sm text-gray-600 leading-relaxed prose prose-sm max-w-none">
            <Markdown>{analysis.summary}</Markdown>
          </div>
        </Card>
      )}
    </div>
  );
}

function CategoryCard({ name, data }: { name: string; data: CategoryScore }) {
  const pct = (data.score / data.max) * 100;
  return (
    <Card className="!p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-sothema-dark">{name}</h3>
        <span className="text-sm font-bold" style={{ color: getScoreColor((data.score / data.max) * 100) }}>
          {data.score}/{data.max}
        </span>
      </div>
      <div className="w-full h-2 bg-gray-100 rounded-full mb-3">
        <div
          className="h-2 rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: getScoreColor(pct) }}
        />
      </div>
      <ul className="space-y-1">
        {data.findings.map((f, i) => (
          <li key={i} className="text-xs text-gray-500 flex items-start gap-1.5">
            <span className="w-1 h-1 rounded-full bg-gray-300 mt-1.5 flex-shrink-0" />
            {f}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function getScoreColor(score: number): string {
  if (score >= 80) return '#16a34a';
  if (score >= 60) return '#eab308';
  if (score >= 40) return '#f97316';
  return '#dc2626';
}
