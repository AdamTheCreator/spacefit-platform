import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from './components/Auth';
import { ErrorBoundary } from './components/ErrorBoundary';

// Lazy load page components for code splitting
const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import('./pages/RegisterPage').then(m => ({ default: m.RegisterPage })));
const AuthCallbackPage = lazy(() => import('./pages/AuthCallbackPage').then(m => ({ default: m.AuthCallbackPage })));
const ChatPage = lazy(() => import('./pages/ChatPage').then(m => ({ default: m.ChatPage })));
const DemoPage = lazy(() => import('./pages/DemoPage').then(m => ({ default: m.DemoPage })));
const ProfilePage = lazy(() => import('./pages/ProfilePage').then(m => ({ default: m.ProfilePage })));
const CustomersPage = lazy(() => import('./pages/CustomersPage').then(m => ({ default: m.CustomersPage })));
const ConnectionsPage = lazy(() => import('./pages/ConnectionsPage').then(m => ({ default: m.ConnectionsPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })));
const PipelinePage = lazy(() => import('./pages/PipelinePage').then(m => ({ default: m.PipelinePage })));
const DocumentsPage = lazy(() => import('./pages/DocumentsPage').then(m => ({ default: m.DocumentsPage })));
const OutreachPage = lazy(() => import('./pages/OutreachPage').then(m => ({ default: m.OutreachPage })));
const PricingPage = lazy(() => import('./pages/PricingPage').then(m => ({ default: m.PricingPage })));
const OnboardingPage = lazy(() => import('./pages/OnboardingPage').then(m => ({ default: m.OnboardingPage })));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })));

// Loading fallback component - Industrial style
function PageLoader() {
  return (
    <div className="h-screen w-screen bg-industrial flex items-center justify-center">
      <div className="flex flex-col items-center gap-6">
        {/* Industrial loading indicator */}
        <div className="relative">
          <div className="w-12 h-12 border border-[var(--border-color)]" />
          <div className="absolute inset-0 border-t-2 border-[var(--accent)] animate-spin" />
        </div>
        <div className="flex flex-col items-center gap-2">
          <p className="font-mono text-xs tracking-wider uppercase text-industrial-secondary">
            Initializing
          </p>
          <div className="flex gap-1">
            <span className="w-1.5 h-1.5 bg-[var(--accent)] animate-pulse" />
            <span className="w-1.5 h-1.5 bg-[var(--accent)] animate-pulse [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 bg-[var(--accent)] animate-pulse [animation-delay:300ms]" />
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  return (
    <div className="h-screen w-screen bg-industrial dark">
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route path="/demo" element={<DemoPage />} />
          <Route path="/pricing" element={<PricingPage />} />

          {/* Protected routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/onboarding" element={<OnboardingPage />} />
            <Route path="/" element={<ErrorBoundary><ChatPage /></ErrorBoundary>} />
            <Route path="/chat" element={<ErrorBoundary><ChatPage /></ErrorBoundary>} />
            <Route path="/chat/:sessionId" element={<ErrorBoundary><ChatPage /></ErrorBoundary>} />
            <Route path="/pipeline" element={<PipelinePage />} />
            <Route path="/pipeline/:dealId" element={<PipelinePage />} />
            <Route path="/documents" element={<ErrorBoundary><DocumentsPage /></ErrorBoundary>} />
            <Route path="/outreach" element={<OutreachPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/customers" element={<CustomersPage />} />
            <Route path="/connections" element={<ConnectionsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>

          {/* Catch-all 404 route */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </div>
  );
}

export default App;
