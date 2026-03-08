import { useEffect, useRef, useCallback, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useChat } from '../../hooks/useChat';
import { useAuthStore } from '../../stores/authStore';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { AgentStatusStrip } from './AgentStatusStrip';
import type { AgentType } from '../../types/chat';

interface ChatContainerProps {
  initialSessionId?: string;
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
  { id: "MALL_RETAIL", emoji: "🛍️", label: "Mall & Retail", desc: "Tenant mix and void analysis" },
  { id: "OFFICE_SPACE", emoji: "💼", label: "Office Space", desc: "Leasing and market comps" },
  { id: "INDUSTRIAL", emoji: "🏭", label: "Industrial", desc: "Warehouse and logistics" },
] as const;

type VerticalModeId = typeof VERTICAL_MODES[number]['id'];

export function ChatContainer({ initialSessionId }: ChatContainerProps) {
  const location = useLocation();
  const locationState = location.state as LocationState | null;
  const user = useAuthStore(state => state.user);

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
  } = useChat(initialSessionId, selectedMode);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialMessageSentRef = useRef(false);
  const isAnalysisKickoff = !!locationState?.documentId;

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
  }, [messages]);

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
        {messages.length === 0 && !isLoading && isAnalysisKickoff ? (
          /* Analysis kickoff loading state */
          <div className="flex flex-col items-center justify-center h-full text-center max-w-md mx-auto animate-fade-in">
            <div className="relative mb-6">
              <div className="w-16 h-16 rounded-2xl bg-[var(--accent-subtle)] flex items-center justify-center">
                <div className="w-8 h-8 rounded-xl bg-[var(--accent)] flex items-center justify-center">
                  <svg className="w-4 h-4 text-[var(--color-neutral-900)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
              </div>
              <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-[var(--accent)] flex items-center justify-center">
                <div className="w-3 h-3 rounded-full border-2 border-[var(--color-neutral-900)] border-t-transparent animate-spin" />
              </div>
            </div>
            <h3 className="text-base font-semibold text-industrial mb-2">
              {!isConnected ? 'Connecting...' : 'Starting Analysis'}
            </h3>
            <p className="text-sm text-industrial-muted">
              {!isConnected
                ? 'Establishing connection to the AI engine...'
                : 'Initializing void analysis with your document data...'}
            </p>
            <div className="flex gap-1 mt-4">
              <span className="w-1.5 h-1.5 bg-[var(--accent)] rounded-full animate-pulse" />
              <span className="w-1.5 h-1.5 bg-[var(--accent)] rounded-full animate-pulse [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 bg-[var(--accent)] rounded-full animate-pulse [animation-delay:300ms]" />
            </div>
          </div>
        ) : messages.length === 0 && !isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-center max-w-2xl mx-auto animate-fade-in rounded-3xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)]/70 px-6 py-10 sm:px-10">
            <div className="w-14 h-14 rounded-2xl bg-[var(--accent-subtle)] border border-[var(--accent)]/20 flex items-center justify-center mb-5">
              <div className="w-2.5 h-2.5 rounded-full bg-[var(--accent)]" />
            </div>

            <h2 className="text-2xl font-semibold tracking-tight text-industrial mb-2">
              SpaceFit Assistant
            </h2>
            <p className="text-sm text-industrial-secondary max-w-lg mb-8 leading-relaxed">
              Ask for site analysis, tenant matching, deal support, or outreach. Responses are grounded in your workspace data.
            </p>

            {/* Demo Mode Button */}
            {user?.is_admin && (
              <Link
                to="/demo"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--bg-tertiary)] text-industrial font-medium text-sm hover:bg-[var(--hover-overlay)] transition-colors border border-[var(--border-default)] mb-8"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM14.553 7.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z" />
                </svg>
                Watch Demo
              </Link>
            )}

            {/* Vertical Mode Picker */}
            <p className="text-xs font-medium text-industrial-muted uppercase tracking-wide mb-3">Assistant Mode</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 mb-8 w-full max-w-2xl">
              {VERTICAL_MODES.map((mode) => (
                <button
                  key={mode.id}
                  onClick={() => setSelectedMode(mode.id)}
                  className={`flex flex-col items-center p-3 rounded-xl border transition-all text-center ${
                    selectedMode === mode.id
                      ? 'border-[var(--accent)] bg-[var(--accent-subtle)]'
                      : 'border-[var(--border-default)] bg-[var(--bg-elevated)] hover:border-[var(--border-strong)]'
                  }`}
                >
                  <span className="text-2xl mb-1">{mode.emoji}</span>
                  <span className={`text-xs font-medium ${
                    selectedMode === mode.id ? 'text-[var(--accent)]' : 'text-industrial'
                  }`}>
                    {mode.label}
                  </span>
                  <span className="text-[10px] text-industrial-muted mt-0.5 leading-tight">
                    {mode.desc}
                  </span>
                </button>
              ))}
            </div>

            <p className="text-xs font-medium text-industrial-muted uppercase tracking-wide mb-4">Try asking</p>

            <div className="flex flex-wrap gap-2 justify-center">
              {[
                'Analyze this property',
                'Find tenant gaps',
                'Compare nearby demand',
                'Draft outreach',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => handleSendMessage(suggestion)}
                  disabled={!isConnected}
                  className="px-4 py-2 rounded-full text-sm text-industrial-secondary bg-[var(--bg-elevated)] border border-[var(--border-default)] hover:border-[var(--border-strong)] hover:bg-[var(--hover-overlay)] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  {suggestion}
                </button>
              ))}
            </div>

            <p className="text-xs text-industrial-muted mt-6">
              Need help?{' '}
              <a
                href="mailto:support-spacefit@agentmail.to"
                className="underline hover:text-industrial-secondary transition-colors"
              >
                Contact support
              </a>
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
        </div>
      </div>

      {/* Agent Status Strip */}
      <AgentStatusStrip
        workflowSteps={workflowSteps}
        activeAgentType={activeAgentType as AgentType | null}
        isProcessing={isProcessing}
      />

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
