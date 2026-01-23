import { memo } from 'react';
import type { Message } from '../../types/chat';
import { AGENTS } from '../../types/chat';
import { MarkdownRenderer } from './MarkdownRenderer';

interface ChatMessageProps {
  message: Message;
  variant?: 'bubble' | 'card'; // bubble = chat style, card = full-width dashboard style
}

export const ChatMessage = memo(function ChatMessage({ message, variant = 'bubble' }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const agent = message.agentType ? AGENTS[message.agentType] : null;

  // On desktop with card variant, agent messages are full-width cards
  // User messages stay as small bubbles on the right
  if (variant === 'card' && !isUser) {
    return (
      <div className="mb-6">
        <div className="card-industrial p-0 overflow-hidden">
          {/* Card Header with agent info */}
          {agent && (
            <div className="flex items-center gap-3 px-5 py-3 bg-[var(--bg-tertiary)] border-b border-industrial">
              <span
                className={`w-2 h-2 ${agent.color} ${
                  message.isStreaming ? 'animate-pulse-industrial' : ''
                }`}
              />
              <span className="font-mono text-xs font-medium uppercase tracking-wide text-industrial">
                {agent.name}
              </span>
              {message.isStreaming && (
                <span className="label-technical ml-2">processing...</span>
              )}
              <span className="ml-auto font-mono text-[10px] text-industrial-muted">
                {message.timestamp.toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>
          )}

          {/* Card Content - full width */}
          <div className="p-5">
            <div className="text-sm font-mono text-industrial">
              <MarkdownRenderer
                content={message.content}
                agentType={message.agentType}
              />
              {message.isStreaming && (
                <span className="inline-block w-1.5 h-4 ml-1 bg-[var(--accent)] animate-pulse" />
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Bubble variant (default) - industrial chat style
  const widthClasses = isUser
    ? 'max-w-[90%] sm:max-w-[75%] md:max-w-[60%] lg:max-w-[50%] xl:max-w-[40%]'
    : 'max-w-[95%] sm:max-w-[90%] md:max-w-[85%] lg:max-w-[80%]';

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}
    >
      <div
        className={`${widthClasses} ${
          isUser
            ? 'bg-[var(--accent)] text-[var(--color-industrial-900)]'
            : isSystem
            ? 'bg-[var(--bg-tertiary)] text-industrial-secondary border border-industrial'
            : 'bg-[var(--bg-elevated)] text-industrial border border-industrial-subtle'
        } px-4 py-3 sm:px-5 sm:py-4`}
      >
        {!isUser && agent && (
          <div className="flex items-center gap-2 mb-3 pb-2 border-b border-industrial-subtle">
            <span
              className={`w-2 h-2 ${agent.color} ${
                message.isStreaming ? 'animate-pulse-industrial' : ''
              }`}
            />
            <span className="font-mono text-[10px] font-medium uppercase tracking-wide text-industrial-secondary">
              {agent.name}
            </span>
            {message.isStreaming && (
              <span className="label-technical ml-2">typing...</span>
            )}
          </div>
        )}

        {/* Render content - use markdown for agents, plain text for user */}
        {isUser ? (
          <p className="text-sm font-mono leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>
        ) : (
          <div className="text-sm font-mono">
            <MarkdownRenderer
              content={message.content}
              agentType={message.agentType}
            />
            {message.isStreaming && (
              <span className="inline-block w-1.5 h-4 ml-1 bg-[var(--accent)] animate-pulse" />
            )}
          </div>
        )}

        <div
          className={`font-mono text-[10px] mt-3 ${
            isUser ? 'text-[var(--color-industrial-700)]' : 'text-industrial-muted'
          }`}
        >
          {message.timestamp.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  );
});
