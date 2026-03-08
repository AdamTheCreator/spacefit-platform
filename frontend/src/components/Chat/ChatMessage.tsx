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
      <div className="mb-6 animate-fade-in">
        <div className="bg-[var(--bg-elevated)] rounded-xl shadow-sm border border-[var(--border-subtle)] overflow-hidden">
          {/* Card Header with agent info */}
          {agent && (
            <div className="flex items-center gap-3 px-5 py-3 bg-[var(--bg-tertiary)] border-b border-[var(--border-subtle)]">
              <span
                className={`w-2.5 h-2.5 rounded-full ${agent.color} ${
                  message.isStreaming ? 'animate-pulse-soft' : ''
                }`}
              />
              <span className="text-xs font-medium text-industrial">
                {agent.name}
              </span>
              {message.isStreaming && (
                <span className="text-xs text-industrial-muted">Processing...</span>
              )}
              <span className="ml-auto text-xs text-industrial-muted">
                {message.timestamp.toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>
          )}

          {/* Card Content - full width */}
          <div className="p-5">
            <div className="text-sm text-industrial leading-relaxed">
              <MarkdownRenderer
                content={message.content}
                agentType={message.agentType}
              />
              {message.isStreaming && (
                <span className="inline-block w-1.5 h-4 ml-1 bg-[var(--accent)] rounded-sm animate-pulse" />
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Bubble variant (default) - softer chat style with rounded corners
  const widthClasses = isUser
    ? 'max-w-[92%] sm:max-w-[76%] md:max-w-[64%] lg:max-w-[52%]'
    : 'max-w-[97%] sm:max-w-[92%] md:max-w-[88%]';

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-5 animate-fade-in`}
    >
      <div
        className={`${widthClasses} ${
          isUser
            ? 'bg-[var(--accent-subtle)] text-industrial rounded-3xl rounded-br-lg border border-[var(--accent)]/20'
            : isSystem
            ? 'bg-[var(--bg-tertiary)] text-industrial-secondary rounded-3xl rounded-bl-lg border border-[var(--border-subtle)]'
            : 'bg-[var(--bg-elevated)] text-industrial rounded-3xl rounded-bl-lg border border-[var(--border-subtle)]'
        } px-4 py-3 sm:px-5 sm:py-4`}
      >
        {!isUser && agent && (
          <div className="flex items-center gap-2 mb-3 pb-2 border-b border-[var(--border-subtle)]/80">
            <span
              className={`w-2 h-2 rounded-full ${agent.color} ${
                message.isStreaming ? 'animate-pulse-soft' : ''
              }`}
            />
            <span className="text-xs font-medium text-industrial-secondary">
              {agent.name}
            </span>
            {message.isStreaming && (
              <span className="text-xs text-industrial-muted ml-2">Typing...</span>
            )}
          </div>
        )}

        {/* Render content - use markdown for agents, plain text for user */}
        {isUser ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>
        ) : (
          <div className="text-sm leading-relaxed">
            <MarkdownRenderer
              content={message.content}
              agentType={message.agentType}
            />
            {message.isStreaming && (
              <span className="inline-block w-1.5 h-4 ml-1 bg-[var(--accent)] rounded-sm animate-pulse" />
            )}
          </div>
        )}

        <div
          className={`text-[11px] mt-3 ${
            isUser ? 'text-industrial-muted' : 'text-industrial-muted'
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
