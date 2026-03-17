import { Link } from 'react-router-dom';
import { MessageSquare, Sparkles } from 'lucide-react';
import type { ChatSessionBrief } from '../../types/project';

interface ProjectChatListProps {
  projectId: string;
  sessions: ChatSessionBrief[];
  activeSessionId?: string;
}

export function ProjectChatList({
  projectId,
  sessions,
  activeSessionId,
}: ProjectChatListProps) {
  if (!sessions.length) {
    return (
      <p className="text-xs text-industrial-muted py-2">
        No chats yet. Start a new conversation below.
      </p>
    );
  }

  return (
    <div className="space-y-0.5">
      {sessions.map((session) => {
        const isActive = session.id === activeSessionId;
        const date = new Date(session.updated_at);
        const dateStr = date.toLocaleDateString('en-US', {
          month: 'numeric',
          day: 'numeric',
        });
        const isAnalysis = session.analysis_type || session.title?.startsWith('Analysis:');

        return (
          <Link
            key={session.id}
            to={`/projects/${projectId}/chat/${session.id}`}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
              isActive
                ? 'bg-[var(--bg-tertiary)] text-industrial font-medium'
                : 'text-industrial-secondary hover:bg-[var(--bg-tertiary)]'
            }`}
          >
            {isAnalysis ? (
              <Sparkles size={14} className="text-[var(--accent)] flex-shrink-0" />
            ) : (
              <MessageSquare size={14} className="text-industrial-muted flex-shrink-0" />
            )}
            <span className="flex-1 truncate">
              {session.title || 'New conversation'}
            </span>
            <span className="text-[11px] text-industrial-muted flex-shrink-0">
              {dateStr}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
