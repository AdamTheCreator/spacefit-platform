import { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = 'Type your message...',
}: ChatInputProps) {
  const [input, setInput] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Dynamic height: compact when idle, expands on focus or typing
  useEffect(() => {
    if (textareaRef.current) {
      const isExpanded = isFocused || input.length > 0;
      // Mobile max: 120px, Desktop max: 200px
      const maxHeight = window.innerWidth < 640 ? 120 : 200;

      if (isExpanded) {
        textareaRef.current.style.height = 'auto';
        textareaRef.current.style.height = `${Math.min(
          textareaRef.current.scrollHeight,
          maxHeight
        )}px`;
      } else {
        // Compact single-line when not focused and empty
        textareaRef.current.style.height = '44px';
      }
    }
  }, [input, isFocused]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-3 items-end">
      <div
        className={`flex-1 relative rounded-3xl border transition-all duration-150 ${
          isFocused
            ? 'border-[var(--accent)] ring-2 ring-[var(--accent)]/15 shadow-sm'
            : 'border-[var(--border-default)] hover:border-[var(--border-strong)]'
        } ${disabled ? 'opacity-60' : ''} bg-[var(--bg-secondary)]`}
      >
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="w-full px-5 py-3.5 pr-12 bg-transparent text-base sm:text-sm text-industrial placeholder:text-industrial-muted resize-none outline-none rounded-3xl min-h-[48px] transition-all"
        />
        {/* Character count indicator */}
        {input.length > 0 && (
          <span className="absolute right-3 bottom-3 text-[10px] text-industrial-muted tabular-nums">
            {input.length}
          </span>
        )}
      </div>
      <button
        type="submit"
        disabled={disabled || !input.trim()}
        aria-label="Send message"
        className="flex-shrink-0 w-11 h-11 flex items-center justify-center rounded-full bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-150 shadow-sm hover:shadow-md active:scale-95"
      >
        <Send size={18} strokeWidth={2} aria-hidden="true" />
      </button>
    </form>
  );
}
