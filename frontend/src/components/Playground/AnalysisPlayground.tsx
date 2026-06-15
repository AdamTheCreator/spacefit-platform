import { useMemo, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Sparkles,
  Play,
  FileText,
  Cpu,
  Gauge,
  ArrowRight,
  Settings2,
} from 'lucide-react';
import { Button } from '../ui/Button';
import { Slider } from '../ui/Slider';
import { SegmentedControl } from '../ui/SegmentedControl';
import { useStartAnalysis } from '../../hooks/useDocuments';
import {
  useAIConfig,
  useProviders,
  useUsage,
  useSpecialistModels,
  useUpdateSpecialistModels,
} from '../../hooks/useAIConfig';
import type { ParsedDocument } from '../../types/document';
import type { ChatSessionBrief } from '../../types/project';

// ---------------------------------------------------------------------------
// AnalysisPlayground — the shared "Playground" surface (DESIGN.md → Playground
// pattern). A persistent controls rail + run area for safely experimenting
// with an AI analysis: pick a document, tune parameters (analysis type, focus,
// trade-area radius), switch the model (BYOK), and run. Results stream through
// the existing /chat/:sessionId surface. Every control maps to a REAL
// /documents/{id}/start-analysis parameter — no mock data, no fake knobs.
//
// Mounted on both the project workspace (/projects/:id) and property detail
// (/property/:id) with host-supplied documents + run history.
// ---------------------------------------------------------------------------

const ANALYSIS_TYPES = [
  {
    value: 'void_analysis',
    label: 'Tenant gaps',
    blurb: 'Find missing tenant categories and recommend specific tenants for the available space.',
  },
  {
    value: 'competitive_analysis',
    label: 'Competitive',
    blurb: 'Map the competitive landscape and nearby operators around the property.',
  },
  {
    value: 'demographic_profile',
    label: 'Demographics',
    blurb: 'Trade-area population, income, and customer segmentation.',
  },
] as const;

type AnalysisTypeValue = (typeof ANALYSIS_TYPES)[number]['value'];

const FOCUS_OPTIONS = [
  { value: 'leasing', label: 'Leasing' },
  { value: 'investment_memo', label: 'Investment' },
] as const;

type FocusValue = (typeof FOCUS_OPTIONS)[number]['value'];

// Folded into the run instructions so the focus actually steers the prompt
// (the void analyzer reads use-case from the instructions).
const FOCUS_INSTRUCTION: Record<FocusValue, string> = {
  leasing: 'Focus: leasing — identify recruitable tenant targets for the available spaces.',
  investment_memo:
    'Focus: investment memo — emphasize demand signals and risk for an investment thesis.',
};

// The model switcher tunes the `analyst` specialist's default model — the
// specialist that performs these property analyses. 'analyst' is a valid
// SPECIALIST_REGISTRY key; the /ai-config/specialist-models endpoint rejects
// anything outside {scout, analyst, matchmaker, outreach, orchestrator}, so the
// AgentType values (void-analysis / demographics) must NOT be used here.
const ANALYSIS_SPECIALIST_KEY = 'analyst';

const ANALYSIS_LABEL: Record<string, string> = {
  void_analysis: 'Tenant gaps',
  competitive_analysis: 'Competitive',
  demographic_profile: 'Demographics',
};

export interface AnalysisPlaygroundProps {
  /** Documents available to analyze for this subject (project/property). */
  documents: ParsedDocument[];
  /** When set, run-history links route through the project chat surface. */
  projectId?: string;
  subjectName?: string | null;
  subjectAddress?: string | null;
  /** Prior analysis sessions, newest first — rendered as run history. */
  recentSessions?: ChatSessionBrief[];
  /** Shown in place of controls when there are no completed documents yet. */
  emptyState?: ReactNode;
}

export function AnalysisPlayground({
  documents,
  projectId,
  subjectName,
  subjectAddress,
  recentSessions,
  emptyState,
}: AnalysisPlaygroundProps) {
  const navigate = useNavigate();
  const startAnalysis = useStartAnalysis();
  const { data: aiConfig } = useAIConfig();
  const { data: providers } = useProviders();
  const { data: usage } = useUsage();
  const { data: specialist } = useSpecialistModels();
  const updateSpecialist = useUpdateSpecialistModels();

  const completedDocs = useMemo(
    () => documents.filter((d) => d.status === 'completed'),
    [documents],
  );

  const [pickedDocId, setPickedDocId] = useState<string | null>(null);
  const [analysisType, setAnalysisType] = useState<AnalysisTypeValue>('void_analysis');
  const [focus, setFocus] = useState<FocusValue>('leasing');
  const [radius, setRadius] = useState(3);
  const [notes, setNotes] = useState('');

  // Derive the effective document during render — falls back to the first
  // completed doc and stays valid as the host's list resolves, without an
  // effect (which would trigger a cascading re-render + selection flash).
  const docId =
    pickedDocId && completedDocs.some((d) => d.id === pickedDocId)
      ? pickedDocId
      : completedDocs[0]?.id ?? '';

  // --- Model switcher (BYOK only — platform-default users can't switch) ---
  const hasByok = !!aiConfig?.has_byok_key && !!aiConfig?.is_key_valid;
  const activeProvider = providers?.find((p) => p.id === aiConfig?.effective_provider);
  const modelOptions = activeProvider?.models ?? [];
  const specialistKey = ANALYSIS_SPECIALIST_KEY;
  const selectedModel =
    specialist?.specialist_models?.[specialistKey] || aiConfig?.effective_model || '';

  const handleModelChange = (model: string) => {
    const next = { ...(specialist?.specialist_models ?? {}) };
    if (model && model !== aiConfig?.effective_model) {
      next[specialistKey] = model;
    } else {
      delete next[specialistKey];
    }
    updateSpecialist.mutate(next, {
      onError: () => toast.error('Could not update the model'),
    });
  };

  const canRun = !!docId && !startAnalysis.isPending;

  const handleRun = async () => {
    if (!docId) return;
    const focusLine = analysisType === 'void_analysis' ? FOCUS_INSTRUCTION[focus] : '';
    const composed = [focusLine, notes.trim()].filter(Boolean).join('\n');
    try {
      const res = await startAnalysis.mutateAsync({
        documentId: docId,
        analysisType,
        tradeAreaMiles: radius,
        notes: composed || undefined,
      });
      // Project runs open in the project chat so they stay in context (and the
      // session is project-linked server-side); standalone runs use global chat.
      const href = projectId
        ? `/projects/${projectId}/chat/${res.session_id}`
        : `/chat/${res.session_id}`;
      navigate(href, {
        state: {
          initialMessage: 'Begin the analysis for this property.',
          documentId: docId,
          analysisType,
        },
      });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to start analysis');
    }
  };

  const selectedType = ANALYSIS_TYPES.find((t) => t.value === analysisType);
  const sessionHref = (id: string) =>
    projectId ? `/projects/${projectId}/chat/${id}` : `/chat/${id}`;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[minmax(320px,400px)_1fr] gap-5">
      {/* ── Controls rail ─────────────────────────────────────────────── */}
      <div className="card-industrial-static p-0 overflow-hidden">
        <div className="flex items-center gap-2.5 px-5 py-4 border-b border-[var(--border-subtle)]">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent-subtle)] flex items-center justify-center">
            <Sparkles size={16} className="text-[var(--accent)]" />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-industrial leading-tight">
              Analysis playground
            </h3>
            <p className="text-[11px] text-industrial-muted truncate">
              {subjectName || 'Configure and run an AI analysis'}
            </p>
          </div>
        </div>

        {completedDocs.length === 0 ? (
          <div className="px-5 py-6">
            {emptyState ?? (
              <p className="text-sm text-industrial-muted leading-relaxed">
                Upload and parse a document for this property to run an analysis. Once a
                document finishes processing it will appear here.
              </p>
            )}
          </div>
        ) : (
          <div className="px-5 py-5 space-y-5">
            {/* Document */}
            <div>
              <label className="flex items-center gap-1.5 text-xs font-semibold text-industrial-secondary tracking-wide mb-2">
                <FileText size={13} /> Document
              </label>
              <select
                value={docId}
                onChange={(e) => setPickedDocId(e.target.value)}
                className="input-industrial"
              >
                {completedDocs.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.filename}
                  </option>
                ))}
              </select>
            </div>

            {/* Analysis type */}
            <div>
              <span className="block text-xs font-semibold text-industrial-secondary tracking-wide mb-2">
                Analysis
              </span>
              <SegmentedControl
                ariaLabel="Analysis type"
                fill
                value={analysisType}
                onChange={(v) => setAnalysisType(v as AnalysisTypeValue)}
                options={ANALYSIS_TYPES.map((t) => ({ value: t.value, label: t.label }))}
              />
              <p className="mt-2 text-[11px] leading-snug text-industrial-muted">
                {selectedType?.blurb}
              </p>
            </div>

            {/* Focus (void analysis only) */}
            {analysisType === 'void_analysis' && (
              <div>
                <span className="block text-xs font-semibold text-industrial-secondary tracking-wide mb-2">
                  Focus
                </span>
                <SegmentedControl
                  ariaLabel="Analysis focus"
                  fill
                  size="sm"
                  value={focus}
                  onChange={(v) => setFocus(v as FocusValue)}
                  options={FOCUS_OPTIONS.map((f) => ({ value: f.value, label: f.label }))}
                />
              </div>
            )}

            {/* Trade-area radius */}
            <Slider
              label="Trade-area radius"
              value={radius}
              onChange={setRadius}
              min={1}
              max={10}
              step={0.5}
              unit="mi"
            />

            {/* Model switcher */}
            <div>
              <label className="flex items-center gap-1.5 text-xs font-semibold text-industrial-secondary tracking-wide mb-2">
                <Cpu size={13} /> Model
              </label>
              {hasByok ? (
                <>
                  <select
                    value={selectedModel}
                    onChange={(e) => handleModelChange(e.target.value)}
                    className="input-industrial"
                    disabled={updateSpecialist.isPending || modelOptions.length === 0}
                  >
                    {modelOptions.length === 0 && (
                      <option value={selectedModel}>{selectedModel || 'Default model'}</option>
                    )}
                    {modelOptions.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1.5 text-[11px] leading-snug text-industrial-muted">
                    Saved as your default model for property analyses.
                  </p>
                </>
              ) : (
                <div className="flex items-center justify-between gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-tertiary)] px-3 py-2">
                  <span className="text-xs text-industrial-secondary truncate">
                    {aiConfig?.effective_model || 'Platform default'}
                  </span>
                  <button
                    type="button"
                    onClick={() => navigate('/settings')}
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--accent)] hover:underline flex-shrink-0"
                  >
                    <Settings2 size={12} /> Add key to switch
                  </button>
                </div>
              )}
            </div>

            {/* Instructions */}
            <div>
              <label className="block text-xs font-semibold text-industrial-secondary tracking-wide mb-2">
                Instructions <span className="font-normal text-industrial-muted">(optional)</span>
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. QSR and fast-casual only, national credit tenants…"
                rows={2}
                className="input-industrial resize-none"
              />
            </div>

            <Button
              variant="primary"
              onClick={handleRun}
              disabled={!canRun}
              loading={startAnalysis.isPending}
              iconLeft={!startAnalysis.isPending ? <Play size={14} /> : undefined}
              className="w-full"
            >
              {startAnalysis.isPending ? 'Starting…' : 'Run analysis'}
            </Button>

            {/* Usage strip */}
            {usage && (
              <div className="flex items-center gap-2 pt-1 text-[11px] text-industrial-muted">
                <Gauge size={12} className="flex-shrink-0" />
                <span className="tabular-nums">
                  {usage.last_24h_total_tokens.toLocaleString()} tokens · {usage.last_24h_llm_calls}{' '}
                  calls (24h)
                </span>
                <span
                  className={`ml-auto px-1.5 py-0.5 rounded-full font-medium ${
                    usage.using_byok
                      ? 'bg-[var(--bg-success)] text-[var(--color-success)]'
                      : 'bg-[var(--bg-tertiary)] text-industrial-secondary'
                  }`}
                >
                  {usage.using_byok ? 'Your key' : 'Platform'}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Run area: explainer + history ─────────────────────────────── */}
      <div className="space-y-5">
        <div className="card-industrial-static flex items-start gap-4">
          <img
            src="/mascots/goose-engineer.webp"
            alt=""
            aria-hidden="true"
            className="w-16 h-16 object-contain shrink-0 select-none hidden sm:block"
            draggable={false}
          />
          <div>
            <h4 className="text-sm font-semibold text-industrial">How the playground works</h4>
            <p className="text-[13px] text-industrial-secondary mt-1.5 leading-relaxed">
              Pick a parsed document, tune the parameters, and run. Specialist agents stream their
              work live — you can re-run with different settings to compare results. Every run is
              saved below.
            </p>
            {subjectAddress && (
              <p className="text-[11px] text-industrial-muted mt-2">{subjectAddress}</p>
            )}
          </div>
        </div>

        <div className="card-industrial-static">
          <h4 className="text-sm font-semibold text-industrial mb-1">Recent runs</h4>
          {recentSessions && recentSessions.length > 0 ? (
            <div className="divide-y divide-[var(--border-subtle)] -mb-2">
              {recentSessions.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => navigate(sessionHref(s.id))}
                  className="group flex items-center gap-3 w-full text-left py-2.5 hover:bg-[var(--hover-overlay)] -mx-2 px-2 rounded-lg transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-industrial truncate">
                      {s.title || 'Untitled analysis'}
                    </p>
                    <p className="text-[11px] text-industrial-muted">
                      {s.analysis_type ? ANALYSIS_LABEL[s.analysis_type] ?? s.analysis_type : 'Chat'}
                      {' · '}
                      {s.message_count} message{s.message_count === 1 ? '' : 's'}
                    </p>
                  </div>
                  <ArrowRight
                    size={14}
                    className="text-industrial-muted group-hover:text-[var(--accent)] transition-colors flex-shrink-0"
                  />
                </button>
              ))}
            </div>
          ) : (
            <p className="text-[13px] text-industrial-muted mt-1.5">
              No runs yet. Configure an analysis on the left and hit Run.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default AnalysisPlayground;
