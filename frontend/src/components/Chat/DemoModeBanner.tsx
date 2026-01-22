import { DEMO_PROPERTY } from '../../data/demoConversation';

interface DemoModeBannerProps {
  onExitDemo: () => void;
}

export function DemoModeBanner({ onExitDemo }: DemoModeBannerProps) {

  return (
    <div className="flex-shrink-0 px-4 py-3 bg-gradient-to-r from-indigo-900/80 via-purple-900/80 to-indigo-900/80 border-b border-indigo-500/30">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Animated demo badge */}
          <div className="relative">
            <span className="absolute inset-0 rounded-full bg-indigo-500 animate-ping opacity-30" />
            <span className="relative flex items-center gap-1.5 px-3 py-1 bg-indigo-600 text-white text-xs font-bold rounded-full uppercase tracking-wider">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path d="M2 6a2 2 0 012-2h6a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM14.553 7.106A1 1 0 0014 8v4a1 1 0 00.553.894l2 1A1 1 0 0018 13V7a1 1 0 00-1.447-.894l-2 1z" />
              </svg>
              Demo Mode
            </span>
          </div>

          <div className="text-sm">
            <span className="text-indigo-200">Showcasing analysis of </span>
            <span className="text-white font-medium">{DEMO_PROPERTY.name}</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-indigo-300 hidden sm:inline">
            This is a pre-populated investor demo
          </span>
          <button
            onClick={onExitDemo}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-700/50 hover:bg-indigo-600/50
                     text-indigo-100 text-sm rounded-lg transition-colors border border-indigo-500/30"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            Exit Demo
          </button>
        </div>
      </div>

      {/* Animated gradient line */}
      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-indigo-400 to-transparent opacity-50"
           style={{ animation: 'data-flow 3s ease-in-out infinite' }} />
    </div>
  );
}
