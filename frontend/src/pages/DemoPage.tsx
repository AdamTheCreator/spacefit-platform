import { useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDemoPlayback } from '../hooks/useDemoPlayback';
import { useScrollDirection } from '../hooks/useScrollDirection';
import { useIsDesktop } from '../hooks/useMediaQuery';
import { ChatMessage, WorkflowProgress, AgentStatusStrip } from '../components/Chat';
import { DEMO_PROPERTY } from '../data/demoConversation';

/**
 * Interactive demo page for investor presentations.
 * Press Enter to advance through each step of the demo.
 */
export function DemoPage() {
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLElement>(null);

  // Detect screen size and scroll direction
  const isDesktop = useIsDesktop();
  const { isVisible: isHeaderVisible } = useScrollDirection(scrollContainerRef, { threshold: 20 });

  const {
    messages,
    workflowSteps,
    isProcessing,
    activeAgentType,
    isComplete,
    isWaitingForInput,
    currentStep,
    totalSteps,
    advanceStep,
    resetDemo,
  } = useDemoPlayback();

  // Scroll to bottom function
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  // Auto-scroll to bottom when messages change (only when new messages are added)
  const prevMessagesLength = useRef(messages.length);
  useEffect(() => {
    if (messages.length > prevMessagesLength.current) {
      scrollToBottom();
    }
    prevMessagesLength.current = messages.length;
  }, [messages.length, scrollToBottom]);

  const handleExitDemo = () => {
    navigate('/login');
  };

  // Calculate progress percentage
  const progressPercent = Math.round((currentStep / totalSteps) * 100);

  // Determine message variant based on screen size

  return (
    <div className="h-screen w-screen flex flex-col bg-industrial dark">
      {/* Demo Header - collapsible on scroll */}
      <header
        className={`flex-shrink-0 flex items-center justify-between px-3 sm:px-6 py-3 sm:py-4 bg-[var(--bg-elevated)] border-b border-industrial transition-all duration-300 ${
          isHeaderVisible ? 'translate-y-0 opacity-100' : '-translate-y-full opacity-0 absolute top-0 left-0 right-0 z-40'
        }`}
      >
        <div className="flex items-center gap-3">
          {/* Logo */}
          <div className="w-10 h-10 bg-[var(--accent)] flex items-center justify-center">
            <svg className="w-6 h-6 text-[var(--color-industrial-900)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          </div>
          <div>
            <h1 className="font-mono text-lg font-bold tracking-tight text-industrial">Space Goose</h1>
            <p className="font-mono text-[10px] text-industrial-muted uppercase tracking-wide">Interactive Demo - {DEMO_PROPERTY.name}</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Progress indicator */}
          <div className="hidden sm:flex items-center gap-2">
            <div className="label-technical">Progress</div>
            <div className="w-24 h-1 bg-[var(--bg-tertiary)] overflow-hidden">
              <div
                className="h-full bg-[var(--accent)] transition-all duration-500"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <div className="font-mono text-xs text-industrial-muted">{progressPercent}%</div>
          </div>

          <button
            onClick={handleExitDemo}
            className="btn-industrial"
          >
            Exit Demo
          </button>
        </div>
      </header>

      {/* Demo Banner */}
      <div className="flex-shrink-0 px-3 sm:px-4 py-2 sm:py-3 bg-[var(--accent)]/10 border-b border-[var(--accent)]/30">
        <div className="flex items-center justify-center gap-2 sm:gap-4">
          <div className="flex items-center gap-2">
            {/* Pulsing indicator */}
            <span className="relative flex h-2 w-2 sm:h-3 sm:w-3">
              <span className="animate-ping absolute inline-flex h-full w-full bg-[var(--accent)] opacity-75"></span>
              <span className="relative inline-flex h-2 w-2 sm:h-3 sm:w-3 bg-[var(--accent)]"></span>
            </span>
            <span className="font-mono text-xs text-[var(--accent)] uppercase tracking-wide">
              <span className="hidden sm:inline">Interactive </span>Demo
            </span>
          </div>

          <span className="text-[var(--accent)]/50 hidden sm:inline">|</span>

          <div className="flex items-center gap-1 sm:gap-2">
            <kbd className="px-1.5 sm:px-2 py-0.5 sm:py-1 bg-[var(--bg-tertiary)] text-industrial-secondary font-mono text-xs border border-industrial-subtle">
              Enter
            </kbd>
            <span className="font-mono text-xs text-[var(--accent)]">
              {isComplete ? 'restart' : isWaitingForInput ? 'continue' : '...'}
            </span>
          </div>
        </div>
      </div>

      {/* Chat Area */}
      <main
        ref={scrollContainerRef as React.RefObject<HTMLElement>}
        className="flex-1 overflow-y-auto px-3 sm:px-6 lg:px-8 xl:px-12 py-4"
      >
        {messages.length === 0 ? (
          // Welcome screen before demo starts
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-20 h-20 bg-[var(--accent)] flex items-center justify-center mb-6">
              <svg className="w-10 h-10 text-[var(--color-industrial-900)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>

            <h2 className="font-mono text-2xl font-bold tracking-tight text-industrial mb-3">
              Welcome to Space Goose Demo
            </h2>

            <p className="font-mono text-sm text-industrial-secondary max-w-lg mb-6">
              Experience how our multi-agent AI system analyzes commercial real estate properties,
              identifies tenant gaps, and automates client outreach.
            </p>

            <div className="bg-[var(--bg-tertiary)] p-6 border border-industrial max-w-md mb-8">
              <h3 className="label-technical mb-3 text-left">This demo will showcase:</h3>
              <ul className="font-mono text-xs text-industrial-secondary space-y-2 text-left">
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-[var(--accent)]"></span>
                  Demographics analysis from Census data
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-[var(--color-success)]"></span>
                  Tenant roster from Google Places
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-[var(--color-warning)]"></span>
                  Foot traffic patterns and metrics
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-[var(--color-error)]"></span>
                  Tenant gap analysis and opportunity identification
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-cyan-500"></span>
                  Tenant matching based on client criteria
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-teal-500"></span>
                  Automated personalized outreach
                </li>
              </ul>
            </div>

            <button
              onClick={advanceStep}
              className="btn-industrial-primary px-8 py-4 text-base"
            >
              <span>Start Demo</span>
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </button>

            <p className="font-mono text-xs text-industrial-muted mt-4">
              or press <kbd className="px-2 py-0.5 bg-[var(--bg-tertiary)] text-industrial-secondary font-mono border border-industrial-subtle">Enter</kbd> to begin
            </p>
          </div>
        ) : (
          <div className={`${isDesktop ? 'max-w-5xl mx-auto' : 'max-w-4xl mx-auto'}`}>
            {/* Workflow Progress - inline version (shown on mobile only) */}
            {workflowSteps.length > 0 && (
              <div className="mb-6 sm:hidden">
                <WorkflowProgress steps={workflowSteps} />
              </div>
            )}

            {/* Messages */}
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}

            {/* Processing indicator */}
            {isProcessing && !isWaitingForInput && (
              <div className="flex items-center gap-3 py-4">
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-[var(--accent)] animate-pulse" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-1.5 h-1.5 bg-[var(--accent)] animate-pulse" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-1.5 h-1.5 bg-[var(--accent)] animate-pulse" style={{ animationDelay: '300ms' }}></span>
                </div>
                <span className="font-mono text-xs text-industrial-muted uppercase tracking-wide">
                  {activeAgentType ? `${activeAgentType.replace('-', ' ')} is working...` : 'Processing...'}
                </span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </main>

      {/* Agent Status Strip - Warp-style horizontal strip above input */}
      <AgentStatusStrip
        workflowSteps={workflowSteps}
        activeAgentType={activeAgentType}
        isProcessing={isProcessing}
      />

      {/* Footer with controls */}
      <footer className="flex-shrink-0 px-3 sm:px-6 py-3 sm:py-4 bg-[var(--bg-elevated)] border-t border-industrial">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="font-mono text-xs text-industrial-muted">
              Step {currentStep} of {totalSteps}
            </span>
            {isComplete && (
              <span className="font-mono text-xs text-[var(--color-success)] flex items-center gap-1 uppercase tracking-wide">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                Demo Complete
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {messages.length > 0 && (
              <button
                onClick={resetDemo}
                className="font-mono text-xs uppercase tracking-wide text-industrial-muted hover:text-industrial
                         hover:bg-[var(--bg-secondary)] px-3 py-1.5 transition-colors"
              >
                Restart
              </button>
            )}

            <button
              onClick={advanceStep}
              disabled={!isWaitingForInput && !isComplete}
              className="btn-industrial-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isComplete ? (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Restart Demo
                </>
              ) : isWaitingForInput ? (
                <>
                  Continue
                  <kbd className="px-1.5 py-0.5 bg-[var(--accent-hover)] text-[10px] font-mono">Enter</kbd>
                </>
              ) : (
                <>
                  <div className="w-4 h-4 border border-[var(--color-industrial-900)] border-t-transparent animate-spin"></div>
                  Processing
                </>
              )}
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
