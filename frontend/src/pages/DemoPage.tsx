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
  const messageVariant = isDesktop ? 'card' : 'bubble';

  return (
    <div className="h-screen w-screen flex flex-col bg-gray-900">
      {/* Demo Header - collapsible on scroll */}
      <header
        className={`flex-shrink-0 flex items-center justify-between px-3 sm:px-6 py-3 sm:py-4 bg-gray-950 border-b border-gray-800 transition-all duration-300 ${
          isHeaderVisible ? 'translate-y-0 opacity-100' : '-translate-y-full opacity-0 absolute top-0 left-0 right-0 z-40'
        }`}
      >
        <div className="flex items-center gap-3">
          {/* Logo */}
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
            <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">SpaceFit AI</h1>
            <p className="text-xs text-gray-400">Interactive Demo - {DEMO_PROPERTY.name}</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Progress indicator */}
          <div className="hidden sm:flex items-center gap-2">
            <div className="text-xs text-gray-400">Progress</div>
            <div className="w-24 h-2 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-500"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <div className="text-xs text-gray-400">{progressPercent}%</div>
          </div>

          <button
            onClick={handleExitDemo}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm
                     rounded-lg transition-colors"
          >
            Exit Demo
          </button>
        </div>
      </header>

      {/* Demo Banner */}
      <div className="flex-shrink-0 px-3 sm:px-4 py-2 sm:py-3 bg-gradient-to-r from-indigo-900/80 via-purple-900/80 to-indigo-900/80 border-b border-indigo-500/30">
        <div className="flex items-center justify-center gap-2 sm:gap-4">
          <div className="flex items-center gap-2">
            {/* Pulsing indicator */}
            <span className="relative flex h-2 w-2 sm:h-3 sm:w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 sm:h-3 sm:w-3 bg-indigo-500"></span>
            </span>
            <span className="text-indigo-200 text-xs sm:text-sm font-medium">
              <span className="hidden sm:inline">Interactive </span>Demo
            </span>
          </div>

          <span className="text-indigo-400 hidden sm:inline">|</span>

          <div className="flex items-center gap-1 sm:gap-2">
            <kbd className="px-1.5 sm:px-2 py-0.5 sm:py-1 bg-gray-800 text-gray-300 text-xs rounded border border-gray-600">
              Enter
            </kbd>
            <span className="text-indigo-200 text-xs sm:text-sm">
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
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mb-6 shadow-lg shadow-indigo-500/30">
              <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>

            <h2 className="text-2xl font-bold text-white mb-3">
              Welcome to SpaceFit AI Demo
            </h2>

            <p className="text-gray-400 max-w-lg mb-6">
              Experience how our multi-agent AI system analyzes commercial real estate properties,
              identifies void opportunities, and automates client outreach.
            </p>

            <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700 max-w-md mb-8">
              <h3 className="text-sm font-medium text-gray-300 mb-3">This demo will showcase:</h3>
              <ul className="text-sm text-gray-400 space-y-2 text-left">
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                  Demographics analysis from Census data
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-500"></span>
                  Tenant roster from Google Places
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-orange-500"></span>
                  Foot traffic patterns and metrics
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-red-500"></span>
                  Void analysis and opportunity identification
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-500"></span>
                  Tenant matching based on client criteria
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-teal-500"></span>
                  Automated personalized outreach
                </li>
              </ul>
            </div>

            <button
              onClick={advanceStep}
              className="flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-indigo-600 to-purple-600
                       hover:from-indigo-500 hover:to-purple-500 text-white font-medium text-lg
                       rounded-xl transition-all shadow-lg shadow-indigo-500/30
                       hover:shadow-indigo-500/50 hover:scale-105"
            >
              <span>Start Demo</span>
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </button>

            <p className="text-gray-500 text-sm mt-4">
              or press <kbd className="px-2 py-0.5 bg-gray-700 text-gray-300 rounded">Enter</kbd> to begin
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
              <ChatMessage key={message.id} message={message} variant={messageVariant} />
            ))}

            {/* Processing indicator */}
            {isProcessing && !isWaitingForInput && (
              <div className="flex items-center gap-3 py-4">
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </div>
                <span className="text-sm text-gray-400">
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
      <footer className="flex-shrink-0 px-3 sm:px-6 py-3 sm:py-4 bg-gray-950 border-t border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">
              Step {currentStep} of {totalSteps}
            </span>
            {isComplete && (
              <span className="text-sm text-green-400 flex items-center gap-1">
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
                className="px-3 py-1.5 text-sm text-gray-400 hover:text-white
                         hover:bg-gray-700 rounded-lg transition-colors"
              >
                Restart
              </button>
            )}

            <button
              onClick={advanceStep}
              disabled={!isWaitingForInput && !isComplete}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500
                       disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed
                       text-white text-sm rounded-lg transition-colors"
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
                  <kbd className="px-1.5 py-0.5 bg-indigo-700 text-xs rounded">Enter</kbd>
                </>
              ) : (
                <>
                  <span className="w-4 h-4 border-2 border-gray-500 border-t-transparent rounded-full animate-spin"></span>
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
