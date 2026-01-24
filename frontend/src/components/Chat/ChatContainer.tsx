import { useEffect, useRef, useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useChat } from '../../hooks/useChat';
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
}

export function ChatContainer({ initialSessionId }: ChatContainerProps) {
  const location = useLocation();
  const locationState = location.state as LocationState | null;

  // Use the new simplified useChat hook
  const {
    messages,
    workflowSteps,
    isProcessing,
    activeAgentType,
    isConnected,
    isLoading,
    sendMessage,
  } = useChat(initialSessionId);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialMessageSentRef = useRef(false);

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
    <div className="flex flex-col h-full bg-[var(--bg-primary)]">
      {/* Connection Status */}
      {!isConnected && (
        <div className="flex-shrink-0 px-4 py-2.5 bg-[var(--bg-warning)] border-b border-[var(--color-warning)]/20" role="status" aria-live="polite">
          <div className="flex items-center gap-2 text-sm text-[var(--color-warning)]">
            <span className="w-2 h-2 rounded-full bg-[var(--color-warning)] animate-pulse" />
            Connecting to server...
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && messages.length === 0 && (
        <div className="flex-shrink-0 px-4 py-2.5 bg-[var(--bg-info)] border-b border-[var(--color-info)]/20" role="status" aria-live="polite">
          <div className="flex items-center gap-2 text-sm text-[var(--color-info)]">
            <span className="w-2 h-2 rounded-full bg-[var(--color-info)] animate-pulse" />
            Loading conversation...
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 xl:px-12 py-6 scrollbar-thin">
        {messages.length === 0 && !isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-center max-w-xl mx-auto animate-fade-in">
            {/* Welcome graphic - softer, friendlier */}
            <div className="relative mb-8">
              <div className="w-20 h-20 rounded-2xl bg-[var(--accent-subtle)] flex items-center justify-center">
                <div className="w-10 h-10 rounded-xl bg-[var(--accent)] flex items-center justify-center">
                  <svg className="w-5 h-5 text-[var(--color-neutral-900)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </div>
              </div>
            </div>

            <h2 className="text-xl font-semibold text-industrial mb-2">
              Welcome to SpaceFit
            </h2>
            <p className="text-sm text-industrial-secondary max-w-md mb-8 leading-relaxed">
              Your AI-powered commercial real estate assistant. Analyze properties, discover tenant opportunities, and automate outreach.
            </p>

            {/* Demo Mode Button */}
            <Link
              to="/demo"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[var(--accent)] text-[var(--color-neutral-900)] font-medium text-sm hover:bg-[var(--accent-hover)] transition-colors shadow-sm mb-8"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM14.553 7.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z" />
              </svg>
              Watch Demo
            </Link>

            <p className="text-xs font-medium text-industrial-muted uppercase tracking-wide mb-4">Try asking</p>

            <div className="flex flex-wrap gap-2 justify-center">
              {[
                'Analyze a mall property',
                'Find void opportunities',
                'Check foot traffic data',
                'Notify matching clients',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => handleSendMessage(suggestion)}
                  disabled={!isConnected}
                  className="px-4 py-2 rounded-lg text-sm text-industrial-secondary bg-[var(--bg-elevated)] border border-[var(--border-default)] hover:border-[var(--border-strong)] hover:bg-[var(--bg-tertiary)] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Agent Status Strip */}
      <AgentStatusStrip
        workflowSteps={workflowSteps}
        activeAgentType={activeAgentType as AgentType | null}
        isProcessing={isProcessing}
      />

      {/* Input Area */}
      <div className="flex-shrink-0 px-4 sm:px-6 lg:px-8 xl:px-12 py-4 border-t border-[var(--border-subtle)] bg-[var(--bg-secondary)]">
        <ChatInput
          onSend={handleSendMessage}
          disabled={!isConnected || isProcessing}
          placeholder={
            !isConnected
              ? 'Connecting to server...'
              : isProcessing
              ? 'Processing your request...'
              : 'Ask me anything about commercial real estate...'
          }
        />
        <p className="text-xs text-industrial-muted mt-3 text-center">
          {isProcessing
            ? 'AI agents are working on your request'
            : 'Press Enter to send • Shift+Enter for new line'}
        </p>
      </div>
    </div>
  );
}
