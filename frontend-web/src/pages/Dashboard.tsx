import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, ShieldCheck, TrendingUp, Clock } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { ScoreDistributionChart } from '@/components/charts/ScoreDistributionChart';
import { getDocuments } from '@/services/documentService';
import { getAnalyses } from '@/services/complianceService';
import { getAuditLogs } from '@/services/auditService';
import type { ComplianceAnalysis, AuditLog } from '@/types';

interface DashboardStats {
  totalDocuments: number;
  totalAnalyses: number;
  avgScore: number;
  inProgress: number;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentActivity, setRecentActivity] = useState<AuditLog[]>([]);
  const [recentAnalyses, setRecentAnalyses] = useState<ComplianceAnalysis[]>([]);
  const [allAnalyses, setAllAnalyses] = useState<ComplianceAnalysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [docsPage, analysesPage, auditPage, recentPage] = await Promise.all([
          getDocuments(1, 1),
          getAnalyses(1, 100),
          getAuditLogs(1, 6),
          getAnalyses(1, 5, 'Completed'),
        ]);

        if (cancelled) return;

        const analyses = analysesPage.items;
        const completed = analyses.filter((a) => a.status === 'Completed');
        const avgScore = completed.length
          ? Math.round(completed.reduce((s, a) => s + a.score, 0) / completed.length)
          : 0;
        const inProgress = analyses.filter(
          (a) => a.status === 'Pending' || a.status === 'Processing'
        ).length;

        setStats({
          totalDocuments: docsPage.totalCount,
          totalAnalyses: analysesPage.totalCount,
          avgScore,
          inProgress,
        });
        setAllAnalyses(analyses);
        setRecentActivity(auditPage.items);
        setRecentAnalyses(recentPage.items);
      } catch (err) {
        if (!cancelled) setError('Failed to load dashboard data.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="space-y-8 animate-in mt-2">
        <div>
          <h1 className="text-3xl font-bold text-gradient pb-1">Dashboard</h1>
          <p className="text-slate-500 mt-1">Welcome back. Here is your compliance overview.</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <div className="h-20 bg-slate-100 rounded animate-pulse" />
            </Card>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2"><div className="h-48 bg-slate-100 rounded animate-pulse" /></Card>
          <Card><div className="h-48 bg-slate-100 rounded animate-pulse" /></Card>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-2">
        <h1 className="text-3xl font-bold text-gradient pb-1 mb-4">Dashboard</h1>
        <Card><p className="text-red-500 text-sm">{error}</p></Card>
      </div>
    );
  }

  const statCards = [
    { label: 'Total Documents', value: stats!.totalDocuments, icon: FileText, color: 'text-sothema-cyan' },
    { label: 'Analyses Run', value: stats!.totalAnalyses, icon: ShieldCheck, color: 'text-sothema-navy' },
    { label: 'Average Score', value: stats!.avgScore, icon: TrendingUp, color: 'text-score-high' },
    { label: 'In Progress', value: stats!.inProgress, icon: Clock, color: 'text-score-medium' },
  ];

  return (
    <div className="space-y-8 animate-in mt-2 mb-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gradient pb-1">Dashboard</h1>
          <p className="text-slate-500 mt-1">Welcome back. Here is your compliance overview.</p>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card key={stat.label} className="relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-4 opacity-5 transform group-hover:scale-110 transition-transform duration-500">
                <Icon className={`h-24 w-24 ${stat.color}`} />
              </div>
              <div className="flex flex-col relative z-10">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-xl bg-slate-50 border border-slate-100 ${stat.color} shadow-sm group-hover:bg-white transition-colors`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <p className="text-sm font-medium text-slate-500">{stat.label}</p>
                </div>
                <p className="text-3xl font-bold text-sothema-dark mt-4">{stat.value}</p>
              </div>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Score Distribution */}
        <Card className="lg:col-span-2">
          <h2 className="text-lg font-semibold text-sothema-dark mb-4">Score Distribution</h2>
          {allAnalyses.length > 0 ? (
            <ScoreDistributionChart analyses={allAnalyses} />
          ) : (
            <p className="text-sm text-slate-400 py-8 text-center">No analyses yet.</p>
          )}
        </Card>

        {/* Recent Activity */}
        <Card>
          <h2 className="text-lg font-semibold text-sothema-dark mb-4">Recent Activity</h2>
          {recentActivity.length > 0 ? (
            <div className="space-y-3">
              {recentActivity.map((log) => (
                <div key={log.id} className="flex items-start gap-3 text-sm">
                  <div className="w-2 h-2 rounded-full bg-sothema-cyan mt-1.5 flex-shrink-0" />
                  <div>
                    <p className="text-sothema-dark">
                      <span className="font-medium">{log.userName ?? 'User'}</span>{' '}
                      <span className="text-gray-500">{formatAction(log.action)}</span>
                    </p>
                    <p className="text-xs text-gray-400">{formatDate(log.timestamp)}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400 py-8 text-center">No activity yet.</p>
          )}
        </Card>
      </div>

      {/* Recent Analyses */}
      <Card>
        <h2 className="text-lg font-semibold text-sothema-dark mb-4">Recent Analyses</h2>
        {recentAnalyses.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Document</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Score</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Status</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Date</th>
                </tr>
              </thead>
              <tbody>
                {recentAnalyses.map((a) => (
                  <tr
                    key={a.id}
                    onClick={() => navigate(`/compliance/${a.id}`)}
                    className="border-b border-gray-100 cursor-pointer hover:bg-gray-50"
                  >
                    <td className="py-3 px-4 text-sothema-dark font-medium">{a.documentTitle ?? '—'}</td>
                    <td className="py-3 px-4"><ScoreBadge score={a.score} size="sm" /></td>
                    <td className="py-3 px-4"><Badge variant="status">{a.status}</Badge></td>
                    <td className="py-3 px-4 text-gray-500">{formatDate(a.analyzedAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-slate-400 py-8 text-center">No completed analyses yet.</p>
        )}
      </Card>
    </div>
  );
}

function formatAction(action: string): string {
  return action.replace(/([A-Z])/g, ' $1').trim().toLowerCase();
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
