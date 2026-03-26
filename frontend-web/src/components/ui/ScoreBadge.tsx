interface ScoreBadgeProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-score-high bg-white ring-score-high/30 shadow-[0_2px_10px_rgba(16,185,129,0.15)]';
  if (score >= 60) return 'text-score-medium bg-white ring-score-medium/30 shadow-[0_2px_10px_rgba(245,158,11,0.15)]';
  if (score >= 40) return 'text-score-low bg-white ring-score-low/30 shadow-[0_2px_10px_rgba(249,115,22,0.15)]';
  return 'text-score-critical bg-white ring-score-critical/30 shadow-[0_2px_10px_rgba(239,68,68,0.15)]';
}

const sizeClasses = {
  sm: 'w-10 h-10 text-sm',
  md: 'w-14 h-14 text-lg',
  lg: 'w-20 h-20 text-2xl',
};

export function ScoreBadge({ score, size = 'md' }: ScoreBadgeProps) {
  return (
    <div
      className={`inline-flex items-center justify-center rounded-full font-bold ring-2 ${getScoreColor(score)} ${sizeClasses[size]}`}
    >
      {score}
    </div>
  );
}

export function getScoreLabel(score: number): string {
  if (score >= 80) return 'Excellent';
  if (score >= 60) return 'Good';
  if (score >= 40) return 'Needs Improvement';
  return 'Critical';
}
