import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { X } from 'lucide-react';
import { useCreateProject, useCreateProjectSession } from '../../hooks/useProjects';

interface CreateProjectModalProps {
  onClose: () => void;
}

// Optional analysis goals the user can toggle on; folded into the project
// instructions so the agent knows how to treat the property.
const GOAL_CHIPS = [
  'Void / tenant-gap analysis',
  'Demographics',
  'Traffic counts',
  'Investment memo',
] as const;

export function CreateProjectModal({ onClose }: CreateProjectModalProps) {
  const [name, setName] = useState('');
  const [propertyAddress, setPropertyAddress] = useState('');
  const [goal, setGoal] = useState('');
  const [selectedGoals, setSelectedGoals] = useState<string[]>([]);
  const navigate = useNavigate();
  const createProject = useCreateProject();
  const createSession = useCreateProjectSession();

  const toggleGoal = (chip: string) =>
    setSelectedGoals((prev) =>
      prev.includes(chip) ? prev.filter((g) => g !== chip) : [...prev, chip]
    );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    const focusLine = selectedGoals.length
      ? `Focus areas: ${selectedGoals.join(', ')}.`
      : '';
    const instructions =
      [goal.trim(), focusLine].filter(Boolean).join('\n\n') || undefined;

    try {
      const project = await createProject.mutateAsync({
        name: name.trim(),
        instructions,
        property_address: propertyAddress.trim() || undefined,
      });

      // When the user chose the investment-memo focus, kick the memo off
      // immediately: open a project chat and auto-send the memo request so
      // they land on a generating memo instead of an empty workspace.
      if (selectedGoals.includes('Investment memo')) {
        try {
          const session = await createSession.mutateAsync(project.id);
          onClose();
          navigate(`/projects/${project.id}/chat/${session.id}`, {
            state: {
              initialMessage: 'Create an investment memo for this property.',
            },
          });
          return;
        } catch {
          // Fall back to the project workspace if session creation fails.
        }
      }

      onClose();
      navigate(`/projects/${project.id}`);
    } catch {
      // Error handled by mutation state
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-md mx-4 bg-[var(--bg-elevated)] rounded-2xl border border-[var(--border-default)] shadow-xl animate-scale-in">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-subtle)]">
          <h2 className="text-base font-semibold text-industrial">
            New project
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-industrial-muted hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-industrial mb-1.5">
              Project name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Westfield Shopping Center"
              className="w-full px-3 py-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-industrial mb-1.5">
              Property address
              <span className="text-industrial-muted font-normal ml-1">
                (optional)
              </span>
            </label>
            <input
              type="text"
              value={propertyAddress}
              onChange={(e) => setPropertyAddress(e.target.value)}
              placeholder="e.g. 12720 Norwalk Blvd, Norwalk, CA 90650"
              className="w-full px-3 py-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-industrial mb-1.5">
              What are you looking for?
              <span className="text-industrial-muted font-normal ml-1">
                (optional)
              </span>
            </label>
            <textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="e.g. I'm leasing this center — find the tenant gaps and the best prospects to backfill the vacant end-cap."
              rows={3}
              className="w-full px-3 py-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors resize-none"
            />
            <p className="mt-2 text-xs text-industrial-muted">
              This steers how the agent treats the property. Add focus areas:
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {GOAL_CHIPS.map((chip) => {
                const active = selectedGoals.includes(chip);
                return (
                  <button
                    key={chip}
                    type="button"
                    onClick={() => toggleGoal(chip)}
                    aria-pressed={active}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                      active
                        ? 'bg-[var(--accent)] text-white border-[var(--accent)]'
                        : 'bg-[var(--bg-secondary)] text-industrial-secondary border-[var(--border-subtle)] hover:border-[var(--accent)]/50'
                    }`}
                  >
                    {chip}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm font-medium text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || createProject.isPending || createSession.isPending}
              className="px-4 py-2 rounded-lg text-sm font-semibold bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createProject.isPending || createSession.isPending ? 'Creating...' : 'Create project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
