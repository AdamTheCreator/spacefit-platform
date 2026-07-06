import { memo } from 'react';
import type { Message } from '../../types/chat';
import { MarkdownRenderer } from './MarkdownRenderer';
import { ThinkingReceipt } from './ThinkingReceipt';
import { useAuthStore } from '../../stores/authStore';

interface ChatMessageProps {
  message: Message;
}

function UserAvatar({ size = 26 }: { size?: number }) {
  const user = useAuthStore((s) => s.user);
  const initials =
    (user?.first_name?.[0] ?? '') + (user?.last_name?.[0] ?? '') ||
    user?.email?.[0]?.toUpperCase() ||
    'U';

  if (user?.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt=""
        style={{ width: size, height: size, borderRadius: '50%', objectFit: 'cover', display: 'block', flexShrink: 0 }}
      />
    );
  }

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: 'linear-gradient(135deg, var(--color-orbit), var(--color-mist))',
        color: '#fff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'var(--font-display)',
        fontSize: size * 0.38,
        fontWeight: 600,
        flexShrink: 0,
        lineHeight: 1,
      }}
    >
      {initials}
    </div>
  );
}

export { UserAvatar };

export const ChatMessage = memo(function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="w-full animate-fade-in">
        {/* User message — right-aligned with profile avatar */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'flex-start', gap: 10 }}>
          <div
            style={{
              maxWidth: '70%',
              background: 'var(--color-neutral-900)',
              color: '#fff',
              padding: '9px 14px',
              borderRadius: '14px 14px 4px 14px',
              fontSize: '13.5px',
              lineHeight: 1.5,
            }}
          >
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
          <UserAvatar size={26} />
        </div>
      </div>
    );
  }

  // Agent message — left-aligned with logo avatar
  return (
    <div className="w-full animate-fade-in">
      {message.receipt && <ThinkingReceipt receipt={message.receipt} />}
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        <div style={{ width: 26, height: 26, borderRadius: '50%', flexShrink: 0, overflow: 'hidden' }}>
          <img src="/spacegoose-logo.png" alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
        </div>
        <div style={{ flex: 1, maxWidth: '82%' }}>
          <div
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-default)',
              borderRadius: '14px 14px 14px 4px',
              padding: '10px 14px',
            }}
          >
            <div style={{ fontSize: '13.5px', lineHeight: 1.55 }} className="text-industrial prose prose-sm max-w-none">
              <MarkdownRenderer content={message.content} agentType={message.agentType} />
            </div>
            {message.isStreaming && (
              <span className="inline-block w-1 h-4 ml-1 bg-[var(--accent)] rounded-full animate-pulse align-middle" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
});
