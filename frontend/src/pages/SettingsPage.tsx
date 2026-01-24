import { useState } from 'react';
import { AppLayout } from '../components/Layout';
import { Bell, Shield, Palette, Sparkles, Check, Plus, X } from 'lucide-react';
import {
  usePreferences,
  usePreferencesOptions,
  useUpdatePreferences,
  type PreferencesUpdate,
} from '../hooks/usePreferences';

function MultiSelect({
  options,
  selected,
  onChange,
}: {
  options: { value: string; label: string; description?: string }[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          key={option.value}
          onClick={() => toggle(option.value)}
          className={`px-3 py-1.5 text-xs font-medium rounded-full transition-all border ${
            selected.includes(option.value)
              ? 'bg-[var(--accent)] text-[var(--color-neutral-900)] border-[var(--accent)] shadow-sm'
              : 'bg-[var(--bg-tertiary)] text-industrial-secondary border-[var(--border-subtle)] hover:border-[var(--border-default)]'
          }`}
          title={option.description}
        >
          {option.label}
          {selected.includes(option.value) && <Check size={12} className="inline ml-1.5" />}
        </button>
      ))}
    </div>
  );
}

function TagInput({
  tags,
  onChange,
  placeholder,
}: {
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}) {
  const [input, setInput] = useState('');

  const addTag = () => {
    const trimmed = input.trim();
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed]);
      setInput('');
    }
  };

  const removeTag = (tag: string) => {
    onChange(tags.filter((t) => t !== tag));
  };

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-3">
        {tags.map((tag) => (
          <span
            key={tag}
            className="px-3 py-1.5 bg-[var(--accent)]/10 text-[var(--accent)] rounded-full text-xs font-medium flex items-center gap-1.5"
          >
            {tag}
            <button onClick={() => removeTag(tag)} className="hover:text-industrial transition-colors">
              <X size={12} />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
          placeholder={placeholder}
          className="input-industrial flex-1"
        />
        <button
          onClick={addTag}
          className="btn-industrial px-3 py-2"
        >
          <Plus size={16} />
        </button>
      </div>
    </div>
  );
}

function AIPreferencesSection() {
  const { data: options, isLoading: optionsLoading } = usePreferencesOptions();
  const { data: preferences, isLoading: prefsLoading } = usePreferences();
  const updateMutation = useUpdatePreferences();

  const [localPrefs, setLocalPrefs] = useState<PreferencesUpdate>({});
  const [hasChanges, setHasChanges] = useState(false);

  // Merge local changes with fetched preferences
  const currentPrefs = {
    role: localPrefs.role ?? preferences?.role ?? null,
    property_types: localPrefs.property_types ?? preferences?.property_types ?? [],
    tenant_categories: localPrefs.tenant_categories ?? preferences?.tenant_categories ?? [],
    markets: localPrefs.markets ?? preferences?.markets ?? [],
    deal_size_min: localPrefs.deal_size_min ?? preferences?.deal_size_min ?? null,
    deal_size_max: localPrefs.deal_size_max ?? preferences?.deal_size_max ?? null,
    key_tenants: localPrefs.key_tenants ?? preferences?.key_tenants ?? [],
    analysis_priorities: localPrefs.analysis_priorities ?? preferences?.analysis_priorities ?? [],
    custom_notes: localPrefs.custom_notes ?? preferences?.custom_notes ?? null,
  };

  const updateField = <K extends keyof PreferencesUpdate>(
    field: K,
    value: PreferencesUpdate[K]
  ) => {
    setLocalPrefs((prev) => ({ ...prev, [field]: value }));
    setHasChanges(true);
  };

  const saveChanges = async () => {
    await updateMutation.mutateAsync(localPrefs);
    setLocalPrefs({});
    setHasChanges(false);
  };

  if (optionsLoading || prefsLoading) {
    return (
      <div className="card-industrial animate-pulse">
        <div className="h-4 bg-[var(--bg-tertiary)] rounded w-48 mb-4"></div>
        <div className="space-y-3">
          <div className="h-3 bg-[var(--bg-tertiary)] rounded w-full"></div>
          <div className="h-3 bg-[var(--bg-tertiary)] rounded w-3/4"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="card-industrial">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)]/10 flex items-center justify-center">
            <Sparkles size={16} className="text-[var(--accent)]" />
          </div>
          <h2 className="text-sm font-semibold text-industrial">AI Preferences</h2>
        </div>
        {preferences && (
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-24 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
              <div
                className="h-full bg-[var(--accent)] rounded-full transition-all"
                style={{ width: `${preferences.completion_percentage}%` }}
              />
            </div>
            <span className="text-xs text-industrial-muted tabular-nums">
              {preferences.completion_percentage}%
            </span>
          </div>
        )}
      </div>

      <p className="text-sm text-industrial-secondary mb-6 leading-relaxed">
        Help SpaceFit AI understand your business to provide more relevant analysis and recommendations.
      </p>

      <div className="space-y-6">
        {/* Role */}
        <div>
          <label className="text-sm font-medium text-industrial block mb-2">Your Role</label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {options?.roles.map((role) => (
              <button
                key={role.value}
                onClick={() => updateField('role', role.value)}
                className={`p-3 rounded-xl border text-left transition-all ${
                  currentPrefs.role === role.value
                    ? 'border-[var(--accent)] bg-[var(--accent)]/10 text-industrial ring-1 ring-[var(--accent)]/20'
                    : 'border-[var(--border-subtle)] bg-[var(--bg-tertiary)] text-industrial-secondary hover:border-[var(--border-default)]'
                }`}
              >
                <div className="text-xs font-medium">{role.label}</div>
                <div className="text-[11px] text-industrial-muted mt-1">{role.description}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Property Types */}
        <div>
          <label className="text-sm font-medium text-industrial block mb-2">Property Types</label>
          <p className="text-xs text-industrial-muted mb-3">Select all that apply</p>
          <MultiSelect
            options={options?.property_types ?? []}
            selected={currentPrefs.property_types}
            onChange={(v) => updateField('property_types', v)}
          />
        </div>

        {/* Tenant Categories */}
        <div>
          <label className="text-sm font-medium text-industrial block mb-2">Tenant Categories</label>
          <p className="text-xs text-industrial-muted mb-3">What types of tenants do you work with?</p>
          <MultiSelect
            options={options?.tenant_categories ?? []}
            selected={currentPrefs.tenant_categories}
            onChange={(v) => updateField('tenant_categories', v)}
          />
        </div>

        {/* Geographic Markets */}
        <div>
          <label className="text-sm font-medium text-industrial block mb-2">Geographic Markets</label>
          <p className="text-xs text-industrial-muted mb-3">Add the markets you operate in</p>
          <TagInput
            tags={currentPrefs.markets}
            onChange={(v) => updateField('markets', v)}
            placeholder="e.g., Fairfield County, CT"
          />
        </div>

        {/* Deal Size */}
        <div>
          <label className="text-sm font-medium text-industrial block mb-2">Typical Deal Size (SF)</label>
          <div className="flex gap-4">
            <div className="flex-1">
              <label className="text-xs text-industrial-muted block mb-1.5">Min</label>
              <input
                type="number"
                value={currentPrefs.deal_size_min ?? ''}
                onChange={(e) =>
                  updateField('deal_size_min', e.target.value ? parseInt(e.target.value) : null)
                }
                placeholder="1,000"
                className="input-industrial"
              />
            </div>
            <div className="flex-1">
              <label className="text-xs text-industrial-muted block mb-1.5">Max</label>
              <input
                type="number"
                value={currentPrefs.deal_size_max ?? ''}
                onChange={(e) =>
                  updateField('deal_size_max', e.target.value ? parseInt(e.target.value) : null)
                }
                placeholder="50,000"
                className="input-industrial"
              />
            </div>
          </div>
        </div>

        {/* Key Tenants */}
        <div>
          <label className="text-sm font-medium text-industrial block mb-2">Key Tenant Relationships</label>
          <p className="text-xs text-industrial-muted mb-3">
            Tenants you have relationships with or frequently represent
          </p>
          <TagInput
            tags={currentPrefs.key_tenants}
            onChange={(v) => updateField('key_tenants', v)}
            placeholder="e.g., Chick-fil-A, Planet Fitness"
          />
        </div>

        {/* Analysis Priorities */}
        <div>
          <label className="text-sm font-medium text-industrial block mb-2">Analysis Priorities</label>
          <p className="text-xs text-industrial-muted mb-3">What matters most in your analyses?</p>
          <MultiSelect
            options={options?.analysis_priorities ?? []}
            selected={currentPrefs.analysis_priorities}
            onChange={(v) => updateField('analysis_priorities', v)}
          />
        </div>

        {/* Custom Notes */}
        <div>
          <label className="text-sm font-medium text-industrial block mb-2">Additional Context</label>
          <p className="text-xs text-industrial-muted mb-3">
            Any other information that would help the AI assist you better
          </p>
          <textarea
            value={currentPrefs.custom_notes ?? ''}
            onChange={(e) => updateField('custom_notes', e.target.value || null)}
            placeholder="e.g., I specialize in drive-thru enabled sites for QSR tenants..."
            rows={3}
            className="input-industrial resize-none"
          />
        </div>

        {/* Save Button */}
        {hasChanges && (
          <div className="flex justify-end pt-4 border-t border-[var(--border-subtle)]">
            <button
              onClick={saveChanges}
              disabled={updateMutation.isPending}
              className="btn-industrial-primary"
            >
              {updateMutation.isPending ? (
                <>
                  <div className="w-4 h-4 rounded-full border-2 border-[var(--color-neutral-900)] border-t-transparent animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Check size={16} />
                  Save Preferences
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function SettingsPage() {
  return (
    <AppLayout>
      <div className="p-6 max-w-3xl mx-auto bg-[var(--bg-primary)] min-h-full">
        <h1 className="text-xl font-semibold text-industrial mb-6">Settings</h1>

        <div className="space-y-6">
          {/* AI Preferences - Featured at top */}
          <AIPreferencesSection />

          {/* Notifications */}
          <div className="card-industrial">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center">
                <Bell size={16} className="text-industrial-muted" />
              </div>
              <h2 className="text-sm font-semibold text-industrial">Notifications</h2>
            </div>

            <div className="space-y-4">
              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-sm text-industrial-secondary">Email notifications</span>
                <input
                  type="checkbox"
                  defaultChecked
                  className="w-4 h-4 rounded bg-[var(--bg-tertiary)] border-[var(--border-default)] text-[var(--accent)] focus:ring-[var(--accent)] focus:ring-offset-0"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-sm text-industrial-secondary">Analysis complete alerts</span>
                <input
                  type="checkbox"
                  defaultChecked
                  className="w-4 h-4 rounded bg-[var(--bg-tertiary)] border-[var(--border-default)] text-[var(--accent)] focus:ring-[var(--accent)] focus:ring-offset-0"
                />
              </label>

              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-sm text-industrial-secondary">Weekly digest</span>
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded bg-[var(--bg-tertiary)] border-[var(--border-default)] text-[var(--accent)] focus:ring-[var(--accent)] focus:ring-offset-0"
                />
              </label>
            </div>
          </div>

          {/* Security */}
          <div className="card-industrial">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center">
                <Shield size={16} className="text-industrial-muted" />
              </div>
              <h2 className="text-sm font-semibold text-industrial">Security</h2>
            </div>

            <div className="space-y-2">
              <button className="w-full text-left px-4 py-3 bg-[var(--bg-tertiary)] hover:bg-[var(--hover-overlay)] border border-[var(--border-subtle)] rounded-xl transition-colors">
                <span className="text-sm font-medium text-industrial">Change password</span>
                <p className="text-xs text-industrial-muted mt-0.5">Update your account password</p>
              </button>

              <button className="w-full text-left px-4 py-3 bg-[var(--bg-tertiary)] hover:bg-[var(--hover-overlay)] border border-[var(--border-subtle)] rounded-xl transition-colors">
                <span className="text-sm font-medium text-industrial">Two-factor authentication</span>
                <p className="text-xs text-industrial-muted mt-0.5">Add an extra layer of security</p>
              </button>

              <button className="w-full text-left px-4 py-3 bg-[var(--bg-tertiary)] hover:bg-[var(--hover-overlay)] border border-[var(--border-subtle)] rounded-xl transition-colors">
                <span className="text-sm font-medium text-industrial">Active sessions</span>
                <p className="text-xs text-industrial-muted mt-0.5">Manage devices where you're logged in</p>
              </button>
            </div>
          </div>

          {/* Appearance */}
          <div className="card-industrial">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center">
                <Palette size={16} className="text-industrial-muted" />
              </div>
              <h2 className="text-sm font-semibold text-industrial">Appearance</h2>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-industrial block mb-2">Theme</label>
                <select className="input-industrial">
                  <option value="dark">Dark (default)</option>
                  <option value="light" disabled>
                    Light (coming soon)
                  </option>
                  <option value="system" disabled>
                    System (coming soon)
                  </option>
                </select>
              </div>
            </div>
          </div>

          {/* Danger Zone */}
          <div className="card-industrial border-[var(--color-error)]/20">
            <h2 className="text-sm font-semibold text-[var(--color-error)] mb-4">Danger Zone</h2>
            <button className="btn-industrial border-[var(--color-error)]/30 text-[var(--color-error)] hover:bg-[var(--bg-error)] transition-colors">
              Delete Account
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
