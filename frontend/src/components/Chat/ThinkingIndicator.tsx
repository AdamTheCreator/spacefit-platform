import { useState, useEffect, useRef } from 'react';
import { AGENTS, type AgentType, type WorkflowStep } from '../../types/chat';

/* ── Agent colors for the per-agent spinner arc ─────────────────────────────── */
const AGENT_SPINNER_COLORS: Partial<Record<AgentType, string>> = {
  scout:      '#3A5BA0',
  analyst:    '#C25E1F',
  matchmaker: '#2F7A3B',
};

/* ── Phase labels driven by workflow state ──────────────────────────────────── */
function derivePhaseLabel(steps: WorkflowStep[]): string {
  if (steps.length === 0) return 'Reading your question';

  const running = steps.find((s) => s.status === 'running');
  if (!running) {
    const allDone = steps.every((s) => s.status === 'completed');
    return allDone ? 'Drafting your answer' : 'Planning the approach';
  }

  const name = AGENTS[running.agentType]?.name ?? running.agentType;
  const desc = running.description;
  if (desc) return desc;

  // Fallback per specialist
  switch (running.agentType) {
    case 'scout': return 'Researching the trade area';
    case 'analyst': return 'Analyzing tenant gaps';
    case 'matchmaker': return 'Matching tenants';
    default: return `Working with ${name}`;
  }
}

/* ── Inline SVG primitives ──────────────────────────────────────────────────── */
function Spinner({ size = 13, color = 'var(--accent)' }: { size?: number; color?: string }) {
  return (
    <svg className="ti-spin" width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
      <circle cx="12" cy="12" r="9" stroke="var(--border-default)" strokeWidth="3" />
      <path d="M21 12a9 9 0 00-9-9" stroke={color} strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function Check({ size = 13, color = '#2F7A3B' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}

/* ── Single row in the work log ─────────────────────────────────────────────── */
function LogRow({ live, done, label, color }: { live: boolean; done: boolean; label: string; color?: string }) {
  return (
    <div className="ti-rise" style={{ display: 'flex', gap: 9, alignItems: 'flex-start', padding: '7px 0' }}>
      <div style={{ width: 16, display: 'flex', justifyContent: 'center', paddingTop: 1 }}>
        {live ? (
          <Spinner color={color || 'var(--accent)'} />
        ) : done ? (
          <Check />
        ) : (
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--border-default)', marginTop: 4 }} />
        )}
      </div>
      <div style={{
        fontSize: '12.5px',
        fontWeight: live ? 600 : 500,
        color: live ? 'var(--text-primary)' : done ? 'var(--text-secondary)' : 'var(--text-muted)',
        minWidth: 0,
      }}>
        {label}
      </div>
    </div>
  );
}

/* ── Main ThinkingIndicator (work log card) ─────────────────────────────────── */
interface ThinkingIndicatorProps {
  isVisible: boolean;
  activeAgentType?: AgentType | null;
  workflowSteps: WorkflowStep[];
}

export function ThinkingIndicator({ isVisible, workflowSteps }: ThinkingIndicatorProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const startRef = useRef<number>(Date.now());

  // Reset timer when indicator becomes visible
  useEffect(() => {
    if (isVisible) {
      startRef.current = Date.now();
      setElapsedSec(0);
      setCollapsed(false);
    }
  }, [isVisible]);

  // Tick elapsed seconds
  useEffect(() => {
    if (!isVisible) return;
    const iv = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(iv);
  }, [isVisible]);

  if (!isVisible) return null;

  const phaseLabel = derivePhaseLabel(workflowSteps);

  // Build row data from workflow steps
  const rows: { key: string; label: string; live: boolean; done: boolean; color?: string }[] = [];

  // Always show "Understanding the request" as first row
  const hasRunningOrDone = workflowSteps.some((s) => s.status === 'running' || s.status === 'completed');
  rows.push({
    key: 'understand',
    label: 'Understanding the request',
    live: !hasRunningOrDone,
    done: hasRunningOrDone,
  });

  // One row per workflow step (specialist agents)
  for (const step of workflowSteps) {
    const agentName = AGENTS[step.agentType]?.name ?? step.agentType;
    const task = step.description || AGENTS[step.agentType]?.description || '';
    rows.push({
      key: step.id,
      label: task ? `${agentName} \u00B7 ${task.charAt(0).toLowerCase() + task.slice(1)}` : agentName,
      live: step.status === 'running',
      done: step.status === 'completed',
      color: AGENT_SPINNER_COLORS[step.agentType],
    });
  }

  // Show "Drafting your answer" when all specialists are done
  const allSpecialistsDone = workflowSteps.length > 0 && workflowSteps.every((s) => s.status === 'completed');
  if (allSpecialistsDone) {
    rows.push({ key: 'draft', label: 'Drafting your answer', live: true, done: false });
  }

  return (
    <div className="w-full animate-fade-in" role="status" aria-live="polite" aria-label="Space Goose is working on your request">
      <div className="chat-stage px-4 py-2">
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          {/* Avatar */}
          <div style={{ width: 28, height: 28, borderRadius: '50%', flexShrink: 0, overflow: 'hidden' }}>
            <img src="/spacegoose-logo.png" alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
          </div>

          {/* Card */}
          <div style={{ flex: 1, minWidth: 0, maxWidth: 460 }}>
            <div style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-default)',
              borderRadius: 12,
              padding: '11px 14px 8px',
            }}>
              {/* Header — clickable to collapse/expand */}
              <button
                onClick={() => setCollapsed((c) => !c)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  width: '100%',
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  fontFamily: 'var(--font-sans)',
                  textAlign: 'left',
                }}
              >
                <Spinner />
                <span style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {phaseLabel}...
                </span>
                <span style={{
                  marginLeft: 'auto',
                  fontSize: 11,
                  color: 'var(--text-muted)',
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {elapsedSec}s
                </span>
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="var(--text-muted)"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ transform: collapsed ? 'none' : 'rotate(180deg)', transition: 'transform 0.2s' }}
                >
                  <path d="M6 9l6 6 6-6" />
                </svg>
              </button>

              {/* Rows */}
              {!collapsed && (
                <div style={{ marginTop: 6, borderTop: '1px solid var(--border-default)', paddingTop: 4 }}>
                  {rows.map((r) => (
                    <LogRow key={r.key} live={r.live} done={r.done} label={r.label} color={r.color} />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
