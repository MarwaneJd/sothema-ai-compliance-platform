import { RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';
import type { ComplianceDetails } from '@/types';

interface CategoryBreakdownChartProps {
  details: ComplianceDetails;
}

export function CategoryBreakdownChart({ details }: CategoryBreakdownChartProps) {
  const data = [
    { category: 'Documentation', score: details.documentation.score, max: 25 },
    { category: 'Regulatory', score: details.regulatory.score, max: 25 },
    { category: 'Quality', score: details.quality.score, max: 25 },
    { category: 'Traceability', score: details.traceability.score, max: 25 },
  ];

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RadarChart data={data}>
        <PolarGrid stroke="#e5e7eb" />
        <PolarAngleAxis dataKey="category" tick={{ fontSize: 12, fill: '#32373c' }} />
        <PolarRadiusAxis domain={[0, 25]} tick={{ fontSize: 10 }} />
        <Radar dataKey="score" stroke="#0074C8" fill="#0074C8" fillOpacity={0.25} strokeWidth={2} />
      </RadarChart>
    </ResponsiveContainer>
  );
}
