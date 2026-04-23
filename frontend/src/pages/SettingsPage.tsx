import { useState } from 'react';
import { AppLayout } from '../components/Layout';
import { Bell, Shield, Palette, Sparkles, Check, Plus, X, Brain, Trash2, Building2, Users, MapPin, Cpu, ChevronDown, ChevronUp, Loader2, AlertCircle, CheckCircle2, Trash, Clock, DollarSign, Gauge } from 'lucide-react';
import {
  usePreferences,
  usePreferencesOptions,
  useUpdatePreferences,
  type PreferencesUpdate,
} from '../hooks/usePreferences';
import { useMemory, useClearMemory } from '../hooks/useMemory';
import {
  useAIConfig,
  useUpdateAIConfig,
  useValidateKey,
  useRemoveKey,
  useProviders,
  useUsage,
  useSpecialistModels,
  useUpdateSpecialistModels,
  type AIConfigUpdate,
} from '../hooks/useAIConfig';
import { useUpdateCredentialScope, type ScopeUpdatePayload } from '../hooks/useCredentialScope';
import { useCredentialAudit, auditActionLabel } from '../hooks/useCredentialAudit';
import { toBYOKUserMessage } from '../lib/byok-errors';

// Shared fallback for sections whose data-fetch failed.
// Avoids the eternal-skeleton bug when the backend is sleepy or offline.
function SectionError({ title, onRetry }: { title: string; onRetry: () => void }) {
  return (
    <div className="card-industrial">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-[var(--bg-error)] flex items-center justify-center shrink-0">
            <AlertCircle size={16} className="text-[var(--color-error)]" />
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-industrial">{title}</h2>
            <p className="text-xs text-industrial-muted mt-0.5">
              Couldn't load from the server. It may be waking up — try again in a few seconds.
            </p>
          </div>
        </div>
        <button onClick={onRetry} className="btn-industrial btn-sm shrink-0">
          Retry
        </button>
      </div>
    </div>
  );
}

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
  const {
    data: options,
    isLoading: optionsLoading,
    isError: optionsError,
    refetch: refetchOptions,
  } = usePreferencesOptions();
  const {
    data: preferences,
    isLoading: prefsLoading,
    isError: prefsError,
    refetch: refetchPrefs,
  } = usePreferences();
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

  // Only fall back to the error card if we have NOTHING to show. If we already
  // have cached options+prefs, keep rendering them through a transient cold-start.
  if ((optionsError && !options) || (prefsError && !preferences)) {
    return (
      <SectionError
        title="AI Preferences"
        onRetry={() => { refetchOptions(); refetchPrefs(); }}
      />
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
        Help Space Goose AI understand your business to provide more relevant analysis and recommendations.
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

function MemorySection() {
  const { data: memory, isLoading, isError, refetch } = useMemory();
  const clearMutation = useClearMemory();
  const [showConfirm, setShowConfirm] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleClear = async () => {
    await clearMutation.mutateAsync();
    setShowConfirm(false);
  };

  const hasMemory = memory && (memory.total_analyses > 0 || memory.book_of_business_summary?.tenant_count);

  // Collapsed summary — what the user sees by default
  const summary = hasMemory
    ? `${memory.total_analyses} analyses · ${memory.analyzed_properties?.length || 0} properties · ${memory.book_of_business_summary?.tenant_count || 0} tenants remembered`
    : 'Nothing remembered yet — starts learning after your first property analysis.';

  return (
    <div className="card-industrial">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        className="w-full flex items-center gap-3 text-left"
      >
        <div className="w-8 h-8 rounded-lg bg-[var(--accent)]/10 flex items-center justify-center shrink-0">
          <Brain size={16} className="text-[var(--accent)]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-industrial">Space Goose Memory</h2>
            <span className="text-[10px] font-semibold tracking-wider uppercase text-industrial-muted px-1.5 py-0.5 rounded bg-[var(--bg-tertiary)]">
              Advanced
            </span>
          </div>
          <p className="text-xs text-industrial-muted mt-0.5 truncate">
            {isLoading ? 'Loading…' : isError ? 'Could not load memory' : summary}
          </p>
        </div>
        <span className={`text-industrial-muted transition-transform ${expanded ? 'rotate-180' : ''}`} aria-hidden="true">
          ▾
        </span>
      </button>

      {expanded && (
        <div className="mt-5 pt-5 border-t border-[var(--border-subtle)]">
          <div className="text-xs text-industrial-secondary leading-relaxed mb-5 space-y-2">
            <p>
              <strong className="text-industrial">What is this?</strong> When you run tenant-gap
              analyses, underwrite properties, or talk to Space Goose about your book of business, it
              quietly saves key facts — the markets you work, the tenant types you care about, the
              properties you've touched — so future answers fit your workflow instead of starting
              from scratch.
            </p>
            <p>
              Memory only updates through normal chat and analysis activity. There's nothing to
              configure here; this panel just shows what's stored and lets you wipe it.
            </p>
          </div>

          {isError && (
            <div className="rounded-xl border border-[var(--color-error)]/30 bg-[var(--bg-error)] px-4 py-3 text-xs text-[var(--color-error)] flex items-center justify-between gap-3">
              <span>Couldn't reach the memory service. The backend may be waking up.</span>
              <button onClick={() => refetch()} className="btn-industrial btn-sm">
                Retry
              </button>
            </div>
          )}

          {!isError && hasMemory && (
            <div className="flex justify-end mb-4">
              <button
                onClick={() => setShowConfirm(true)}
                className="btn-industrial btn-sm text-[var(--color-error)] border-[var(--color-error)]/30 hover:bg-[var(--bg-error)]"
              >
                <Trash2 size={14} />
                Clear Memory
              </button>
            </div>
          )}

          {!isError && !hasMemory && !isLoading && (
            <div className="text-center py-8 bg-[var(--bg-tertiary)] rounded-xl border border-[var(--border-subtle)]">
              <Brain size={32} className="text-industrial-muted mx-auto mb-3" />
              <p className="text-sm text-industrial-muted">No memory yet</p>
              <p className="text-xs text-industrial-muted mt-1">
                It'll fill in automatically as you analyze properties and chat with Space Goose.
              </p>
            </div>
          )}

          {!isError && hasMemory && (
            <div className="space-y-6">
          {/* Stats Grid */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-[var(--bg-tertiary)] rounded-xl p-4 border border-[var(--border-subtle)]">
              <div className="flex items-center gap-2 mb-2">
                <Building2 size={14} className="text-[var(--accent)]" />
                <span className="text-xs text-industrial-muted">Analyses</span>
              </div>
              <div className="text-2xl font-bold text-industrial tabular-nums">
                {memory.total_analyses}
              </div>
            </div>

            <div className="bg-[var(--bg-tertiary)] rounded-xl p-4 border border-[var(--border-subtle)]">
              <div className="flex items-center gap-2 mb-2">
                <MapPin size={14} className="text-[var(--color-success)]" />
                <span className="text-xs text-industrial-muted">Properties</span>
              </div>
              <div className="text-2xl font-bold text-industrial tabular-nums">
                {memory.analyzed_properties?.length || 0}
              </div>
            </div>

            <div className="bg-[var(--bg-tertiary)] rounded-xl p-4 border border-[var(--border-subtle)]">
              <div className="flex items-center gap-2 mb-2">
                <Users size={14} className="text-[var(--color-info)]" />
                <span className="text-xs text-industrial-muted">Tenants</span>
              </div>
              <div className="text-2xl font-bold text-industrial tabular-nums">
                {memory.book_of_business_summary?.tenant_count || 0}
              </div>
            </div>
          </div>

          {/* Recent Properties */}
          {memory.analyzed_properties && memory.analyzed_properties.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-3">
                Recent Properties
              </h3>
              <div className="space-y-2">
                {memory.analyzed_properties.slice(0, 5).map((prop, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-3 bg-[var(--bg-tertiary)] rounded-lg border border-[var(--border-subtle)]"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-industrial truncate">
                        {prop.address}
                      </p>
                      <p className="text-xs text-industrial-muted">
                        {prop.asset_type} &bull; {prop.void_count} gaps
                      </p>
                    </div>
                    <span className="text-[10px] text-industrial-muted flex-shrink-0 ml-4">
                      {new Date(prop.analysis_date).toLocaleDateString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top Categories */}
          {memory.book_of_business_summary?.top_categories && memory.book_of_business_summary.top_categories.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-3">
                Top Tenant Categories
              </h3>
              <div className="flex flex-wrap gap-2">
                {memory.book_of_business_summary.top_categories.slice(0, 8).map((cat) => (
                  <span
                    key={cat}
                    className="px-3 py-1.5 bg-[var(--accent)]/10 text-[var(--accent)] rounded-full text-xs font-medium"
                  >
                    {cat}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Preferred Areas */}
          {memory.preferences?.preferred_trade_areas && memory.preferences.preferred_trade_areas.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-industrial-muted uppercase tracking-wide mb-3">
                Your Markets
              </h3>
              <div className="flex flex-wrap gap-2">
                {memory.preferences.preferred_trade_areas.map((area) => (
                  <span
                    key={area}
                    className="px-3 py-1.5 bg-[var(--bg-success)] text-[var(--color-success)] rounded-full text-xs font-medium"
                  >
                    {area}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Last Updated */}
          {memory.last_updated && (
            <p className="text-xs text-industrial-muted text-right">
              Last updated: {new Date(memory.last_updated).toLocaleDateString()}
            </p>
          )}
            </div>
          )}
        </div>
      )}

      {/* Clear Confirmation Dialog */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-[var(--bg-elevated)] rounded-xl border border-[var(--border-subtle)] p-6 max-w-sm mx-4 shadow-xl">
            <h3 className="text-sm font-semibold text-industrial mb-2">Clear Memory?</h3>
            <p className="text-xs text-industrial-secondary mb-4">
              This will permanently delete all your analysis history, property data, and inferred preferences. Space Goose will start fresh.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowConfirm(false)}
                className="btn-industrial"
              >
                Cancel
              </button>
              <button
                onClick={handleClear}
                disabled={clearMutation.isPending}
                className="btn-industrial bg-[var(--color-error)] text-white border-[var(--color-error)] hover:bg-[var(--color-error)]/90"
              >
                {clearMutation.isPending ? 'Clearing...' : 'Clear Memory'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Provider display names for the effective model badge
const PROVIDER_LABELS: Record<string, string> = {
  anthropic: 'Claude',
  openai: 'OpenAI',
  google: 'Gemini',
  deepseek: 'DeepSeek',
  openai_compatible: 'Custom',
  platform_default: 'Platform',
};

function AIModelSection() {
  const { data: config, isLoading, isError, refetch } = useAIConfig();
  const { data: providers } = useProviders();
  const updateMutation = useUpdateAIConfig();
  const validateMutation = useValidateKey();
  const removeMutation = useRemoveKey();

  const [expanded, setExpanded] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [apiKey, setApiKey] = useState('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [baseUrl, setBaseUrl] = useState('');
  const [validated, setValidated] = useState(false);

  // Initialize form when config loads.
  // If /ai-config failed (or the user is on platform_default), reset the
  // form to a blank slate so the provider dropdown, which is fed by the
  // independent /ai-config/providers endpoint, stays usable even when
  // the saved config can't be read.
  const initForm = () => {
    if (config && config.provider !== 'platform_default') {
      setSelectedProvider(config.provider);
      setSelectedModel(config.model || '');
      setBaseUrl(config.base_url || '');
    } else {
      setSelectedProvider('');
      setSelectedModel('');
      setBaseUrl('');
    }
  };

  const currentProvider = providers?.find((p) => p.id === selectedProvider);
  const showBaseUrl = currentProvider?.requires_base_url;

  const handleProviderChange = (providerId: string) => {
    setSelectedProvider(providerId);
    setApiKey('');
    setValidated(false);
    const provider = providers?.find((p) => p.id === providerId);
    setSelectedModel(provider?.default_model || '');
    setBaseUrl('');
  };

  const handleValidate = async () => {
    if (!selectedProvider || !apiKey) return;
    // Always send the user's selected model. The backend overrides it with
    // a cheap probe model for known providers (anthropic/openai/google/
    // deepseek) to avoid rate-limiting brand-new keys on tier-gated
    // premium models, but for openai_compatible there's no canonical probe
    // model — it falls back to whatever we send and 400s on empty.
    const result = await validateMutation.mutateAsync({
      provider: selectedProvider,
      api_key: apiKey,
      model: selectedModel || undefined,
      base_url: baseUrl || undefined,
    });
    setValidated(result.valid);
  };

  const handleSave = async () => {
    const payload: AIConfigUpdate = {
      provider: selectedProvider,
      model: selectedModel || null,
      api_key: apiKey || undefined,
      base_url: baseUrl || null,
    };
    await updateMutation.mutateAsync(payload);
    setApiKey('');
    setExpanded(false);
  };

  const handleRemoveKey = async () => {
    await removeMutation.mutateAsync();
    setSelectedProvider('');
    setApiKey('');
    setSelectedModel('');
    setBaseUrl('');
    setValidated(false);
    setExpanded(false);
  };

  if (isLoading) {
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

  // When /ai-config fails, keep the section rendered — the provider list
  // comes from a separate endpoint that's still working, and a user with a
  // broken config should still be able to pick a new one. A dismissible
  // warning strip replaces the old full-card error state.
  const configLoadFailed = isError && !config;

  const effectiveLabel = config
    ? `${PROVIDER_LABELS[config.effective_provider] || config.effective_provider} — ${config.effective_model}`
    : configLoadFailed
      ? 'Platform default'
      : 'Loading...';

  return (
    <div className="card-industrial">
      {configLoadFailed && (
        <div className="mb-4 flex items-center gap-2 text-xs px-3 py-2 rounded-lg bg-[var(--bg-error)] text-[var(--color-error)]">
          <AlertCircle size={14} className="shrink-0" />
          <span className="flex-1">
            Couldn't load your saved AI configuration. You can still configure a provider below.
          </span>
          <button
            onClick={() => refetch()}
            className="underline hover:no-underline shrink-0"
          >
            Retry
          </button>
        </div>
      )}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)]/10 flex items-center justify-center">
            <Cpu size={16} className="text-[var(--accent)]" />
          </div>
          <h2 className="text-sm font-semibold text-industrial">AI Model</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-industrial-muted px-2.5 py-1 bg-[var(--bg-tertiary)] rounded-full border border-[var(--border-subtle)]">
            {effectiveLabel}
          </span>
          {config?.has_byok_key && config.is_key_valid && (
            <span className="text-[10px] text-[var(--color-success)] px-2 py-0.5 bg-[var(--bg-success)] rounded-full">
              BYOK
            </span>
          )}
        </div>
      </div>

      <p className="text-sm text-industrial-secondary mb-4 leading-relaxed">
        {config?.has_byok_key
          ? 'Using your own API key. Chat requests go directly to your provider.'
          : 'Using Space Goose\'s built-in AI. Bring your own key to use any provider.'}
      </p>

      {/* Expand/collapse toggle */}
      <button
        onClick={() => {
          setExpanded(!expanded);
          if (!expanded) initForm();
        }}
        className="flex items-center gap-2 text-xs font-medium text-[var(--accent)] hover:text-[var(--accent)]/80 transition-colors"
      >
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        {config?.has_byok_key ? 'Change model configuration' : 'Configure custom model'}
      </button>

      {expanded && (
        <div className="mt-4 pt-4 border-t border-[var(--border-subtle)] space-y-4">
          {/* Provider select */}
          <div>
            <label className="text-sm font-medium text-industrial block mb-2">Provider</label>
            <select
              value={selectedProvider}
              onChange={(e) => handleProviderChange(e.target.value)}
              className="input-industrial"
            >
              <option value="">Select a provider...</option>
              {providers
                ?.filter((p) => p.id !== 'platform_default')
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
            </select>
          </div>

          {/* API key */}
          {selectedProvider && currentProvider?.requires_key && (
            <div>
              <label className="text-sm font-medium text-industrial block mb-2">API Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setValidated(false);
                }}
                placeholder={config?.has_byok_key ? '••••••••••••••••' : 'Enter your API key'}
                className="input-industrial"
              />
            </div>
          )}

          {/* Model select */}
          {selectedProvider && currentProvider && currentProvider.models.length > 0 && (
            <div>
              <label className="text-sm font-medium text-industrial block mb-2">Model</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="input-industrial"
              >
                {currentProvider.models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Base URL (only for custom) */}
          {showBaseUrl && (
            <div>
              <label className="text-sm font-medium text-industrial block mb-2">Base URL</label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.example.com/v1"
                className="input-industrial"
              />
            </div>
          )}

          {/* Validation feedback */}
          {validateMutation.data && (
            <div
              className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg ${
                validateMutation.data.valid
                  ? 'bg-[var(--bg-success)] text-[var(--color-success)]'
                  : 'bg-[var(--bg-error)] text-[var(--color-error)]'
              }`}
            >
              {validateMutation.data.valid ? (
                <CheckCircle2 size={14} />
              ) : (
                <AlertCircle size={14} />
              )}
              {validateMutation.data.valid
                ? `Key validated successfully (${validateMutation.data.model_tested})`
                : validateMutation.data.error}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleValidate}
              disabled={!selectedProvider || !apiKey || validateMutation.isPending}
              className="btn-industrial"
            >
              {validateMutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                'Validate'
              )}
            </button>

            <button
              onClick={handleSave}
              disabled={!validated && !config?.has_byok_key || updateMutation.isPending}
              className="btn-industrial-primary"
            >
              {updateMutation.isPending ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Check size={14} />
                  Save
                </>
              )}
            </button>

            {config?.has_byok_key && (
              <button
                onClick={handleRemoveKey}
                disabled={removeMutation.isPending}
                className="btn-industrial text-[var(--color-error)] border-[var(--color-error)]/30 hover:bg-[var(--bg-error)] ml-auto"
              >
                <Trash size={14} />
                Remove Key
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// --- BYOK v2 sub-sections --------------------------------------------------
//
// Rendered only when the backend returns a v2 `AIConfig` (identified by a
// non-null `id` field). On a v1 backend these components render nothing,
// so the page is safe to ship ahead of the backend feature flag flipping.

function ScopeSection() {
  const { data: config } = useAIConfig();
  const update = useUpdateCredentialScope();

  // Existing scope, with defaults for the input controls.
  const scope = config?.scope ?? {};
  const initialAllowed = (scope.allowed_models ?? []).join(', ');
  const initialRequestCap = scope.monthly_request_cap ?? '';
  const initialSpendCap = scope.monthly_spend_cap_usd ?? '';

  const [allowedRaw, setAllowedRaw] = useState<string>(initialAllowed);
  const [requestCap, setRequestCap] = useState<string>(String(initialRequestCap));
  const [spendCap, setSpendCap] = useState<string>(String(initialSpendCap));
  const [error, setError] = useState<string | null>(null);
  const [savedOk, setSavedOk] = useState(false);

  // v2 sentinel: the Settings card shouldn't exist for v1 responses.
  if (!config?.id || !config.has_byok_key) return null;

  const handleSave = async () => {
    setError(null);
    setSavedOk(false);
    const allowedModels = allowedRaw
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    const payload: ScopeUpdatePayload = {
      allowed_models: allowedModels,
      // Empty string = clear. Number parse errors = clear.
      monthly_request_cap: requestCap.trim() === '' ? null : Number(requestCap) || null,
      monthly_spend_cap_usd: spendCap.trim() === '' ? null : Number(spendCap) || null,
    };

    try {
      await update.mutateAsync(payload);
      setSavedOk(true);
    } catch (err) {
      const msg = toBYOKUserMessage(err);
      setError(msg.body);
    }
  };

  return (
    <div className="card-industrial">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center">
          <Gauge size={16} className="text-industrial-muted" />
        </div>
        <h2 className="text-sm font-semibold text-industrial">Usage controls</h2>
      </div>

      <p className="text-sm text-industrial-secondary mb-5 leading-relaxed">
        Restrict which models this credential may use and cap its monthly cost or request count.
        Leave a field blank to remove that limit.
      </p>

      <div className="space-y-4">
        <div>
          <label className="text-sm font-medium text-industrial block mb-2">
            Allowed models (comma-separated)
          </label>
          <input
            type="text"
            value={allowedRaw}
            onChange={(e) => setAllowedRaw(e.target.value)}
            placeholder="claude-haiku-4-5-20251001, claude-sonnet-4-6-20260320"
            className="input-industrial"
          />
          <p className="text-xs text-industrial-muted mt-1">
            Leave blank to allow any model the provider supports.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium text-industrial block mb-2">
              <Clock size={12} className="inline mr-1 -mt-0.5" />
              Monthly request cap
            </label>
            <input
              type="number"
              min={0}
              value={requestCap}
              onChange={(e) => setRequestCap(e.target.value)}
              placeholder="e.g. 10000"
              className="input-industrial"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-industrial block mb-2">
              <DollarSign size={12} className="inline mr-1 -mt-0.5" />
              Monthly spend cap (USD)
            </label>
            <input
              type="number"
              min={0}
              step={1}
              value={spendCap}
              onChange={(e) => setSpendCap(e.target.value)}
              placeholder="e.g. 500"
              className="input-industrial"
            />
            <p className="text-xs text-industrial-muted mt-1">
              Estimate only — based on a blended per-token rate.
            </p>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg bg-[var(--bg-error)] text-[var(--color-error)]">
            <AlertCircle size={14} />
            {error}
          </div>
        )}
        {savedOk && !error && (
          <div className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg bg-[var(--bg-success)] text-[var(--color-success)]">
            <CheckCircle2 size={14} />
            Scope updated
          </div>
        )}

        <div>
          <button
            onClick={handleSave}
            disabled={update.isPending}
            className="btn-industrial-primary"
          >
            {update.isPending ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Check size={14} />
                Save scope
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function RecentActivitySection() {
  const { data: config } = useAIConfig();
  const { data: entries, isLoading } = useCredentialAudit(20);

  // v2 sentinel + only interesting when there's a stored key.
  if (!config?.id) return null;

  return (
    <div className="card-industrial">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center">
          <Clock size={16} className="text-industrial-muted" />
        </div>
        <h2 className="text-sm font-semibold text-industrial">Recent activity</h2>
      </div>

      {isLoading ? (
        <div className="animate-pulse space-y-2">
          <div className="h-3 bg-[var(--bg-tertiary)] rounded w-full"></div>
          <div className="h-3 bg-[var(--bg-tertiary)] rounded w-5/6"></div>
          <div className="h-3 bg-[var(--bg-tertiary)] rounded w-4/6"></div>
        </div>
      ) : !entries || entries.length === 0 ? (
        <p className="text-sm text-industrial-muted">No activity yet.</p>
      ) : (
        <ul className="divide-y divide-[var(--border-subtle)]">
          {entries.map((e) => (
            <li key={e.id} className="py-2 flex items-center justify-between gap-3">
              <div className="min-w-0 flex items-center gap-2">
                {e.success ? (
                  <CheckCircle2 size={12} className="text-[var(--color-success)] shrink-0" />
                ) : (
                  <AlertCircle size={12} className="text-[var(--color-error)] shrink-0" />
                )}
                <span className="text-sm text-industrial">{auditActionLabel(e.action)}</span>
                {e.provider && (
                  <span className="text-xs text-industrial-muted truncate">
                    · {e.provider}
                  </span>
                )}
                {e.error_code && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-error)] text-[var(--color-error)] font-mono">
                    {e.error_code}
                  </span>
                )}
              </div>
              <span className="text-xs text-industrial-muted tabular-nums shrink-0">
                {new Date(e.occurred_at).toLocaleString(undefined, {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const SPECIALIST_NAMES = ['scout', 'analyst', 'matchmaker', 'outreach'] as const;
const ANTHROPIC_MODELS = [
  'claude-sonnet-4-6-20260320',
  'claude-sonnet-4-20250514',
  'claude-haiku-4-5-20251001',
];

function UsageSection() {
  const { data: usage } = useUsage();

  if (!usage) return null;

  const totalK = (usage.current_period_input_tokens + usage.current_period_output_tokens) / 1000;

  return (
    <div className="card-industrial">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center">
          <Sparkles size={16} className="text-industrial-muted" />
        </div>
        <h2 className="text-sm font-semibold text-industrial">Usage This Month</h2>
        {usage.using_byok && (
          <span className="text-[10px] text-[var(--color-success)] px-2 py-0.5 bg-[var(--bg-success)] rounded-full ml-auto">
            BYOK
          </span>
        )}
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <p className="text-xs text-industrial-muted">Tokens</p>
          <p className="text-lg font-semibold text-industrial">{totalK.toFixed(1)}K</p>
        </div>
        <div>
          <p className="text-xs text-industrial-muted">Tool Calls (24h)</p>
          <p className="text-lg font-semibold text-industrial">{usage.last_24h_llm_calls}</p>
        </div>
        <div>
          <p className="text-xs text-industrial-muted">Est. Cost</p>
          <p className="text-lg font-semibold text-industrial">${usage.last_24h_cost_estimate_usd.toFixed(2)}</p>
        </div>
      </div>
      {!usage.using_byok && totalK > 5 && (
        <p className="text-xs text-[var(--accent)] mt-3 pt-3 border-t border-[var(--border-subtle)]">
          You&apos;ve used {totalK.toFixed(0)}K tokens on our platform key. Add your own Anthropic key in AI Model settings for unmetered usage.
        </p>
      )}
    </div>
  );
}

function SpecialistModelsSection() {
  const { data: config } = useAIConfig();
  const { data: specModels } = useSpecialistModels();
  const updateMutation = useUpdateSpecialistModels();
  const [localModels, setLocalModels] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);

  // Sync from server
  const serverModels = specModels?.specialist_models || {};

  const handleChange = (name: string, model: string) => {
    const updated = { ...serverModels, ...localModels, [name]: model };
    // Remove empty entries (means "use default")
    if (!model) delete updated[name];
    setLocalModels(updated);
    setDirty(true);
  };

  const handleSave = async () => {
    await updateMutation.mutateAsync({ ...serverModels, ...localModels });
    setDirty(false);
    setLocalModels({});
  };

  // Only show if user has BYOK key
  if (!config?.has_byok_key || !config?.is_key_valid) return null;

  const merged = { ...serverModels, ...localModels };

  return (
    <div className="card-industrial">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center">
          <Brain size={16} className="text-industrial-muted" />
        </div>
        <h2 className="text-sm font-semibold text-industrial">Specialist Models</h2>
      </div>
      <p className="text-xs text-industrial-muted mb-4">
        Override which Claude model each specialist uses. Leave blank for the default.
      </p>
      <div className="space-y-3">
        {SPECIALIST_NAMES.map((name) => (
          <div key={name} className="flex items-center gap-3">
            <span className="text-xs font-medium text-industrial w-24 capitalize">{name}</span>
            <select
              value={merged[name] || ''}
              onChange={(e) => handleChange(name, e.target.value)}
              className="input-industrial flex-1 text-xs"
            >
              <option value="">Default</option>
              {ANTHROPIC_MODELS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        ))}
      </div>
      {dirty && (
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="btn-industrial-primary mt-4 text-xs"
        >
          {updateMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
          Save
        </button>
      )}
    </div>
  );
}

export function SettingsPage() {
  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="p-6 max-w-3xl mx-auto min-h-full">
          <h1 className="text-xl font-semibold text-industrial mb-6">Settings</h1>

          <div className="space-y-6">
            {/* AI Model Configuration — most important, up top */}
            <AIModelSection />

            {/* Usage controls: allow-lists + monthly caps (v2 only) */}
            <ScopeSection />

            {/* Recent credential activity (v2 only) */}
            <RecentActivitySection />

            {/* Usage */}
            <UsageSection />

            {/* Per-specialist model overrides (BYOK only) */}
            <SpecialistModelsSection />

            {/* AI Preferences */}
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

          {/* Advanced: Space Goose Memory (collapsed by default) */}
          <MemorySection />

          {/* Danger Zone */}
          <div className="card-industrial border-[var(--color-error)]/20">
            <h2 className="text-sm font-semibold text-[var(--color-error)] mb-4">Danger Zone</h2>
            <button className="btn-industrial border-[var(--color-error)]/30 text-[var(--color-error)] hover:bg-[var(--bg-error)] transition-colors">
              Delete Account
            </button>
          </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
