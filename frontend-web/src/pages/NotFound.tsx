import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { FileQuestion } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="flex items-center justify-center py-20">
      <Card className="text-center max-w-md">
        <FileQuestion className="h-16 w-16 mx-auto mb-4 text-gray-300" />
        <h1 className="text-2xl font-bold text-sothema-dark mb-2">404</h1>
        <p className="text-gray-500 mb-6">The page you're looking for doesn't exist.</p>
        <Link to="/">
          <Button>Back to Dashboard</Button>
        </Link>
      </Card>
    </div>
  );
}
