import { FileX } from 'lucide-react';
import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
}

export function EmptyState({ title, description, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-gray-400">
      {icon || <FileX className="h-12 w-12 mb-4" />}
      <h3 className="text-lg font-medium text-gray-600 mb-1">{title}</h3>
      {description && <p className="text-sm">{description}</p>}
    </div>
  );
}
