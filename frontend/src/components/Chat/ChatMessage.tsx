import { memo } from 'react';
import type { Message } from '../../types/chat';
import { AGENTS } from '../../types/chat';
import { MarkdownRenderer } from './MarkdownRenderer';
import { ThinkingReceipt } from './ThinkingReceipt';

interface ChatMessageProps {
  message: Message;
  /**
   * The user question this agent turn answers, supplied ONLY when the
   * pairing isn't visually adjacent (other bubbles intervene) — keeps
   * delayed/interleaved replies legible.
   */
  answersQuestion?: string | null;
}

export const ChatMessage = memo(function ChatMessage({ message, answersQuestion }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const agent = message.agentType ? AGENTS[message.agentType] : null;
  const quote = !isUser && answersQuestion
    ? answersQuestion.length > 110
      ? `${answersQuestion.slice(0, 110)}…`
      : answersQuestion
    : null;

  return (
    <div className={`w-full group animate-fade-in ${isUser ? '' : 'bg-[var(--bg-secondary)]/50 py-2 rounded-2xl'}`}>
      {!isUser && message.receipt && (
        <ThinkingReceipt receipt={message.receipt} />
      )}
      <div className="chat-stage px-4 py-2">
        <div className="flex gap-4 sm:gap-6">
          {/* Avatar Area */}
          <div className="flex-shrink-0 pt-1">
            {isUser ? (
              <div className="w-7 h-7 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center text-[10px] font-bold text-industrial-secondary">
                U
              </div>
            ) : (
              <img src="/spacegoose-logo.png" alt="" className="w-7 h-7 rounded-full object-cover" />
            )}
          </div>

          {/* Content Area */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-bold text-industrial">
                {isUser ? 'You' : agent?.name || 'Space Goose'}
              </span>
              {!isUser && message.isStreaming && (
                <span className="text-[10px] font-medium text-[var(--accent)] uppercase tracking-wider animate-pulse">
                  {message.content ? 'Streaming...' : 'Thinking...'}
                </span>
              )}
            </div>

            {quote && (
              <div className="mb-2 pl-2 border-l-2 border-[var(--border-subtle)]">
                <span className="text-xs text-industrial-muted italic">
                  Answering: “{quote}”
                </span>
              </div>
            )}

            <div className="text-[15px] text-industrial leading-relaxed prose prose-sm max-w-none">
              {isUser ? (
                <p className="whitespace-pre-wrap">{message.content}</p>
              ) : (
                <MarkdownRenderer
                  content={message.content}
                  agentType={message.agentType}
                />
              )}
              {message.isStreaming && !isUser && (
                <span className="inline-block w-1 h-4 ml-1 bg-[var(--accent)] rounded-full animate-pulse align-middle" />
              )}
            </div>

            {/* Subtle Timestamp */}
            <div className="mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <span className="text-[10px] text-industrial-muted uppercase tracking-tighter">
                {message.timestamp.toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});
