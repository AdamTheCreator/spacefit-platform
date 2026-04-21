import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import './index.css';
import App from './App.tsx';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes — data considered fresh
      gcTime: 1000 * 60 * 30, // 30 min — keep cache even when no subscribers
      // Don't refetch when the user switches browser tabs. The previous default
      // (true) triggered a request storm every time they came back to Settings
      // while the backend was cold-starting, and wiped the UI in the meantime.
      refetchOnWindowFocus: false,
      // Keep retrying cold-starts for ~15s total with exponential backoff.
      retry: 2,
      retryDelay: (attempt) => Math.min(1500 * 2 ** attempt, 8000),
    },
  },
});

// Pre-warm the Render free-tier backend as soon as the SPA loads. A cold
// Render service takes 30-90s to respond; firing a throw-away /health ping
// immediately means by the time the user hits a real endpoint the service is
// likely already awake. Fire-and-forget; errors are expected during cold start.
(function prewarmBackend() {
  const apiBase = import.meta.env.VITE_API_URL;
  if (!apiBase) return;
  const origin = apiBase.replace(/\/api\/v1\/?$/, '');
  fetch(`${origin}/health`, { method: 'GET', mode: 'cors', credentials: 'omit' })
    .catch(() => { /* intentionally swallow — the point is just to wake it up */ });
})();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <App />
        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            style: {
              background: '#1F3556',
              border: '1px solid #3E5681',
              color: '#F5F1E8',
            },
          }}
        />
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>
);
