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
    <div className="flex flex-col h-full bg-gray-900">
      {/* Connection Status */}
      {!isConnected && (
        <div className="flex-shrink-0 px-4 py-2 bg-yellow-900/50 border-b border-yellow-700/50">
          <div className="flex items-center gap-2 text-yellow-400 text-sm">
            <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
            Connecting to server...
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && messages.length === 0 && (
        <div className="flex-shrink-0 px-4 py-2 bg-blue-900/30 border-b border-blue-700/30">
          <div className="flex items-center gap-2 text-blue-400 text-sm">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
            Loading conversation...
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-3 sm:px-6 lg:px-8 xl:px-12 py-4">
        {messages.length === 0 && !isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-full bg-gray-800 flex items-center justify-center mb-4">
              <svg
                className="w-8 h-8 text-gray-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
            </div>
            <h2 className="text-xl font-medium text-gray-300 mb-2">
              Welcome to SpaceFit AI
            </h2>
            <p className="text-gray-500 max-w-md mb-4">
              I can help you analyze commercial real estate properties, identify
              tenant opportunities, and send notifications to your clients.
            </p>
            {/* Demo Mode Button */}
            <Link
              to="/demo"
              className="mt-6 mb-4 px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600
                       hover:from-indigo-500 hover:to-purple-500 text-white font-medium
                       rounded-lg transition-all shadow-lg shadow-indigo-500/25
                       hover:shadow-indigo-500/40 flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM14.553 7.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z" />
              </svg>
              View Investor Demo
            </Link>

            <p className="text-gray-600 text-xs mb-4">or start a new conversation</p>

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
                  className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300
                           rounded-full text-sm transition-colors border border-gray-700
                           disabled:opacity-50 disabled:cursor-not-allowed"
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
      <div className="flex-shrink-0 px-3 sm:px-6 lg:px-8 xl:px-12 py-4 border-t border-gray-800">
        <ChatInput
          onSend={handleSendMessage}
          disabled={!isConnected || isProcessing}
          placeholder={
            !isConnected
              ? 'Connecting to server...'
              : isProcessing
              ? 'Agents are working...'
              : 'Ask me about properties, tenant analysis, or client notifications...'
          }
        />
        <p className="text-xs text-gray-600 mt-2 text-center">
          {isProcessing
            ? 'Processing your request with multiple agents...'
            : 'SpaceFit AI coordinates multiple agents to gather real estate intelligence'}
        </p>
      </div>
    </div>
  );
}
