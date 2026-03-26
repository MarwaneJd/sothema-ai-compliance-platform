import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import type { ComplianceAnalysis } from '@/types';

interface ScoreDistributionChartProps {
  analyses: ComplianceAnalysis[];
}

const ranges = [
  { label: '0-20', min: 0, max: 20, color: '#dc2626' },
  { label: '21-40', min: 21, max: 40, color: '#f97316' },
  { label: '41-60', min: 41, max: 60, color: '#eab308' },
  { label: '61-80', min: 61, max: 80, color: '#0074C8' },
  { label: '81-100', min: 81, max: 100, color: '#16a34a' },
];

export function ScoreDistributionChart({ analyses }: ScoreDistributionChartProps) {
  const completed = analyses.filter((a) => a.status === 'Completed');
  const data = ranges.map((r) => ({
    range: r.label,
    count: completed.filter((a) => a.score >= r.min && a.score <= r.max).length,
    color: r.color,
  }));

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
        <XAxis dataKey="range" tick={{ fontSize: 12 }} />
        <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
        <Tooltip />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
