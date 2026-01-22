import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle, Upload, Link2, ArrowRight, ArrowLeft, Loader2 } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import api from '../lib/axios';

type OnboardingStep = 'welcome' | 'import' | 'connect' | 'complete';

const STEPS: OnboardingStep[] = ['welcome', 'import', 'connect', 'complete'];

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

  const toggleAgent = (agentId: string) => {
    setSelectedAgents((prev) =>
      prev.includes(agentId)
        ? prev.filter((id) => id !== agentId)
        : [...prev, agentId]
    );
  };

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      {/* Progress bar */}
      <div className="w-full bg-gray-800 h-1">
        <div
          className="bg-blue-500 h-1 transition-all duration-300"
          style={{ width: `${((currentIndex + 1) / STEPS.length) * 100}%` }}
        />
      </div>

      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-2xl">
          {/* Welcome Step */}
          {currentStep === 'welcome' && (
            <div className="text-center">
              <div className="w-20 h-20 bg-blue-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
                <span className="text-4xl">👋</span>
              </div>
              <h1 className="text-3xl font-bold text-white mb-4">
                Welcome to SpaceFit AI, {user?.first_name || 'there'}!
              </h1>
              <p className="text-gray-400 text-lg mb-8 max-w-md mx-auto">
                Let&apos;s get you set up. This will only take a few minutes and you can
                always update these settings later.
              </p>
              <button
                onClick={handleNext}
                className="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors inline-flex items-center gap-2"
              >
                Get started
                <ArrowRight size={20} />
              </button>
            </div>
          )}

          {/* Import Step */}
          {currentStep === 'import' && (
            <div>
              <div className="text-center mb-8">
                <div className="w-16 h-16 bg-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Upload className="text-purple-400" size={32} />
                </div>
                <h2 className="text-2xl font-bold text-white mb-2">
                  Import your customer list
                </h2>
                <p className="text-gray-400">
                  Upload a CSV or Excel file with your customers and their criteria
                </p>
              </div>

              <div className="bg-gray-800/50 border-2 border-dashed border-gray-700 rounded-xl p-12 text-center mb-6 hover:border-gray-600 transition-colors cursor-pointer">
                <Upload className="mx-auto mb-4 text-gray-500" size={48} />
                <p className="text-gray-300 mb-2">
                  Drag and drop your file here, or click to browse
                </p>
                <p className="text-sm text-gray-500">
                  Supports CSV and Excel files up to 10MB
                </p>
              </div>

              <div className="flex justify-between">
                <button
                  onClick={handleBack}
                  className="px-6 py-3 text-gray-400 hover:text-white transition-colors inline-flex items-center gap-2"
                >
                  <ArrowLeft size={20} />
                  Back
                </button>
                <div className="flex gap-3">
                  <button
                    onClick={handleSkip}
                    className="px-6 py-3 text-gray-400 hover:text-white transition-colors"
                  >
                    Skip for now
                  </button>
                  <button
                    onClick={handleNext}
                    className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors inline-flex items-center gap-2"
                  >
                    Continue
                    <ArrowRight size={20} />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Connect Step */}
          {currentStep === 'connect' && (
            <div>
              <div className="text-center mb-8">
                <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Link2 className="text-green-400" size={32} />
                </div>
                <h2 className="text-2xl font-bold text-white mb-2">
                  Connect your data sources
                </h2>
                <p className="text-gray-400">
                  Select the platforms you use. You&apos;ll be able to add credentials later.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-8">
                {AVAILABLE_AGENTS.map((agent) => (
                  <button
                    key={agent.id}
                    onClick={() => toggleAgent(agent.id)}
                    className={`p-4 rounded-xl border-2 text-left transition-all ${
                      selectedAgents.includes(agent.id)
                        ? 'border-blue-500 bg-blue-500/10'
                        : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-2xl">{agent.icon}</span>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <h3 className="font-medium text-white">{agent.name}</h3>
                          {selectedAgents.includes(agent.id) && (
                            <CheckCircle className="text-blue-500" size={20} />
                          )}
                        </div>
                        <p className="text-sm text-gray-400 mt-1">{agent.description}</p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>

              <div className="flex justify-between">
                <button
                  onClick={handleBack}
                  className="px-6 py-3 text-gray-400 hover:text-white transition-colors inline-flex items-center gap-2"
                >
                  <ArrowLeft size={20} />
                  Back
                </button>
                <div className="flex gap-3">
                  <button
                    onClick={handleSkip}
                    className="px-6 py-3 text-gray-400 hover:text-white transition-colors"
                  >
                    Skip for now
                  </button>
                  <button
                    onClick={handleNext}
                    className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors inline-flex items-center gap-2"
                  >
                    Continue
                    <ArrowRight size={20} />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Complete Step */}
          {currentStep === 'complete' && (
            <div className="text-center">
              <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
                <CheckCircle className="text-green-400" size={48} />
              </div>
              <h1 className="text-3xl font-bold text-white mb-4">You&apos;re all set!</h1>
              <p className="text-gray-400 text-lg mb-8 max-w-md mx-auto">
                Your account is ready. Start chatting with SpaceFit AI to analyze
                properties and find the perfect matches for your clients.
              </p>
              <div className="flex justify-center gap-4">
                <button
                  onClick={handleBack}
                  className="px-6 py-3 text-gray-400 hover:text-white transition-colors inline-flex items-center gap-2"
                >
                  <ArrowLeft size={20} />
                  Back
                </button>
                <button
                  onClick={handleComplete}
                  disabled={isLoading}
                  className="px-8 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white font-medium rounded-lg transition-colors inline-flex items-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <Loader2 size={20} className="animate-spin" />
                      Starting...
                    </>
                  ) : (
                    <>
                      Start using SpaceFit AI
                      <ArrowRight size={20} />
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
