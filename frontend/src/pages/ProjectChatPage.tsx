import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Paperclip } from 'lucide-react';
import { AppLayout } from '../components/Layout/AppLayout';
import { ChatContainer } from '../components/Chat';
import { ProjectSidebar } from '../components/Projects/ProjectSidebar';
import { useProject } from '../hooks/useProjects';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/axios';

export function ProjectChatPage() {
  const { projectId, sessionId } = useParams<{
    projectId: string;
    sessionId: string;
  }>();
  const { data: project, isLoading } = useProject(projectId || null);

  // Fetch project imports count
  const { data: projectImports } = useQuery({
    queryKey: ['project-imports', projectId],
    queryFn: async () => {
      const res = await api.get(`/projects/${projectId}/imports`);
      return res.data as { id: string; source: string }[];
    },
    enabled: !!projectId,
    staleTime: 30_000,
  });

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
          {/* Context chip */}
          {(project.documents.length > 0 || (projectImports && projectImports.length > 0)) && (
            <Link
              to={`/projects/${projectId}`}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] text-[11px] text-industrial-muted hover:text-industrial transition-colors ml-auto"
              title="View project data"
            >
              <Paperclip size={12} />
              {[
                project.documents.length > 0 &&
                  `${project.documents.length} doc${project.documents.length !== 1 ? 's' : ''}`,
                projectImports &&
                  projectImports.length > 0 &&
                  `${projectImports.length} import${projectImports.length !== 1 ? 's' : ''}`,
              ]
                .filter(Boolean)
                .join(', ')}
            </Link>
          )}
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
