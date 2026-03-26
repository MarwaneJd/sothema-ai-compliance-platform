import type { AnalysisStatus, UserRole } from '@/types';

const statusStyles: Record<AnalysisStatus, string> = {
  Pending: 'bg-yellow-50 text-yellow-700 border border-yellow-200',
  Processing: 'bg-sothema-cyan-light text-sothema-primary-dark border border-sothema-cyan/30',
  Completed: 'bg-green-50 text-green-700 border border-green-200',
  Failed: 'bg-red-50 text-red-700 border border-red-200',
};

const roleStyles: Record<UserRole, string> = {
  Admin: 'bg-purple-50 text-purple-700 border border-purple-200',
  Analyst: 'bg-sothema-cyan-light text-sothema-primary-dark border border-sothema-cyan/30',
  Viewer: 'bg-slate-50 text-slate-700 border border-slate-200',
};

interface BadgeProps {
  children: string;
  variant?: 'status' | 'role' | 'default';
  className?: string;
}

export function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
  let style = 'bg-gray-100 text-gray-700';

  if (variant === 'status' && children in statusStyles) {
    style = statusStyles[children as AnalysisStatus];
  } else if (variant === 'role' && children in roleStyles) {
    style = roleStyles[children as UserRole];
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style} ${className}`}>
      {children}
    </span>
  );
}
