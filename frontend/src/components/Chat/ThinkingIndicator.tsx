interface ThinkingIndicatorProps {
  isVisible: boolean;
}

export function ThinkingIndicator({ isVisible }: ThinkingIndicatorProps) {
  if (!isVisible) return null;

  return (
    <div className="flex items-start gap-3 mb-4 animate-fadeIn">
      {/* Avatar with pulsing animation */}
      <div className="relative flex-shrink-0">
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="w-5 h-5 text-white"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M12 2v4M12 18v4M2 12h4M18 12h4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
          </svg>
        </div>
        {/* Pulsing ring */}
        <div className="absolute inset-0 rounded-full bg-blue-500 opacity-30 animate-ping" />
        <div
          className="absolute inset-0 rounded-full border-2 border-blue-400 opacity-50"
          style={{ animation: 'pulse 2s ease-in-out infinite' }}
        />
      </div>

      {/* Thinking bubble */}
      <div className="bg-gray-800/60 backdrop-blur-sm rounded-2xl rounded-tl-sm px-4 py-3 max-w-md">
        <div className="flex items-center gap-3">
          {/* Animated dots */}
          <div className="flex gap-1.5">
            <span
              className="w-2 h-2 rounded-full bg-blue-400"
              style={{ animation: 'bounce 1.4s ease-in-out infinite', animationDelay: '0s' }}
            />
            <span
              className="w-2 h-2 rounded-full bg-purple-400"
              style={{ animation: 'bounce 1.4s ease-in-out infinite', animationDelay: '0.2s' }}
            />
            <span
              className="w-2 h-2 rounded-full bg-blue-400"
              style={{ animation: 'bounce 1.4s ease-in-out infinite', animationDelay: '0.4s' }}
            />
          </div>
          <span className="text-sm text-gray-400">SpaceFit is thinking...</span>
        </div>

        {/* Shimmer bar */}
        <div className="mt-3 h-1 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full w-1/2 bg-gradient-to-r from-transparent via-blue-500 to-transparent rounded-full"
            style={{
              animation: 'shimmer 1.5s ease-in-out infinite',
            }}
          />
        </div>
      </div>

      <style>{`
        @keyframes bounce {
          0%, 60%, 100% {
            transform: translateY(0);
          }
          30% {
            transform: translateY(-8px);
          }
        }
        @keyframes shimmer {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(200%);
          }
        }
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fadeIn {
          animation: fadeIn 0.3s ease-out;
        }
      `}</style>
    </div>
  );
}
