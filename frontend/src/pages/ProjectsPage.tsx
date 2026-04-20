import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, FolderOpen, FileText, MessageSquare, Search, MoreHorizontal, Trash2, Archive } from 'lucide-react';
import { toast } from 'sonner';
import { AppLayout } from '../components/Layout/AppLayout';
import { CreateProjectModal } from '../components/Projects/CreateProjectModal';
import { DeleteProjectModal } from '../components/Projects/DeleteProjectModal';
import { useDeleteProject, useArchiveProject, useProjects } from '../hooks/useProjects';
import type { Project } from '../types/project';

interface ProjectCardProps {
  project: Project;
  onDelete: (project: Project) => void;
  onArchive: (project: Project) => void;
}

function ProjectCard({ project, onDelete, onArchive }: ProjectCardProps) {
  const updated = new Date(project.updated_at);
  const dateStr = updated.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="group relative rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-secondary)] transition-all hover:border-[var(--accent)]/30 hover:bg-[var(--bg-tertiary)]">
      <Link to={`/projects/${project.id}`} className="block p-5">
        <div className="mb-3 flex items-start justify-between pr-10">
          <div className="w-9 h-9 rounded-lg bg-[var(--accent-subtle)] text-[var(--accent)] flex items-center justify-center">
            <FolderOpen size={18} />
          </div>
          <span className="text-xs text-industrial-muted">{dateStr}</span>
        </div>
        <h3 className="text-sm font-semibold text-industrial mb-1 group-hover:text-[var(--accent)] transition-colors truncate">
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
      </Link>

      <div className="absolute right-3 top-3">
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setShowMenu((current) => !current);
          }}
          className="rounded-lg p-1.5 text-industrial-muted transition-colors hover:bg-[var(--bg-primary)] hover:text-industrial"
        >
          <MoreHorizontal size={16} />
        </button>

        {showMenu && (
          <>
            <button
              type="button"
              aria-label="Close project actions"
              className="fixed inset-0 z-10 cursor-default"
              onClick={() => setShowMenu(false)}
            />
            <div className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] py-1 shadow-md">
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setShowMenu(false);
                  onArchive(project);
                }}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm text-industrial-secondary transition-colors hover:bg-[var(--bg-tertiary)]"
              >
                <Archive size={14} />
                Archive project
              </button>
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setShowMenu(false);
                  onDelete(project);
                }}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm text-[var(--color-error)] transition-colors hover:bg-[var(--bg-error)]"
              >
                <Trash2 size={14} />
                Delete project
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function ProjectsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
  const { data, isLoading } = useProjects({ search: search || undefined });
  const deleteProject = useDeleteProject();
  const archiveProject = useArchiveProject();

  const handleDeleteProject = async () => {
    if (!projectToDelete) return;

    try {
      await deleteProject.mutateAsync(projectToDelete.id);
      toast.success(`Deleted "${projectToDelete.name}"`);
      setProjectToDelete(null);
      navigate('/projects');
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to delete project';
      toast.error(message);
    }
  };

  const handleArchiveProject = async (project: Project) => {
    try {
      await archiveProject.mutateAsync({ id: project.id, is_archived: true });
      toast.success(`Archived "${project.name}"`);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to archive project';
      toast.error(message);
    }
  };

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-xl font-bold text-industrial">Projects</h1>
              <p className="text-sm text-industrial-muted mt-1">
                Organize documents and chats around a property
              </p>
            </div>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--accent)] text-white text-sm font-semibold hover:bg-[var(--accent-hover)] transition-colors shadow-sm"
            >
              <Plus size={16} strokeWidth={2.5} />
              New project
            </button>
          </div>

          {/* Search */}
          <div className="relative mb-6">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-industrial-muted"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search projects..."
              className="w-full pl-9 pr-4 py-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors"
            />
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
                src="/mascots/goose-planner.webp"
                alt=""
                aria-hidden="true"
                className="w-28 h-28 mx-auto mb-3 object-contain select-none"
                draggable={false}
              />
              <p className="text-sm text-industrial-muted mb-4">
                {search
                  ? 'No projects match your search'
                  : 'Kick off your first project and the Planner will take it from there.'}
              </p>
              {!search && (
                <button
                  onClick={() => setShowCreate(true)}
                  className="text-sm text-[var(--accent)] font-medium hover:underline"
                >
                  Create a project
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {data.items.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onDelete={setProjectToDelete}
                  onArchive={handleArchiveProject}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {showCreate && (
        <CreateProjectModal onClose={() => setShowCreate(false)} />
      )}

      {projectToDelete && (
        <DeleteProjectModal
          project={projectToDelete}
          isDeleting={deleteProject.isPending}
          onClose={() => {
            if (!deleteProject.isPending) {
              setProjectToDelete(null);
            }
          }}
          onConfirm={handleDeleteProject}
        />
      )}
    </AppLayout>
  );
}
