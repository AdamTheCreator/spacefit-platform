import { useState } from 'react';
import { ThumbsUp, ThumbsDown, X } from 'lucide-react';
import api from '../../lib/axios';

interface TenantFeedbackProps {
  sessionId: string;
  suggestion: string;
}

export function TenantFeedback({ sessionId, suggestion }: TenantFeedbackProps) {
  const [feedback, setFeedback] = useState<'positive' | 'negative' | null>(null);
  const [showCorrection, setShowCorrection] = useState(false);
  const [correction, setCorrection] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleFeedback = async (type: 'positive' | 'negative') => {
    setFeedback(type);
    if (type === 'negative') {
      setShowCorrection(true);
      return;
    }
    // Positive feedback — submit immediately
    await submitFeedback(type);
  };

  const submitFeedback = async (type: 'positive' | 'negative', correctionText?: string) => {
    try {
      await api.post('/feedback/tenant', {
        session_id: sessionId,
        suggestion,
        feedback: type,
        correction_text: correctionText || null,
      });
      setSubmitted(true);
      setShowCorrection(false);
    } catch {
      // Silently fail — feedback is non-critical
    }
  };

  if (submitted) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-industrial-muted">
        {feedback === 'positive' ? <ThumbsUp size={10} /> : <ThumbsDown size={10} />}
        Thanks for the feedback
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1">
      <button
        onClick={() => handleFeedback('positive')}
        className={`p-1 rounded hover:bg-[var(--bg-secondary)] transition-colors ${
          feedback === 'positive' ? 'text-green-500' : 'text-industrial-muted'
        }`}
        title="Good suggestion"
      >
        <ThumbsUp size={12} />
      </button>
      <button
        onClick={() => handleFeedback('negative')}
        className={`p-1 rounded hover:bg-[var(--bg-secondary)] transition-colors ${
          feedback === 'negative' ? 'text-red-500' : 'text-industrial-muted'
        }`}
        title="Inaccurate suggestion"
      >
        <ThumbsDown size={12} />
      </button>

      {showCorrection && (
        <span className="inline-flex items-center gap-1 ml-1">
          <input
            type="text"
            value={correction}
            onChange={(e) => setCorrection(e.target.value)}
            placeholder="What's wrong?"
            className="px-2 py-1 text-xs bg-[var(--bg-secondary)] border border-[var(--border-default)] rounded-md text-industrial w-40 focus:outline-none focus:border-[var(--accent)]"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                submitFeedback('negative', correction);
              }
            }}
            autoFocus
          />
          <button
            onClick={() => submitFeedback('negative', correction)}
            className="px-2 py-1 text-xs bg-[var(--accent)] text-white rounded-md hover:bg-[var(--accent)]/90"
          >
            Send
          </button>
          <button
            onClick={() => { setShowCorrection(false); setFeedback(null); }}
            className="p-1 text-industrial-muted hover:text-industrial"
          >
            <X size={12} />
          </button>
        </span>
      )}
    </span>
  );
}
