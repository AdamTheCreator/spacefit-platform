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
          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            selected.includes(option.value)
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
          title={option.description}
        >
          {option.label}
          {selected.includes(option.value) && <Check size={14} className="inline ml-1" />}
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
      <div className="flex flex-wrap gap-2 mb-2">
        {tags.map((tag) => (
          <span
            key={tag}
            className="px-3 py-1 bg-blue-600/30 text-blue-300 rounded-full text-sm flex items-center gap-1"
          >
            {tag}
            <button onClick={() => removeTag(tag)} className="hover:text-white">
              <X size={14} />
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
          className="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <button
          onClick={addTag}
          className="px-3 py-2 bg-gray-600 hover:bg-gray-500 rounded-lg text-gray-300 transition-colors"
        >
          <Plus size={18} />
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
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 animate-pulse">
        <div className="h-6 bg-gray-700 rounded w-48 mb-4"></div>
        <div className="space-y-3">
          <div className="h-4 bg-gray-700 rounded w-full"></div>
          <div className="h-4 bg-gray-700 rounded w-3/4"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Sparkles size={20} className="text-purple-400" />
          <h2 className="text-lg font-medium text-white">AI Preferences</h2>
        </div>
        {preferences && (
          <div className="flex items-center gap-2">
            <div className="h-2 w-24 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-500 transition-all"
                style={{ width: `${preferences.completion_percentage}%` }}
              />
            </div>
            <span className="text-sm text-gray-400">
              {preferences.completion_percentage}% complete
            </span>
          </div>
        )}
      </div>

      <p className="text-gray-400 text-sm mb-6">
        Help SpaceFit AI understand your business to provide more relevant analysis and recommendations.
      </p>

      <div className="space-y-6">
        {/* Role */}
        <div>
          <label className="text-gray-300 block mb-2 font-medium">Your Role</label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {options?.roles.map((role) => (
              <button
                key={role.value}
                onClick={() => updateField('role', role.value)}
                className={`p-3 rounded-lg border text-left transition-colors ${
                  currentPrefs.role === role.value
                    ? 'border-purple-500 bg-purple-500/20 text-white'
                    : 'border-gray-600 bg-gray-700 text-gray-300 hover:border-gray-500'
                }`}
              >
                <div className="font-medium">{role.label}</div>
                <div className="text-xs text-gray-400 mt-1">{role.description}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Property Types */}
        <div>
          <label className="text-gray-300 block mb-2 font-medium">Property Types</label>
          <p className="text-gray-500 text-sm mb-2">Select all that apply</p>
          <MultiSelect
            options={options?.property_types ?? []}
            selected={currentPrefs.property_types}
            onChange={(v) => updateField('property_types', v)}
          />
        </div>

        {/* Tenant Categories */}
        <div>
          <label className="text-gray-300 block mb-2 font-medium">Tenant Categories</label>
          <p className="text-gray-500 text-sm mb-2">What types of tenants do you work with?</p>
          <MultiSelect
            options={options?.tenant_categories ?? []}
            selected={currentPrefs.tenant_categories}
            onChange={(v) => updateField('tenant_categories', v)}
          />
        </div>

        {/* Geographic Markets */}
        <div>
          <label className="text-gray-300 block mb-2 font-medium">Geographic Markets</label>
          <p className="text-gray-500 text-sm mb-2">Add the markets you operate in</p>
          <TagInput
            tags={currentPrefs.markets}
            onChange={(v) => updateField('markets', v)}
            placeholder="e.g., Fairfield County, CT"
          />
        </div>

        {/* Deal Size */}
        <div>
          <label className="text-gray-300 block mb-2 font-medium">Typical Deal Size (SF)</label>
          <div className="flex gap-4">
            <div className="flex-1">
              <label className="text-gray-500 text-sm">Min</label>
              <input
                type="number"
                value={currentPrefs.deal_size_min ?? ''}
                onChange={(e) =>
                  updateField('deal_size_min', e.target.value ? parseInt(e.target.value) : null)
                }
                placeholder="1,000"
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>
            <div className="flex-1">
              <label className="text-gray-500 text-sm">Max</label>
              <input
                type="number"
                value={currentPrefs.deal_size_max ?? ''}
                onChange={(e) =>
                  updateField('deal_size_max', e.target.value ? parseInt(e.target.value) : null)
                }
                placeholder="50,000"
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>
          </div>
        </div>

        {/* Key Tenants */}
        <div>
          <label className="text-gray-300 block mb-2 font-medium">Key Tenant Relationships</label>
          <p className="text-gray-500 text-sm mb-2">
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
          <label className="text-gray-300 block mb-2 font-medium">Analysis Priorities</label>
          <p className="text-gray-500 text-sm mb-2">What matters most in your analyses?</p>
          <MultiSelect
            options={options?.analysis_priorities ?? []}
            selected={currentPrefs.analysis_priorities}
            onChange={(v) => updateField('analysis_priorities', v)}
          />
        </div>

        {/* Custom Notes */}
        <div>
          <label className="text-gray-300 block mb-2 font-medium">Additional Context</label>
          <p className="text-gray-500 text-sm mb-2">
            Any other information that would help the AI assist you better
          </p>
          <textarea
            value={currentPrefs.custom_notes ?? ''}
            onChange={(e) => updateField('custom_notes', e.target.value || null)}
            placeholder="e.g., I specialize in drive-thru enabled sites for QSR tenants..."
            rows={3}
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
          />
        </div>

        {/* Save Button */}
        {hasChanges && (
          <div className="flex justify-end pt-4 border-t border-gray-700">
            <button
              onClick={saveChanges}
              disabled={updateMutation.isPending}
              className="px-6 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-800 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {updateMutation.isPending ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Check size={18} />
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
      <div className="p-6 max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-6">Settings</h1>

        <div className="space-y-6">
          {/* AI Preferences - Featured at top */}
          <AIPreferencesSection />

          {/* Notifications */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center gap-3 mb-4">
              <Bell size={20} className="text-gray-400" />
              <h2 className="text-lg font-medium text-white">Notifications</h2>
            </div>

            <div className="space-y-4">
              <label className="flex items-center justify-between">
                <span className="text-gray-300">Email notifications</span>
                <input
                  type="checkbox"
                  defaultChecked
                  className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-blue-600 focus:ring-blue-500"
                />
              </label>

              <label className="flex items-center justify-between">
                <span className="text-gray-300">Analysis complete alerts</span>
                <input
                  type="checkbox"
                  defaultChecked
                  className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-blue-600 focus:ring-blue-500"
                />
              </label>

              <label className="flex items-center justify-between">
                <span className="text-gray-300">Weekly digest</span>
                <input
                  type="checkbox"
                  className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-blue-600 focus:ring-blue-500"
                />
              </label>
            </div>
          </div>

          {/* Security */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center gap-3 mb-4">
              <Shield size={20} className="text-gray-400" />
              <h2 className="text-lg font-medium text-white">Security</h2>
            </div>

            <div className="space-y-4">
              <button className="w-full text-left px-4 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                <span className="text-gray-300">Change password</span>
                <p className="text-gray-500 text-sm">Update your account password</p>
              </button>

              <button className="w-full text-left px-4 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                <span className="text-gray-300">Two-factor authentication</span>
                <p className="text-gray-500 text-sm">Add an extra layer of security</p>
              </button>

              <button className="w-full text-left px-4 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                <span className="text-gray-300">Active sessions</span>
                <p className="text-gray-500 text-sm">Manage devices where you're logged in</p>
              </button>
            </div>
          </div>

          {/* Appearance */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex items-center gap-3 mb-4">
              <Palette size={20} className="text-gray-400" />
              <h2 className="text-lg font-medium text-white">Appearance</h2>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-gray-300 block mb-2">Theme</label>
                <select className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent">
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
          <div className="bg-gray-800 rounded-lg p-6 border border-red-900/50">
            <h2 className="text-lg font-medium text-red-400 mb-4">Danger Zone</h2>
            <button className="px-4 py-2 bg-red-900/30 hover:bg-red-900/50 text-red-400 border border-red-700 rounded-lg transition-colors">
              Delete Account
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
