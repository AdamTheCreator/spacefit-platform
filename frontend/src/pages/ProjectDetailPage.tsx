import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  MoreHorizontal,
  Trash2,
  Send,
} from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { toast } from 'sonner';
import { AppLayout } from '../components/Layout/AppLayout';
import { DeleteProjectModal } from '../components/Projects/DeleteProjectModal';
import { ProjectSidebar } from '../components/Projects/ProjectSidebar';
import { ProjectChatList } from '../components/Projects/ProjectChatList';
import {
  useProject,
  useCreateProjectSession,
  useDeleteProject,
} from '../hooks/useProjects';

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { data: project, isLoading } = useProject(projectId || null);
  const createSession = useCreateProjectSession();
  const deleteProject = useDeleteProject();
  const [showMenu, setShowMenu] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [input]);

  const handleSend = async () => {
    if (!input.trim() || !projectId || isSending) return;
    const message = input.trim();
    setIsSending(true);
    try {
      const session = await createSession.mutateAsync(projectId);
      navigate(`/projects/${projectId}/chat/${session.id}`, {
        state: { initialMessage: message },
      });
    } catch {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDelete = async () => {
    if (!projectId || !project) return;
    try {
      await deleteProject.mutateAsync(projectId);
      toast.success(`Deleted "${project.name}"`);
      setShowDeleteConfirm(false);
      navigate('/projects');
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to delete project';
      toast.error(message);
    }
  };

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
      <div className="h-full flex">
        {/* Left — Main content */}
        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
          {/* Header */}
          <div className="px-6 pt-5 pb-2">
            <Link
              to="/projects"
              className="inline-flex items-center gap-1.5 text-xs text-industrial-muted hover:text-industrial transition-colors mb-4"
            >
              <ArrowLeft size={14} />
              All projects
            </Link>

            <div className="flex items-start justify-between">
              <h1 className="text-2xl font-bold text-industrial tracking-tight">
                {project.name}
              </h1>
              <div className="relative flex-shrink-0">
                <button
                  onClick={() => setShowMenu(!showMenu)}
                  className="p-1.5 rounded-lg text-industrial-muted hover:bg-[var(--bg-tertiary)] transition-colors"
                >
                  <MoreHorizontal size={18} />
                </button>
                {showMenu && (
                  <>
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setShowMenu(false)}
                    />
                    <div className="absolute right-0 mt-1 w-44 bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-xl shadow-md z-20 overflow-hidden py-1">
                      <button
                        onClick={() => {
                          setShowMenu(false);
                          setShowDeleteConfirm(true);
                        }}
                        className="flex items-center gap-2 w-full px-4 py-2 text-sm text-[var(--color-error)] hover:bg-[var(--bg-error)] transition-colors"
                      >
                        <Trash2 size={14} />
                        Delete project
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>

            {project.description && (
              <p className="text-sm text-industrial-secondary mt-1">
                {project.description}
              </p>
            )}
          </div>

          {/* Inline chat input */}
          <div className="px-6 py-4">
            <div
              className={`rounded-2xl border transition-all ${
                isSending
                  ? 'border-[var(--accent)]/40 bg-[var(--bg-primary)] opacity-70'
                  : 'border-[var(--border-default)] bg-[var(--bg-primary)] focus-within:border-[var(--border-strong)] focus-within:shadow-md'
              }`}
            >
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="How can I help with this property?"
                disabled={isSending}
                rows={1}
                className="w-full px-4 pt-4 pb-2 bg-transparent text-[15px] text-industrial placeholder:text-industrial-muted resize-none outline-none rounded-t-2xl min-h-[48px] max-h-[160px] scrollbar-thin"
              />
              <div className="flex items-center justify-end px-3 pb-2.5">
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || isSending}
                  className="w-8 h-8 flex items-center justify-center rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:bg-[var(--bg-tertiary)] disabled:text-industrial-muted transition-all"
                >
                  <Send size={16} strokeWidth={2.5} />
                </button>
              </div>
            </div>
          </div>

          {/* Previous chats */}
          <div className="px-6 pb-6">
            {project.sessions.length > 0 ? (
              <div>
                <p className="text-[11px] font-bold text-industrial-muted uppercase tracking-widest mb-2">
                  Chats
                </p>
                <ProjectChatList
                  projectId={project.id}
                  sessions={project.sessions}
                />
              </div>
            ) : (
              <p className="text-xs text-industrial-muted text-center py-4">
                Start a chat to analyze documents, find voids, or build an investment memo.
              </p>
            )}
          </div>
        </div>

        {/* Right — Sidebar */}
        <div className="w-80 flex-shrink-0 hidden lg:block bg-[var(--bg-secondary)] border-l border-[var(--border-subtle)]">
          <ProjectSidebar project={project} />
        </div>
      </div>

      {showDeleteConfirm && (
        <DeleteProjectModal
          project={project}
          isDeleting={deleteProject.isPending}
          onClose={() => {
            if (!deleteProject.isPending) {
              setShowDeleteConfirm(false);
            }
          }}
          onConfirm={handleDelete}
        />
      )}
    </AppLayout>
  );
}
