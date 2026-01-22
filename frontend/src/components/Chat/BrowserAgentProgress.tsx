import { useEffect, useState } from 'react';
import { Monitor, Loader2, Clock } from 'lucide-react';
import type { AgentType } from '../../types/chat';
import { AGENTS } from '../../types/chat';

interface BrowserAgentProgressProps {
  agentType: AgentType;
  isActive: boolean;
  estimatedDuration?: number; // seconds
  currentStep?: string;
  stepProgress?: number; // 0-100
}

export function BrowserAgentProgress({
  agentType,
  isActive,
  estimatedDuration = 45,
  currentStep,
  stepProgress,
}: BrowserAgentProgressProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isActive) {
      setElapsed(0);
      return;
    }

    const interval = setInterval(() => {
      setElapsed((e) => e + 1);
    }, 1000);

    return () => clearInterval(interval);
  }, [isActive]);

  if (!isActive) return null;

  const agent = AGENTS[agentType];
  const progress = stepProgress ?? Math.min((elapsed / estimatedDuration) * 100, 95);
  const remaining = Math.max(estimatedDuration - elapsed, 0);

  return (
    <div className="bg-purple-900/20 border border-purple-700/50 rounded-lg p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-800/50 rounded-lg">
            <Monitor size={18} className="text-purple-400" />
          </div>
          <div>
            <h4 className="text-sm font-medium text-purple-300">
              Browser Agent Active
            </h4>
            <p className="text-xs text-gray-400">{agent?.name || agentType}</p>
          </div>
        </div>
        <Loader2 size={18} className="animate-spin text-purple-400" />
      </div>

      {currentStep && (
        <p className="text-sm text-gray-300 mb-3">{currentStep}</p>
      )}

      <div className="space-y-2">
        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all duration-1000 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="flex justify-between text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <Clock size={12} />
            {elapsed}s elapsed
          </span>
          <span>~{remaining}s remaining</span>
        </div>
      </div>

      <p className="text-xs text-gray-500 mt-3">
        Accessing external data source via browser automation. This is slower
        than API calls but provides access to premium data.
      </p>
    </div>
  );
}

interface BrowserProgressData {
  agent_type: string;
  step: string;
  progress_pct: number;
  message: string;
  estimated_remaining_seconds?: number;
}

interface UseBrowserProgressReturn {
  progress: BrowserProgressData | null;
  setProgress: (data: BrowserProgressData | null) => void;
  isActive: boolean;
}

/**
 * Hook to manage browser agent progress state.
 * Can be used with WebSocket messages.
 */
export function useBrowserProgress(): UseBrowserProgressReturn {
  const [progress, setProgress] = useState<BrowserProgressData | null>(null);

  return {
    progress,
    setProgress,
    isActive: progress !== null,
  };
}
