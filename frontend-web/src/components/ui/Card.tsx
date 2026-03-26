import type { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
}

export function Card({ children, className = '' }: CardProps) {
  return (
    <div className={`glass-card hover-lift p-6 ${className}`}>
      {children}
    </div>
  );
}
