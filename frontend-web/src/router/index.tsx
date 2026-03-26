import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { RoleGuard } from '@/components/guards/RoleGuard';
import Dashboard from '@/pages/Dashboard';
import Documents from '@/pages/Documents';
import DocumentDetail from '@/pages/DocumentDetail';
import ComplianceAnalyses from '@/pages/ComplianceAnalyses';
import ComplianceDetail from '@/pages/ComplianceDetail';
import Chat from '@/pages/Chat';
import AuditLogs from '@/pages/AuditLogs';
import Settings from '@/pages/Settings';
import NotFound from '@/pages/NotFound';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'documents', element: <Documents /> },
      { path: 'documents/:id', element: <DocumentDetail /> },
      { path: 'compliance', element: <ComplianceAnalyses /> },
      { path: 'compliance/:analysisId', element: <ComplianceDetail /> },
      { path: 'chat', element: <Chat /> },
      {
        path: 'audit',
        element: (
          <RoleGuard role="Admin">
            <AuditLogs />
          </RoleGuard>
        ),
      },
      { path: 'settings', element: <Settings /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);
