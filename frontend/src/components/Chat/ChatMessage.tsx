import type { Message } from '../../types/chat';
import { AGENTS } from '../../types/chat';
import { MarkdownRenderer } from './MarkdownRenderer';

interface ChatMessageProps {
  message: Message;
  variant?: 'bubble' | 'card'; // bubble = chat style, card = full-width dashboard style
}

export function ChatMessage({ message, variant = 'bubble' }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const agent = message.agentType ? AGENTS[message.agentType] : null;

  // On desktop with card variant, agent messages are full-width cards
  // User messages stay as small bubbles on the right
  if (variant === 'card' && !isUser) {
    return (
      <div className="mb-6">
        <div className="bg-gray-800/50 rounded-xl border border-gray-700/50 overflow-hidden">
          {/* Card Header with agent info */}
          {agent && (
            <div className="flex items-center gap-3 px-5 py-3 bg-gray-800/80 border-b border-gray-700/50">
              <span
                className={`w-3 h-3 rounded-full ${agent.color} ${
                  message.isStreaming ? 'animate-pulse' : ''
                }`}
              />
              <span className="font-medium text-gray-200">
                {agent.name}
              </span>
              {message.isStreaming && (
                <span className="text-xs text-gray-500 ml-2">analyzing...</span>
              )}
              <span className="ml-auto text-xs text-gray-500">
                {message.timestamp.toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>
          )}

          {/* Card Content - full width */}
          <div className="p-5">
            <div className="text-sm">
              <MarkdownRenderer
                content={message.content}
                agentType={message.agentType}
              />
              {message.isStreaming && (
                <span className="inline-block w-2 h-4 ml-1 bg-gray-400 animate-pulse" />
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Bubble variant (default) - traditional chat bubbles
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
            ? 'bg-blue-600 text-white rounded-2xl rounded-br-md'
            : isSystem
            ? 'bg-gray-700 text-gray-300 rounded-2xl border border-gray-600'
            : 'bg-gray-800 text-gray-100 rounded-2xl rounded-bl-md border border-gray-700/50'
        } px-4 py-3 sm:px-5 sm:py-4`}
      >
        {!isUser && agent && (
          <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-700">
            <span
              className={`w-2.5 h-2.5 rounded-full ${agent.color} ${
                message.isStreaming ? 'animate-pulse' : ''
              }`}
            />
            <span className="text-sm font-medium text-gray-400">
              {agent.name}
            </span>
            {message.isStreaming && (
              <span className="text-xs text-gray-500 ml-2">typing...</span>
            )}
          </div>
        )}

        {/* Render content - use markdown for agents, plain text for user */}
        {isUser ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>
        ) : (
          <div className="text-sm">
            <MarkdownRenderer
              content={message.content}
              agentType={message.agentType}
            />
            {message.isStreaming && (
              <span className="inline-block w-2 h-4 ml-1 bg-gray-400 animate-pulse" />
            )}
          </div>
        )}

        <div
          className={`text-xs mt-3 ${
            isUser ? 'text-blue-200' : 'text-gray-500'
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
}
