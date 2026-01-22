import { Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from './components/Auth';
import {
  LoginPage,
  RegisterPage,
  AuthCallbackPage,
  ChatPage,
  DemoPage,
  ProfilePage,
  CustomersPage,
  ConnectionsPage,
  SettingsPage,
  PipelinePage,
  DocumentsPage,
  OutreachPage,
  PricingPage,
} from './pages';
import { OnboardingPage } from './pages/OnboardingPage';

function App() {
  return (
    <div className="h-screen w-screen bg-gray-900">
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
          <Route path="/" element={<ChatPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chat/:sessionId" element={<ChatPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/pipeline/:dealId" element={<PipelinePage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/outreach" element={<OutreachPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/customers" element={<CustomersPage />} />
          <Route path="/connections" element={<ConnectionsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </div>
  );
}

export default App;
