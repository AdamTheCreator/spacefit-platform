import { useEffect, useRef, useState } from 'react';
import { X, Loader2, Check } from 'lucide-react';
import api from '../../lib/axios';
import { useAuthStore } from '../../stores/authStore';

type Props = {
  open: boolean;
  onClose: () => void;
};

const TEAM_SIZES = [
  { value: '1-5', label: '1 – 5 people' },
  { value: '6-20', label: '6 – 20 people' },
  { value: '21-50', label: '21 – 50 people' },
  { value: '50+', label: '50+ people' },
];

const TOOL_OPTIONS = [
  'CoStar',
  'Placer.ai',
  'SiteUSA',
  'Salesforce',
  'HubSpot',
  'Other',
];

export function SalesLeadModal({ open, onClose }: Props) {
  const { user } = useAuthStore();
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [teamSize, setTeamSize] = useState('');
  const [tools, setTools] = useState<string[]>([]);
  const [useCase, setUseCase] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && user?.email) {
      setEmail(user.email);
    }
  }, [open, user?.email]);

  useEffect(() => {
    if (!open) {
      // Reset on close so a re-open starts fresh.
      const t = setTimeout(() => {
        setSuccess(false);
        setError(null);
        setCompany('');
        setTeamSize('');
        setTools([]);
        setUseCase('');
      }, 200);
      return () => clearTimeout(t);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  const toggleTool = (tool: string) => {
    setTools((prev) =>
      prev.includes(tool) ? prev.filter((t) => t !== tool) : [...prev, tool],
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.post('/sales/leads', {
        email,
        company_name: company || null,
        team_size: teamSize || null,
        current_tools: tools.length ? tools : null,
        use_case: useCase || null,
      });
      setSuccess(true);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Couldn't submit your request. Please try again.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(15, 27, 45, 0.5)' }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="sales-lead-title"
        className="w-full max-w-lg rounded-2xl border bg-white p-6 sm:p-8 shadow-xl"
        style={{ borderColor: '#E0DFDD' }}
      >
        <div className="flex items-start justify-between mb-6">
          <div>
            <h2
              id="sales-lead-title"
              className="text-xl font-semibold"
              style={{ color: '#0F1B2D', fontFamily: "'Sora', sans-serif" }}
            >
              Talk to sales
            </h2>
            <p className="mt-1 text-sm" style={{ color: '#737169' }}>
              Tell us about your team and we'll be in touch within one business day.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="p-1 rounded-md hover:bg-neutral-100"
            style={{ color: '#737169' }}
          >
            <X size={20} />
          </button>
        </div>

        {success ? (
          <div className="flex flex-col items-center text-center py-8">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center mb-4"
              style={{ background: '#E5F4EC' }}
            >
              <Check size={24} style={{ color: '#1F7A4D' }} />
            </div>
            <h3
              className="text-lg font-semibold mb-2"
              style={{ color: '#0F1B2D', fontFamily: "'Sora', sans-serif" }}
            >
              Thanks — we got it.
            </h3>
            <p className="text-sm mb-6" style={{ color: '#737169' }}>
              Our team will reach out shortly to set up a call.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-md text-sm font-semibold"
              style={{ background: '#0F1B2D', color: 'white' }}
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <Field label="Work email" required>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="w-full px-3 py-2 rounded-md border text-sm"
                style={{ borderColor: '#E0DFDD' }}
              />
            </Field>

            <Field label="Company">
              <input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Northstar Capital"
                className="w-full px-3 py-2 rounded-md border text-sm"
                style={{ borderColor: '#E0DFDD' }}
              />
            </Field>

            <Field label="Team size">
              <div className="grid grid-cols-2 gap-2">
                {TEAM_SIZES.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setTeamSize(opt.value)}
                    className="px-3 py-2 rounded-md border text-sm text-left transition"
                    style={{
                      borderColor: teamSize === opt.value ? '#0F1B2D' : '#E0DFDD',
                      background: teamSize === opt.value ? '#0F1B2D' : 'white',
                      color: teamSize === opt.value ? 'white' : '#0F1B2D',
                    }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </Field>

            <Field label="Current tools (select any)">
              <div className="flex flex-wrap gap-2">
                {TOOL_OPTIONS.map((tool) => {
                  const active = tools.includes(tool);
                  return (
                    <button
                      key={tool}
                      type="button"
                      onClick={() => toggleTool(tool)}
                      className="px-3 py-1.5 rounded-full border text-xs font-medium transition"
                      style={{
                        borderColor: active ? '#0F1B2D' : '#E0DFDD',
                        background: active ? '#0F1B2D' : 'white',
                        color: active ? 'white' : '#0F1B2D',
                      }}
                    >
                      {tool}
                    </button>
                  );
                })}
              </div>
            </Field>

            <Field label="What are you trying to do? (optional)">
              <textarea
                value={useCase}
                onChange={(e) => setUseCase(e.target.value)}
                rows={3}
                placeholder="We're a 12-person retail brokerage looking to replace CoStar…"
                className="w-full px-3 py-2 rounded-md border text-sm"
                style={{ borderColor: '#E0DFDD' }}
              />
            </Field>

            {error && (
              <div
                className="text-sm px-3 py-2 rounded-md"
                style={{ background: '#FDECEC', color: '#9B1C1C' }}
              >
                {error}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-md text-sm font-semibold border"
                style={{ borderColor: '#E0DFDD', color: '#0F1B2D' }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !email}
                className="px-4 py-2 rounded-md text-sm font-semibold inline-flex items-center gap-2 disabled:opacity-50"
                style={{ background: '#0F1B2D', color: 'white' }}
              >
                {submitting && <Loader2 size={14} className="animate-spin" />}
                Send request
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span
        className="block text-xs font-semibold uppercase tracking-wide mb-1.5"
        style={{ color: '#737169' }}
      >
        {label}
        {required && <span style={{ color: '#9B1C1C' }}> *</span>}
      </span>
      {children}
    </label>
  );
}
