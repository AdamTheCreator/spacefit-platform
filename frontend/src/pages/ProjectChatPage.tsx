import { useParams, Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { AppLayout } from '../components/Layout/AppLayout';
import { ChatContainer } from '../components/Chat';
import { ProjectSidebar } from '../components/Projects/ProjectSidebar';
import { useProject } from '../hooks/useProjects';

export function ProjectChatPage() {
  const { projectId, sessionId } = useParams<{
    projectId: string;
    sessionId: string;
  }>();
  const { data: project, isLoading } = useProject(projectId || null);

  if (isLoading || !project) {
    return (
      <AppLayout>
        <div className="h-full flex items-center justify-center">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
            <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:200ms]" />
            <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:400ms]" />
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="h-full flex flex-col">
        {/* Top bar with project back-link */}
        <div className="flex items-center gap-3 px-4 py-2.5 border-b border-[var(--border-subtle)]">
          <Link
            to={`/projects/${projectId}`}
            className="p-1.5 rounded-lg text-industrial-muted hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            <ArrowLeft size={18} />
          </Link>
          <span className="text-sm font-semibold text-industrial truncate">
            {project.name}
          </span>
        </div>

        {/* Split: Chat left, Sidebar right */}
        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 min-w-0">
            <ChatContainer
              key={sessionId}
              initialSessionId={sessionId}
              projectId={projectId}
            />
          </div>
          <div className="w-80 flex-shrink-0 hidden lg:block bg-[var(--bg-secondary)] border-l border-[var(--border-subtle)]">
            <ProjectSidebar project={project} />
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
