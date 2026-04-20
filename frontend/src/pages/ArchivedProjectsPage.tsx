import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Archive, FolderOpen, FileText, MessageSquare, RotateCcw, Trash2, MoreHorizontal } from 'lucide-react';
import { toast } from 'sonner';
import { AppLayout } from '../components/Layout/AppLayout';
import { DeleteProjectModal } from '../components/Projects/DeleteProjectModal';
import { useProjects, useArchiveProject, useDeleteProject } from '../hooks/useProjects';
import type { Project } from '../types/project';

interface ArchivedCardProps {
  project: Project;
  onRestore: (project: Project) => void;
  onDelete: (project: Project) => void;
}

function ArchivedCard({ project, onRestore, onDelete }: ArchivedCardProps) {
  const [showMenu, setShowMenu] = useState(false);
  const archivedDate = new Date(project.updated_at).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });

  return (
    <div className="group relative rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)] transition-all hover:border-[var(--accent)]/30 hover:bg-[var(--bg-tertiary)]">
      <div className="block p-5">
        <div className="mb-3 flex items-start justify-between pr-10">
          <div className="w-9 h-9 rounded-lg bg-[var(--bg-tertiary)] text-industrial-muted flex items-center justify-center">
            <FolderOpen size={18} />
          </div>
          <span className="text-xs text-industrial-muted">{archivedDate}</span>
        </div>
        <h3 className="text-sm font-semibold text-industrial mb-1 truncate">
          {project.name}
        </h3>
        {project.description && (
          <p className="text-xs text-industrial-muted mb-3 line-clamp-2">
            {project.description}
          </p>
        )}
        <div className="flex items-center gap-4 text-xs text-industrial-muted">
          <span className="flex items-center gap-1">
            <FileText size={12} />
            {project.document_count}
          </span>
          <span className="flex items-center gap-1">
            <MessageSquare size={12} />
            {project.session_count}
          </span>
        </div>
      </div>

      <div className="absolute right-3 top-3">
        <button
          onClick={() => setShowMenu((c) => !c)}
          className="rounded-lg p-1.5 text-industrial-muted transition-colors hover:bg-[var(--bg-primary)] hover:text-industrial"
        >
          <MoreHorizontal size={16} />
        </button>

        {showMenu && (
          <>
            <button
              type="button"
              className="fixed inset-0 z-10 cursor-default"
              onClick={() => setShowMenu(false)}
            />
            <div className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] py-1 shadow-md">
              <button
                onClick={() => {
                  setShowMenu(false);
                  onRestore(project);
                }}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm text-industrial-secondary transition-colors hover:bg-[var(--bg-tertiary)]"
              >
                <RotateCcw size={14} />
                Restore project
              </button>
              <button
                onClick={() => {
                  setShowMenu(false);
                  onDelete(project);
                }}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm text-[var(--color-error)] transition-colors hover:bg-[var(--bg-error)]"
              >
                <Trash2 size={14} />
                Delete permanently
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function ArchivedProjectsPage() {
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
  const { data, isLoading } = useProjects({ archived: true });
  const archiveProject = useArchiveProject();
  const deleteProject = useDeleteProject();

  const handleRestore = async (project: Project) => {
    try {
      await archiveProject.mutateAsync({ id: project.id, is_archived: false });
      toast.success(`Restored "${project.name}"`);
    } catch {
      toast.error('Failed to restore project');
    }
  };

  const handleDelete = async () => {
    if (!projectToDelete) return;
    try {
      await deleteProject.mutateAsync(projectToDelete.id);
      toast.success(`Permanently deleted "${projectToDelete.name}"`);
      setProjectToDelete(null);
    } catch {
      toast.error('Failed to delete project');
    }
  };

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[var(--bg-tertiary)] text-industrial-muted flex items-center justify-center">
                <Archive size={20} />
              </div>
              <div>
                <h1 className="text-xl font-bold text-industrial">Archive</h1>
                <p className="text-sm text-industrial-muted mt-0.5">
                  Archived projects can be restored or permanently deleted
                </p>
              </div>
            </div>
            <Link
              to="/projects"
              className="text-sm text-[var(--accent)] font-medium hover:underline"
            >
              Back to projects
            </Link>
          </div>

          {/* Grid */}
          {isLoading ? (
            <div className="flex items-center gap-2 py-12 justify-center">
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:200ms]" />
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:400ms]" />
            </div>
          ) : !data?.items.length ? (
            <div className="text-center py-16">
              <img
                src="/mascots/goose-planet.webp"
                alt=""
                aria-hidden="true"
                className="w-24 h-24 mx-auto mb-3 object-contain select-none opacity-90"
                draggable={false}
              />
              <p className="text-sm text-industrial-muted">
                Nothing in orbit here yet — archived projects will land here when you wrap them up.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.items.map((project) => (
                <ArchivedCard
                  key={project.id}
                  project={project}
                  onRestore={handleRestore}
                  onDelete={setProjectToDelete}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {projectToDelete && (
        <DeleteProjectModal
          project={projectToDelete}
          isDeleting={deleteProject.isPending}
          onClose={() => {
            if (!deleteProject.isPending) setProjectToDelete(null);
          }}
          onConfirm={handleDelete}
        />
      )}
    </AppLayout>
  );
}
