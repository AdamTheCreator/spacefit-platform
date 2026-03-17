import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { Sparkles, Users, FileText, Mail, Save, ArrowRight, MapPin } from 'lucide-react';
import { useChat } from '../../hooks/useChat';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { AgentStatusStrip } from './AgentStatusStrip';
import { AnalysisProcessingView } from './AnalysisProcessingView';
import { ExportBar } from './ExportBar';
import { ThinkingIndicator } from './ThinkingIndicator';
import type { AgentType } from '../../types/chat';

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
    currentSessionId,
  } = useChat(initialSessionId, selectedMode, projectId);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialMessageSentRef = useRef(false);
  const lastMessage = messages.at(-1);
  const showThinkingIndicator = isProcessing && lastMessage?.role === 'user';

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

  const handleSendMessage = useCallback((content: string) => {
    sendMessage(content);
  }, [sendMessage]);

  return (
    <div className="flex flex-col h-full bg-transparent">
      {/* Connection Status */}
      {!isConnected && (
        <div className="flex-shrink-0 px-4 py-2.5 bg-[var(--bg-warning)] border-b border-[var(--color-warning)]/20" role="status" aria-live="polite">
          <div className="chat-stage flex items-center gap-2 text-sm text-[var(--color-warning)]">
            <span className="w-2 h-2 rounded-full bg-[var(--color-warning)] animate-pulse" />
            Connecting to server...
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && messages.length === 0 && (
        <div className="flex-shrink-0 px-4 py-2.5 bg-[var(--bg-info)] border-b border-[var(--color-info)]/20" role="status" aria-live="polite">
          <div className="chat-stage flex items-center gap-2 text-sm text-[var(--color-info)]">
            <span className="w-2 h-2 rounded-full bg-[var(--color-info)] animate-pulse" />
            Loading conversation...
          </div>
        </div>
      )}

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
            <div className="w-12 h-12 rounded-xl bg-[var(--accent)] text-white flex items-center justify-center mb-8 shadow-lg shadow-[var(--accent)]/20">
              <Sparkles size={24} />
            </div>

            <h2 className="text-3xl font-bold tracking-tight text-industrial mb-10">
              How can I help you today?
            </h2>

            {/* Context-Aware Suggestion Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full px-4">
              {(chatContext ? CONTEXT_SUGGESTIONS[chatContext] || DEFAULT_SUGGESTIONS : DEFAULT_SUGGESTIONS).map((s) => (
                <button
                  key={s.title}
                  onClick={() => handleSendMessage(s.title)}
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
          <div className="space-y-8 pb-10">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}

            <ThinkingIndicator
              isVisible={showThinkingIndicator}
              activeAgentType={activeAgentType as AgentType | null}
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

      {/* Agent Status Strip — hidden when centered processing view is shown */}
      {!(messages.length === 0 && isProcessing) && (
        <AgentStatusStrip
          workflowSteps={workflowSteps}
          activeAgentType={activeAgentType as AgentType | null}
          isProcessing={isProcessing}
          analysisTarget={
            isProcessing && messages.length > 0
              ? messages.find((m) => m.role === 'user')?.content?.slice(0, 60) || null
              : null
          }
        />
      )}

      {/* Input Area */}
      <div className="chat-input-shell flex-shrink-0 px-3 sm:px-5 py-4 border-t border-[var(--border-subtle)]">
        <div className="chat-stage">
          <ChatInput
            onSend={handleSendMessage}
            disabled={!isConnected || isProcessing}
            placeholder={
              !isConnected
                ? 'Connecting to server...'
                : isProcessing
                ? 'Processing your request...'
                : 'Message SpaceFit...'
            }
          />
          <p className="text-xs text-industrial-muted mt-3 text-center">
            {isProcessing
              ? 'AI agents are working on your request'
              : 'Enter to send, Shift+Enter for a new line'}
          </p>
        </div>
      </div>
    </div>
  );
}
