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
    <div className="flex flex-col h-full bg-industrial">
      {/* Connection Status */}
      {!isConnected && (
        <div className="flex-shrink-0 px-4 py-2 bg-[var(--color-warning)]/10 border-b border-[var(--color-warning)]/30">
          <div className="status-indicator status-indicator-warning">
            Connecting to server...
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && messages.length === 0 && (
        <div className="flex-shrink-0 px-4 py-2 bg-[var(--color-info)]/10 border-b border-[var(--color-info)]/30">
          <div className="status-indicator status-indicator-info">
            Loading conversation...
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-3 sm:px-6 lg:px-8 xl:px-12 py-4 scrollbar-industrial">
        {messages.length === 0 && !isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-center max-w-2xl mx-auto">
            {/* Industrial welcome graphic */}
            <div className="relative mb-8">
              <div className="w-20 h-20 border border-industrial flex items-center justify-center">
                <div className="w-12 h-12 border border-[var(--accent)] flex items-center justify-center">
                  <div className="w-4 h-4 bg-[var(--accent)]" />
                </div>
              </div>
              {/* Corner markers */}
              <div className="absolute -top-1 -left-1 w-2 h-2 border-l border-t border-[var(--accent)]" />
              <div className="absolute -top-1 -right-1 w-2 h-2 border-r border-t border-[var(--accent)]" />
              <div className="absolute -bottom-1 -left-1 w-2 h-2 border-l border-b border-[var(--accent)]" />
              <div className="absolute -bottom-1 -right-1 w-2 h-2 border-r border-b border-[var(--accent)]" />
            </div>

            <h2 className="font-mono text-lg font-bold tracking-tight text-industrial mb-3">
              SpaceFit AI Terminal
            </h2>
            <p className="font-mono text-xs text-industrial-secondary max-w-md mb-6 leading-relaxed">
              Commercial real estate intelligence platform. Analyze properties, identify tenant opportunities, and automate client notifications.
            </p>

            {/* Demo Mode Button */}
            <Link
              to="/demo"
              className="btn-industrial-primary mb-6"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM14.553 7.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z" />
              </svg>
              View Demo
            </Link>

            <div className="label-technical mb-4">Quick Actions</div>

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
                  className="btn-industrial text-[11px] py-1.5 px-3 disabled:opacity-50 disabled:cursor-not-allowed"
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
      <div className="flex-shrink-0 px-3 sm:px-6 lg:px-8 xl:px-12 py-4 border-t border-industrial bg-[var(--bg-elevated)]">
        <ChatInput
          onSend={handleSendMessage}
          disabled={!isConnected || isProcessing}
          placeholder={
            !isConnected
              ? 'Connecting to server...'
              : isProcessing
              ? 'Agents processing...'
              : 'Enter query...'
          }
        />
        <p className="label-technical mt-2 text-center">
          {isProcessing
            ? 'Multi-agent processing in progress'
            : 'AI-powered real estate intelligence'}
        </p>
      </div>
    </div>
  );
}
