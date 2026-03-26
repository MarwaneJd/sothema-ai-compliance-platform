import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, ShieldCheck, TrendingUp, Clock } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { ScoreDistributionChart } from '@/components/charts/ScoreDistributionChart';
import { mockDocuments } from '@/mocks/documents';
import { mockAnalyses } from '@/mocks/analyses';
import { mockAuditLogs } from '@/mocks/auditLogs';

export default function Dashboard() {
  const navigate = useNavigate();
  const [loaded, setLoaded] = useState(false);
  useEffect(() => setLoaded(true), []);

  const completed = mockAnalyses.filter((a) => a.status === 'Completed');
  const avgScore = completed.length
    ? Math.round(completed.reduce((s, a) => s + a.score, 0) / completed.length)
    : 0;
  const pending = mockAnalyses.filter((a) => a.status === 'Pending' || a.status === 'Processing').length;

  const stats = [
    { label: 'Total Documents', value: mockDocuments.length, icon: FileText, color: 'text-sothema-cyan' },
    { label: 'Analyses Run', value: mockAnalyses.length, icon: ShieldCheck, color: 'text-sothema-navy' },
    { label: 'Average Score', value: avgScore, icon: TrendingUp, color: 'text-score-high' },
    { label: 'In Progress', value: pending, icon: Clock, color: 'text-score-medium' },
  ];

  const recentActivity = mockAuditLogs.slice(0, 6);
  const recentAnalyses = mockAnalyses.filter((a) => a.status === 'Completed').slice(0, 5);

  if (!loaded) return null;

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
        {stats.map((stat) => {
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
          <ScoreDistributionChart analyses={mockAnalyses} />
        </Card>

        {/* Recent Activity */}
        <Card>
          <h2 className="text-lg font-semibold text-sothema-dark mb-4">Recent Activity</h2>
          <div className="space-y-3">
            {recentActivity.map((log) => (
              <div key={log.id} className="flex items-start gap-3 text-sm">
                <div className="w-2 h-2 rounded-full bg-sothema-cyan mt-1.5 flex-shrink-0" />
                <div>
                  <p className="text-sothema-dark">
                    <span className="font-medium">{log.userName}</span>{' '}
                    <span className="text-gray-500">{formatAction(log.action)}</span>
                  </p>
                  <p className="text-xs text-gray-400">{formatDate(log.timestamp)}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Recent Analyses */}
      <Card>
        <h2 className="text-lg font-semibold text-sothema-dark mb-4">Recent Analyses</h2>
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
                  <td className="py-3 px-4 text-sothema-dark font-medium">{a.documentTitle}</td>
                  <td className="py-3 px-4"><ScoreBadge score={a.score} size="sm" /></td>
                  <td className="py-3 px-4"><Badge variant="status">{a.status}</Badge></td>
                  <td className="py-3 px-4 text-gray-500">{formatDate(a.analyzedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
