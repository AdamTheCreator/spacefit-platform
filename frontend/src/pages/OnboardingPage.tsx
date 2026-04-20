import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle, Upload, ArrowRight, ArrowLeft, Loader2 } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import api from '../lib/axios';

type OnboardingStep = 'welcome' | 'import' | 'connect' | 'ai_key' | 'complete';

const STEPS: OnboardingStep[] = ['welcome', 'import', 'connect', 'ai_key', 'complete'];

const AVAILABLE_AGENTS = [
  {
    id: 'costar',
    name: 'CoStar',
    description: 'Commercial real estate data and analytics',
    icon: '🏢',
  },
  {
    id: 'placer_ai',
    name: 'Placer.ai',
    description: 'Foot traffic and location intelligence',
    icon: '👣',
  },
  {
    id: 'census_acs',
    name: 'Census ACS',
    description: 'American Community Survey demographics',
    icon: '📊',
  },
  {
    id: 'loopnet',
    name: 'LoopNet',
    description: 'Commercial property listings',
    icon: '🔍',
  },
];

export function OnboardingPage() {
  const navigate = useNavigate();
  const { user, setUser } = useAuthStore();
  const [currentStep, setCurrentStep] = useState<OnboardingStep>('welcome');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [byokKey, setByokKey] = useState('');
  const [byokValidating, setByokValidating] = useState(false);
  const [byokResult, setByokResult] = useState<{ valid: boolean; error?: string } | null>(null);

  const currentIndex = STEPS.indexOf(currentStep);

  const handleNext = () => {
    const nextIndex = currentIndex + 1;
    if (nextIndex < STEPS.length) {
      setCurrentStep(STEPS[nextIndex]);
    }
  };

  const handleBack = () => {
    const prevIndex = currentIndex - 1;
    if (prevIndex >= 0) {
      setCurrentStep(STEPS[prevIndex]);
    }
  };

  const handleComplete = async () => {
    setIsLoading(true);
    try {
      await api.post('/onboarding/complete');
      if (user) {
        setUser({ ...user, has_completed_onboarding: true });
      }
      navigate('/', { replace: true });
    } catch (error) {
      console.error('Failed to complete onboarding:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSkip = () => {
    handleNext();
  };

  const handleByokSubmit = async () => {
    if (!byokKey.trim()) return;
    setByokValidating(true);
    setByokResult(null);
    try {
      // Save the key
      await api.put('/ai-config', {
        provider: 'anthropic',
        api_key: byokKey.trim(),
        model: 'claude-haiku-4-5-20251001',
      });
      // Validate it
      const res = await api.post('/ai-config/validate-key', {
        provider: 'anthropic',
        api_key: byokKey.trim(),
        model: 'claude-haiku-4-5-20251001',
      });
      setByokResult(res.data);
      if (res.data.valid) {
        setTimeout(() => handleNext(), 800);
      }
    } catch {
      setByokResult({ valid: false, error: 'Failed to validate key' });
    } finally {
      setByokValidating(false);
    }
  };

  const toggleAgent = (agentId: string) => {
    setSelectedAgents((prev) =>
      prev.includes(agentId)
        ? prev.filter((id) => id !== agentId)
        : [...prev, agentId]
    );
  };

  return (
    <div className="min-h-screen bg-industrial flex flex-col dark">
      {/* Progress bar */}
      <div className="w-full bg-[var(--bg-tertiary)] h-0.5">
        <div
          className="bg-[var(--accent)] h-0.5 transition-all duration-300"
          style={{ width: `${((currentIndex + 1) / STEPS.length) * 100}%` }}
        />
      </div>

      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-2xl">
          {/* Welcome Step — Planner goose */}
          {currentStep === 'welcome' && (
            <div className="text-center">
              <img
                src="/mascots/goose-planner.png"
                alt=""
                className="w-36 h-36 mx-auto mb-4 object-contain select-none"
                draggable={false}
              />
              <h1 className="font-mono text-2xl font-bold tracking-tight text-industrial mb-4">
                Welcome to Perigee, {user?.first_name || 'there'}!
              </h1>
              <p className="font-mono text-sm text-industrial-secondary mb-8 max-w-md mx-auto">
                Let&apos;s get you set up. This will only take a few minutes and you can
                always update these settings later.
              </p>
              <button
                onClick={handleNext}
                className="btn-industrial-primary px-8 py-3"
              >
                Get started
                <ArrowRight size={18} />
              </button>
            </div>
          )}

          {/* Import Step — Carriers goose (cargo/data crew) */}
          {currentStep === 'import' && (
            <div>
              <div className="text-center mb-8">
                <img
                  src="/mascots/goose-carriers.png"
                  alt=""
                  className="w-28 h-28 mx-auto mb-3 object-contain select-none"
                  draggable={false}
                />
                <h2 className="font-mono text-xl font-bold tracking-tight text-industrial mb-2">
                  Import your customer list
                </h2>
                <p className="font-mono text-xs text-industrial-muted">
                  Upload a CSV or Excel file with your customers and their criteria
                </p>
              </div>

              <div className="bg-[var(--bg-tertiary)] border-2 border-dashed border-industrial p-12 text-center mb-6 hover:border-[var(--accent)] transition-colors cursor-pointer">
                <Upload className="mx-auto mb-4 text-industrial-muted" size={48} />
                <p className="font-mono text-sm text-industrial-secondary mb-2">
                  Drag and drop your file here, or click to browse
                </p>
                <p className="font-mono text-xs text-industrial-muted">
                  Supports CSV and Excel files up to 10MB
                </p>
              </div>

              <div className="flex justify-between">
                <button
                  onClick={handleBack}
                  className="btn-industrial"
                >
                  <ArrowLeft size={18} />
                  Back
                </button>
                <div className="flex gap-3">
                  <button
                    onClick={handleSkip}
                    className="font-mono text-xs uppercase tracking-wide text-industrial-muted hover:text-industrial transition-colors px-4 py-2"
                  >
                    Skip for now
                  </button>
                  <button
                    onClick={handleNext}
                    className="btn-industrial-primary"
                  >
                    Continue
                    <ArrowRight size={18} />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Connect Step — Engineer goose (wiring up integrations) */}
          {currentStep === 'connect' && (
            <div>
              <div className="text-center mb-8">
                <img
                  src="/mascots/goose-engineer.png"
                  alt=""
                  className="w-28 h-28 mx-auto mb-3 object-contain select-none"
                  draggable={false}
                />
                <h2 className="font-mono text-xl font-bold tracking-tight text-industrial mb-2">
                  Connect your data sources
                </h2>
                <p className="font-mono text-xs text-industrial-muted">
                  Select the platforms you use. You&apos;ll be able to add credentials later.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-8">
                {AVAILABLE_AGENTS.map((agent) => (
                  <button
                    key={agent.id}
                    onClick={() => toggleAgent(agent.id)}
                    className={`p-4 border text-left transition-all ${
                      selectedAgents.includes(agent.id)
                        ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                        : 'border-industrial-subtle bg-[var(--bg-tertiary)] hover:border-industrial'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-2xl">{agent.icon}</span>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <h3 className="font-mono text-sm font-medium text-industrial">{agent.name}</h3>
                          {selectedAgents.includes(agent.id) && (
                            <CheckCircle className="text-[var(--accent)]" size={18} />
                          )}
                        </div>
                        <p className="font-mono text-[10px] text-industrial-muted mt-1">{agent.description}</p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>

              <div className="flex justify-between">
                <button
                  onClick={handleBack}
                  className="btn-industrial"
                >
                  <ArrowLeft size={18} />
                  Back
                </button>
                <div className="flex gap-3">
                  <button
                    onClick={handleSkip}
                    className="font-mono text-xs uppercase tracking-wide text-industrial-muted hover:text-industrial transition-colors px-4 py-2"
                  >
                    Skip for now
                  </button>
                  <button
                    onClick={handleNext}
                    className="btn-industrial-primary"
                  >
                    Continue
                    <ArrowRight size={18} />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* AI Key Step — Welder goose (sealing the connection) */}
          {currentStep === 'ai_key' && (
            <div>
              <div className="text-center mb-8">
                <img
                  src="/mascots/goose-welder.png"
                  alt=""
                  className="w-28 h-28 mx-auto mb-3 object-contain select-none"
                  draggable={false}
                />
                <h2 className="font-mono text-xl font-bold tracking-tight text-industrial mb-2">
                  Bring your own AI key
                </h2>
                <p className="font-mono text-xs text-industrial-muted max-w-md mx-auto">
                  Add your Anthropic API key for unlimited usage with your own billing.
                  We cover your first queries free &mdash; add a key anytime from Settings.
                </p>
              </div>

              <div className="bg-[var(--bg-tertiary)] border border-industrial-subtle p-6 mb-6">
                <label className="font-mono text-xs uppercase tracking-wide text-industrial-muted mb-2 block">
                  Anthropic API Key
                </label>
                <div className="flex gap-3">
                  <input
                    type="password"
                    value={byokKey}
                    onChange={(e) => { setByokKey(e.target.value); setByokResult(null); }}
                    placeholder="sk-ant-..."
                    className="flex-1 bg-[var(--bg-primary)] border border-industrial-subtle px-3 py-2 font-mono text-sm text-industrial placeholder:text-industrial-muted/50 focus:border-[var(--accent)] focus:outline-none"
                  />
                  <button
                    onClick={handleByokSubmit}
                    disabled={!byokKey.trim() || byokValidating}
                    className="btn-industrial-primary px-4 disabled:opacity-50"
                  >
                    {byokValidating ? <Loader2 size={16} className="animate-spin" /> : 'Validate'}
                  </button>
                </div>
                {byokResult && (
                  <p className={`font-mono text-xs mt-2 ${byokResult.valid ? 'text-[var(--color-success)]' : 'text-[var(--color-error)]'}`}>
                    {byokResult.valid ? 'Key validated successfully!' : byokResult.error}
                  </p>
                )}
                <p className="font-mono text-[10px] text-industrial-muted mt-3">
                  Your key is encrypted and stored securely. Get one at console.anthropic.com.
                </p>
              </div>

              <div className="flex justify-between">
                <button onClick={handleBack} className="btn-industrial">
                  <ArrowLeft size={18} />
                  Back
                </button>
                <div className="flex gap-3">
                  <button
                    onClick={handleSkip}
                    className="font-mono text-xs uppercase tracking-wide text-industrial-muted hover:text-industrial transition-colors px-4 py-2"
                  >
                    Skip for now
                  </button>
                  <button onClick={handleNext} className="btn-industrial-primary">
                    Continue
                    <ArrowRight size={18} />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Complete Step — Launch goose (mission begins) */}
          {currentStep === 'complete' && (
            <div className="text-center">
              <img
                src="/mascots/goose-launch.png"
                alt=""
                className="w-36 h-36 mx-auto mb-4 object-contain select-none"
                draggable={false}
              />
              <h1 className="font-mono text-2xl font-bold tracking-tight text-industrial mb-4">You&apos;re cleared for launch!</h1>
              <p className="font-mono text-sm text-industrial-secondary mb-8 max-w-md mx-auto">
                Your mission control is ready. Start chatting with Perigee to analyze
                properties and find the perfect matches for your clients.
              </p>
              <div className="flex justify-center gap-4">
                <button
                  onClick={handleBack}
                  className="btn-industrial"
                >
                  <ArrowLeft size={18} />
                  Back
                </button>
                <button
                  onClick={handleComplete}
                  disabled={isLoading}
                  className="btn-industrial-primary px-8 py-3 disabled:opacity-50"
                >
                  {isLoading ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      Starting...
                    </>
                  ) : (
                    <>
                      Start using Perigee AI
                      <ArrowRight size={18} />
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
