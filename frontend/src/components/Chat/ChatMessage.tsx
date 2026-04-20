import { memo } from 'react';
import { Sparkles } from 'lucide-react';
import type { Message } from '../../types/chat';
import { AGENTS } from '../../types/chat';
import { MarkdownRenderer } from './MarkdownRenderer';

interface ChatMessageProps {
  message: Message;
}

export const ChatMessage = memo(function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const agent = message.agentType ? AGENTS[message.agentType] : null;

  return (
    <div className={`w-full group animate-fade-in ${isUser ? '' : 'bg-[var(--bg-secondary)]/50 py-2 rounded-2xl'}`}>
      <div className="chat-stage px-4 py-2">
        <div className="flex gap-4 sm:gap-6">
          {/* Avatar Area */}
          <div className="flex-shrink-0 pt-1">
            {isUser ? (
              <div className="w-7 h-7 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center text-[10px] font-bold text-industrial-secondary">
                U
              </div>
            ) : (
              <div className="w-7 h-7 rounded-lg bg-[var(--accent)] flex items-center justify-center text-white">
                <Sparkles size={14} />
              </div>
            )}
          </div>

          {/* Content Area */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-bold text-industrial">
                {isUser ? 'You' : agent?.name || 'Perigee'}
              </span>
              {!isUser && message.isStreaming && (
                <span className="text-[10px] font-medium text-[var(--accent)] uppercase tracking-wider animate-pulse">
                  Thinking...
                </span>
              )}
            </div>

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
