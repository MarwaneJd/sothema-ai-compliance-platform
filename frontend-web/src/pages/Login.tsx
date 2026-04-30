import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

export default function Login() {
  const { login } = useAuth();

  return (
    <div className="min-h-screen flex items-center justify-center bg-sothema-bg p-6">
      <Card className="max-w-md w-full text-center">
        <h1 className="text-2xl font-bold text-sothema-dark mb-2">Sothema Compliance Platform</h1>
        <p className="text-sm text-gray-500 mb-6">
          Sign in with your Microsoft account to continue.
        </p>
        <Button onClick={() => login()} className="w-full">
          Sign in with Microsoft
        </Button>
      </Card>
    </div>
  );
}
