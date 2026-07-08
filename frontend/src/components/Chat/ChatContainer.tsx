import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Users, FileText, Mail, Save, ArrowRight, MapPin, Key, Layers } from 'lucide-react';
import { useChat } from '../../hooks/useChat';
import { useChatStore } from '../../stores/chatStore';
import { useAIConfig } from '../../hooks/useAIConfig';
import { useChatSessions } from '../../hooks/useChatSessions';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { AnalysisProcessingView } from './AnalysisProcessingView';
import { ExportBar } from './ExportBar';
import { TenantSavePanel } from './TenantSavePanel';
import { ThinkingIndicator } from './ThinkingIndicator';
import { PromoteNudge } from './PromoteNudge';
import { PromoteModal } from './PromoteModal';
import {
  headerMode,
  shouldShowSaveButton,
  shouldShowNudge,
  composerFootnoteVariant,
  type PromoteChatContext,
} from './promoteChat';
import { AGENTS, type AgentType } from '../../types/chat';

interface ChatContainerProps {
  initialSessionId?: string;
  chatContext?: string;
  projectId?: string;
}

interface LocationState {
  initialMessage?: string;
  documentId?: string;
  analysisType?: string;
}

// Vertical mode definitions for the mode picker
const VERTICAL_MODES = [
  { id: "MASTER_DEFAULT", emoji: "🏢", label: "General CRE", desc: "All property types" },
  { id: "QSR_FAST_FOOD", emoji: "🍔", label: "Fast Food / QSR", desc: "Site selection for restaurants" },
  { id: "MALL_RETAIL", emoji: "🛍️", label: "Mall & Retail", desc: "Tenant mix and gap analysis" },
  { id: "OFFICE_SPACE", emoji: "💼", label: "Office Space", desc: "Leasing and market comps" },
  { id: "INDUSTRIAL", emoji: "🏭", label: "Industrial", desc: "Warehouse and logistics" },
] as const;

type VerticalModeId = typeof VERTICAL_MODES[number]['id'];

// CTA configs keyed by the agent type that triggers them
const NEXT_STEP_ACTIONS: Record<string, { label: string; icon: React.ReactNode; message: string }[]> = {
  orchestrator: [
    // Shown after demographics summary — let user adjust radius or continue
    { label: 'Adjust trade area radius', icon: <MapPin size={14} />, message: 'Re-run the demographics with a different radius (1, 3, 5, or 10 miles)' },
    { label: 'Analyze tenant mix', icon: <Users size={14} />, message: 'Analyze the current tenant mix at this property' },
  ],
  'void-analysis': [
    { label: 'Match tenants', icon: <Users size={14} />, message: 'Match tenants for the gaps you identified' },
    { label: 'Export report', icon: <FileText size={14} />, message: 'Export this analysis as a PDF report' },
  ],
  'tenant-match': [
    { label: 'Create outreach campaign', icon: <Mail size={14} />, message: 'Create an outreach campaign for the matched tenants' },
  ],
  outreach: [
    { label: 'Review & send', icon: <Mail size={14} />, message: 'Review and send the outreach campaign' },
    { label: 'Save as template', icon: <Save size={14} />, message: 'Save this outreach as a reusable template' },
  ],
};

// Context-specific suggestion sets for different entry points
const CONTEXT_SUGGESTIONS: Record<string, { title: string; desc: string; icon: string }[]> = {
  outreach: [
    { title: 'Draft outreach', desc: 'Create a personalized email for a tenant', icon: '✉️' },
    { title: 'Analyze property', desc: 'Find tenant gaps at a specific site', icon: '🏢' },
    { title: 'Match tenants', desc: 'Find the best prospects for your space', icon: '🛍️' },
    { title: 'Market comps', desc: 'Compare recent leasing data in the area', icon: '📊' },
  ],
  pipeline: [
    { title: 'Analyze property', desc: 'Run a full analysis on this deal', icon: '🏢' },
    { title: 'Market comps', desc: 'Compare recent leasing data in the area', icon: '📊' },
    { title: 'Draft outreach', desc: 'Create a personalized email for a tenant', icon: '✉️' },
    { title: 'Match tenants', desc: 'Find the best prospects for your space', icon: '🛍️' },
  ],
  // Shown inside a property project's chat — tailored to the uploaded property + docs
  project: [
    { title: 'Run a void analysis', desc: 'Find the tenant gaps at this property', icon: '🛍️' },
    { title: 'Summarize demographics', desc: 'Trade-area population, income, and spending', icon: '📊' },
    { title: 'Draft an investment memo', desc: 'A first-pass memo from the uploaded docs', icon: '📝' },
    { title: 'Draft tenant outreach', desc: 'Email the tenants worth pursuing', icon: '✉️' },
  ],
};

const DEFAULT_SUGGESTIONS = [
  { title: 'Analyze property', desc: 'Find tenant gaps at a specific site', icon: '🏢' },
  { title: 'Match tenants', desc: 'Find the best prospects for your space', icon: '🛍️' },
  { title: 'Market comps', desc: 'Compare recent leasing data in the area', icon: '📊' },
  { title: 'Draft outreach', desc: 'Create a personalized email for a tenant', icon: '✉️' },
];

export function ChatContainer({ initialSessionId, chatContext, projectId }: ChatContainerProps) {
  const location = useLocation();
  const locationState = location.state as LocationState | null;
  // Track selected vertical mode for new conversations
  const [selectedMode, setSelectedMode] = useState<VerticalModeId>("MASTER_DEFAULT");

  // Use the new simplified useChat hook
  const {
    messages,
    workflowSteps,
    isProcessing,
    activeAgentType,
    isConnected,
    isLoading,
    sendMessage,
    cancelInflight,
    reloadContext,
    currentSessionId,
  } = useChat(initialSessionId, selectedMode, projectId);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialMessageSentRef = useRef(false);
  const processingStartRef = useRef<number>(0);
  const prevProcessingRef = useRef(false);
  const prevWorkflowStepsRef = useRef(workflowSteps);
  // Show the work log card while processing — keep it visible until an
  // agent message in the CURRENT turn has real content (text has streamed in).
  // Only check messages after the last user message to avoid prior turns
  // making the indicator vanish on follow-up questions.
  const showThinkingIndicator = (() => {
    if (!isProcessing) return false;
    // Find the last user message index — current turn starts after it
    let lastUserIdx = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') { lastUserIdx = i; break; }
    }
    // Check if any agent message AFTER the last user message has content
    for (let i = lastUserIdx + 1; i < messages.length; i++) {
      if (messages[i].role === 'agent' && messages[i].content.trim().length > 0) {
        return false;
      }
    }
    return true;
  })();

  // Track processing start time and attach receipt when processing ends
  useEffect(() => {
    if (isProcessing && !prevProcessingRef.current) {
      // Processing just started — record timestamp and snapshot steps
      processingStartRef.current = Date.now();
    }
    if (!isProcessing && prevProcessingRef.current) {
      // Processing just ended — attach a receipt to the last agent message
      const elapsed = Math.max(1, Math.round((Date.now() - processingStartRef.current) / 1000));
      const completedSteps = prevWorkflowStepsRef.current.filter((s) => s.status === 'completed');
      const agentNames = completedSteps
        .map((s) => AGENTS[s.agentType]?.name ?? s.agentType)
        .filter((n) => n !== 'Space Goose Assistant'); // exclude orchestrator
      if (agentNames.length > 0) {
        // Find the last agent message and attach the receipt
        for (let i = messages.length - 1; i >= 0; i--) {
          const msg = messages[i];
          if (msg.role === 'agent' && !msg.receipt) {
            // Use the store's updateMessage directly
            const { updateMessage } = useChatStore.getState();
            updateMessage(msg.id, { receipt: { agents: agentNames, seconds: elapsed } });
            break;
          }
        }
      }
    }
    prevProcessingRef.current = isProcessing;
    prevWorkflowStepsRef.current = workflowSteps;
  }, [isProcessing, messages, workflowSteps]);

  // Determine next-step actions based on the last agent message
  const nextStepActions = useMemo(() => {
    if (isProcessing || messages.length === 0) return null;
    // Find the last agent message
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role === 'agent' && msg.agentType && !msg.isStreaming) {
        return NEXT_STEP_ACTIONS[msg.agentType] || null;
      }
    }
    return null;
  }, [messages, isProcessing]);

  // Detect if a restored session ended with a question (show "Continue" button)
  const showContinueButton = useMemo(() => {
    if (isProcessing || messages.length === 0 || !initialSessionId) return false;
    // Find the last agent/assistant message
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role === 'agent') {
        const content = msg.content.trim();
        // Check if it ends with a question or an actionable prompt
        return content.endsWith('?') ||
          content.toLowerCase().includes('would you like') ||
          content.toLowerCase().includes('shall i') ||
          content.toLowerCase().includes('want me to');
      }
      if (msg.role === 'user') break; // User already responded — no need for continue button
    }
    return false;
  }, [messages, isProcessing, initialSessionId]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Handle initial message from navigation state (e.g., from Documents page)
  useEffect(() => {
    if (
      locationState?.initialMessage &&
      isConnected &&
      !initialMessageSentRef.current
    ) {
      initialMessageSentRef.current = true;
      const timer = setTimeout(() => {
        sendMessage(locationState.initialMessage!);
        window.history.replaceState({}, document.title);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [locationState?.initialMessage, isConnected, sendMessage]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isProcessing]);

  // Whether the user has sent a message during this mount — the nudge only
  // shows on a restored chat the user hasn't picked back up yet.
  const [userSentThisSession, setUserSentThisSession] = useState(false);

  const handleSendMessage = useCallback((content: string) => {
    setUserSentThisSession(true);
    sendMessage(content);
  }, [sendMessage]);

  const navigate = useNavigate();
  const { data: aiConfig } = useAIConfig();
  const [byokDismissed, setByokDismissed] = useState(false);
  const [draft, setDraft] = useState<string | undefined>(undefined);
  const [draftNonce, setDraftNonce] = useState(0);
  const userMessageCount = messages.filter((m) => m.role === 'user').length;
  const showByokNudge = !byokDismissed && !aiConfig?.has_byok_key && userMessageCount >= 5;

  const handleStarterClick = useCallback((title: string) => {
    setDraft(`${title}: `);
    setDraftNonce((n) => n + 1);
  }, []);

  // ---- Save to project (chat promotion) ----------------------------------
  // The promote affordances only apply to the free-form chat surface. Project
  // chats (ProjectChatPage passes `projectId`) already have project context and
  // their own header, so the whole flow is suppressed there.
  const isProjectRoute = !!projectId;
  const { sessions } = useChatSessions();
  const sessionIdForPromote = currentSessionId ?? initialSessionId ?? null;
  const sessionMeta = sessions.find((s) => s.id === sessionIdForPromote);
  // Locally-remembered promotion so the header flips instantly after the modal
  // succeeds, before the sessions query refetches.
  const [promotedTo, setPromotedTo] = useState<{ id: string; name: string } | null>(null);
  const effectiveProjectId = promotedTo?.id ?? sessionMeta?.project_id ?? null;
  const effectiveProjectName = promotedTo?.name ?? sessionMeta?.project_name ?? null;

  const [promoteOpen, setPromoteOpen] = useState(false);
  const nudgeKey = `spacegoose:promote-nudge-dismissed:${initialSessionId ?? 'new'}`;
  const [nudgeDismissed, setNudgeDismissed] = useState(() => {
    try {
      return sessionStorage.getItem(nudgeKey) === '1';
    } catch {
      return false;
    }
  });
  const dismissNudge = useCallback(() => {
    setNudgeDismissed(true);
    try {
      sessionStorage.setItem(nudgeKey, '1');
    } catch {
      /* sessionStorage unavailable — dismissal stays in-memory */
    }
  }, [nudgeKey]);

  const promoteCtx: PromoteChatContext = {
    inProject: isProjectRoute || !!effectiveProjectId,
    hasMessages: messages.length > 0,
    messageCount: messages.length,
    isProcessing,
    userSentThisSession,
    nudgeDismissed,
  };
  const headerState = headerMode(promoteCtx);
  const footnoteVariant = composerFootnoteVariant(promoteCtx);

  return (
    <div className="flex flex-col h-full bg-transparent">
      {/* BYOK nudge */}
      {showByokNudge && (
        <div className="flex-shrink-0 px-4 py-2 bg-[var(--accent)]/5 border-b border-[var(--accent)]/20 flex items-center gap-2 text-xs text-[var(--accent)]">
          <Key size={12} />
          <span>Add your own Anthropic key for unmetered usage.</span>
          <button
            onClick={() => navigate('/settings')}
            className="underline hover:no-underline font-medium"
          >
            Add key
          </button>
          <button
            onClick={() => setByokDismissed(true)}
            className="ml-auto text-industrial-muted hover:text-industrial"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Connection status is shown in the header dot — no banner needed */}

      {/* Chat header — scope pill + promote button (free-form surface only) */}
      {!isProjectRoute && headerState !== 'hidden' && (
        <div className="flex-shrink-0 flex items-center gap-3 px-4 sm:px-5 py-2.5 border-b border-[var(--border-subtle)]">
          <h1 className="text-sm font-semibold text-industrial truncate">
            {sessionMeta?.title || 'Chat'}
          </h1>
          {headerState === 'project' ? (
            <span
              className="flex-shrink-0 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[var(--accent-subtle)] text-[var(--accent)] truncate max-w-[200px]"
              title={effectiveProjectName ?? undefined}
            >
              In: {effectiveProjectName}
            </span>
          ) : (
            <span className="flex-shrink-0 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[var(--bg-tertiary)] text-industrial-muted">
              Free-form
            </span>
          )}
          {shouldShowSaveButton(promoteCtx) && (
            <button
              onClick={() => setPromoteOpen(true)}
              className="ml-auto flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border-strong)] text-[13px] font-medium text-industrial hover:bg-[var(--bg-tertiary)] transition-colors"
            >
              <Layers size={13} />
              Save to project
            </button>
          )}
        </div>
      )}

      {/* Loading state is handled inline in the messages area */}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-3 sm:px-5 py-6 scrollbar-thin">
        <div className="chat-stage">
        {messages.length === 0 && isProcessing ? (
          /* Centered analysis processing view */
          <AnalysisProcessingView
            workflowSteps={workflowSteps}
            activeAgentType={activeAgentType as AgentType | null}
            isProcessing={isProcessing}
            analysisTarget={
              messages.find((m) => m.role === 'user')?.content?.slice(0, 60) || null
            }
          />
        ) : messages.length === 0 && !isLoading ? (
          <div className="flex flex-col items-center justify-center min-h-[60vh] text-center max-w-2xl mx-auto animate-fade-in">
            <img
              src="/mascots/goose-planner.webp"
              alt=""
              aria-hidden="true"
              className="w-28 h-28 mb-4 object-contain select-none"
              draggable={false}
            />

            <h2 className="font-display text-3xl font-bold tracking-tight text-industrial mb-2">
              How can I help you today?
            </h2>
            <p className="text-sm text-industrial-secondary mb-10 max-w-md">
              Ask anything about your markets, properties, or prospects — or pick a starting point.
            </p>

            {/* Context-Aware Suggestion Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full px-4">
              {(chatContext ? CONTEXT_SUGGESTIONS[chatContext] || DEFAULT_SUGGESTIONS : DEFAULT_SUGGESTIONS).map((s) => (
                <button
                  key={s.title}
                  onClick={() => handleStarterClick(s.title)}
                  disabled={!isConnected}
                  className="flex flex-col items-start p-4 rounded-xl border border-[var(--border-default)] hover:bg-[var(--bg-secondary)] hover:border-[var(--border-strong)] transition-all text-left group"
                >
                  <span className="text-lg mb-1">{s.icon}</span>
                  <span className="text-sm font-medium text-industrial">{s.title}</span>
                  <span className="text-xs text-industrial-muted group-hover:text-industrial-secondary">{s.desc}</span>
                </button>
              ))}
            </div>

            {/* Subtle Assistant Mode Picker */}
            <div className="mt-12 flex items-center gap-2 p-1 bg-[var(--bg-tertiary)] rounded-lg">
              {VERTICAL_MODES.slice(0, 3).map((mode) => (
                <button
                  key={mode.id}
                  onClick={() => setSelectedMode(mode.id)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                    selectedMode === mode.id
                      ? 'bg-[var(--bg-primary)] text-industrial shadow-sm'
                      : 'text-industrial-muted hover:text-industrial-secondary'
                  }`}
                >
                  {mode.label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 12 }} className="pb-10">
            {messages.map((message) => {
              // Hide the empty streaming agent bubble while the work log
              // card is visible — it would duplicate the indicator.
              if (
                showThinkingIndicator &&
                message.role === 'agent' &&
                message.isStreaming &&
                !message.content
              ) {
                return null;
              }
              return (
                <ChatMessage
                  key={message.id}
                  message={message}
                />
              );
            })}

            <ThinkingIndicator
              isVisible={showThinkingIndicator}
              activeAgentType={activeAgentType as AgentType | null}
              workflowSteps={workflowSteps}
            />

            {/* Continue analysis button for resumed sessions */}
            {showContinueButton && !nextStepActions && (
              <div className="chat-stage px-4 py-2 animate-fade-in">
                <div className="flex pl-11 sm:pl-13">
                  <button
                    onClick={() => handleSendMessage('Yes, please continue')}
                    disabled={!isConnected}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-sm font-medium transition-all shadow-sm"
                  >
                    <ArrowRight size={14} />
                    Continue this analysis
                  </button>
                </div>
              </div>
            )}

            {/* Next-step action cards */}
            {nextStepActions && (
              <div className="chat-stage px-4 py-2 animate-fade-in">
                <div className="flex flex-wrap gap-2 pl-11 sm:pl-13">
                  {nextStepActions.map((action) => (
                    <button
                      key={action.label}
                      onClick={() => handleSendMessage(action.message)}
                      disabled={!isConnected}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-[var(--accent)]/30 bg-[var(--accent-subtle)] hover:bg-[var(--accent)]/15 hover:border-[var(--accent)]/50 text-sm font-medium text-[var(--accent)] transition-all"
                    >
                      {action.icon}
                      {action.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Inline nudge — offer to ground the free-form chat in a project */}
            {shouldShowNudge(promoteCtx) && (
              <div className="px-1 py-1">
                <PromoteNudge
                  onPromote={() => setPromoteOpen(true)}
                  onDismiss={dismissNudge}
                />
              </div>
            )}

            {/* Save void/matchmaker tenant suggestions as Contacts */}
            <TenantSavePanel key={currentSessionId ?? 'none'} />

            {/* Export bar — show when analysis is complete and session exists */}
            {!isProcessing && messages.length >= 3 && currentSessionId && (
              <div className="chat-stage px-4 py-2">
                <ExportBar sessionId={currentSessionId} />
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
        </div>
      </div>

      {/* Agent Status Strip removed — the work log card + receipt line replace it */}

      {/* Input Area */}
      <div className="chat-input-shell flex-shrink-0 px-3 sm:px-5 py-4 border-t border-[var(--border-subtle)]">
        <div className="chat-stage">
          {isProcessing && (
            <div className="flex justify-center mb-3">
              <button
                type="button"
                onClick={cancelInflight}
                className="flex items-center gap-2 px-4 py-1.5 rounded-full border border-[var(--border-subtle)] bg-[var(--surface-elevated)] text-sm text-industrial-secondary hover:text-industrial-primary hover:border-industrial-primary transition-colors"
                aria-label="Stop generating"
                title="Stop generating"
              >
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 12 12"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <rect x="2" y="2" width="8" height="8" rx="1" />
                </svg>
                Stop generating
              </button>
            </div>
          )}
          <ChatInput
            onSend={handleSendMessage}
            disabled={!isConnected || isProcessing}
            draft={draft}
            draftNonce={draftNonce}
            placeholder={
              !isConnected
                ? 'Server offline — start the backend to chat'
                : isProcessing
                ? 'Space Goose is working\u2026'
                : 'Message Space Goose...'
            }
          />
          <p className="text-xs text-industrial-muted mt-3 text-center">
            {isProcessing ? (
              'AI agents are working on your request'
            ) : footnoteVariant === 'none' ? (
              'Enter to send, Shift+Enter for a new line'
            ) : footnoteVariant === 'new' ? (
              'No project context.'
            ) : (
              <>
                No project context. Citations will pull from external sources
                only ·{' '}
                <button
                  onClick={() => setPromoteOpen(true)}
                  className="text-[var(--accent)] hover:underline"
                >
                  Save to project
                </button>{' '}
                to ground in your uploaded data.
              </>
            )}
          </p>
        </div>
      </div>

      {/* Promote-to-project modal */}
      {promoteOpen && sessionIdForPromote && (
        <PromoteModal
          sessionId={sessionIdForPromote}
          onClose={() => setPromoteOpen(false)}
          onPromoted={(project) => {
            // Flip the header pill immediately, then reconnect the socket so the
            // next turn is grounded in the just-attached project's data (the
            // server caches session context per-connection).
            setPromotedTo(project);
            reloadContext();
          }}
        />
      )}
    </div>
  );
}
