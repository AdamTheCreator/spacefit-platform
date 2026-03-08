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
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div
        className={`relative flex items-end w-full rounded-2xl border transition-all duration-200 ${
          isFocused
            ? 'border-[var(--border-strong)] bg-[var(--bg-primary)] shadow-md'
            : 'border-[var(--border-default)] bg-[var(--bg-secondary)]'
        } ${disabled ? 'opacity-50' : ''}`}
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
          className="w-full pl-4 pr-12 py-3 bg-transparent text-[15px] text-industrial placeholder:text-industrial-muted resize-none outline-none rounded-2xl min-h-[52px] max-h-[200px] scrollbar-thin"
        />
        
        <div className="absolute right-2 bottom-2">
          <button
            type="submit"
            disabled={disabled || !input.trim()}
            className="w-8 h-8 flex items-center justify-center rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:bg-[var(--bg-tertiary)] disabled:text-industrial-muted transition-all"
          >
            <Send size={16} strokeWidth={2.5} />
          </button>
        </div>
      </div>
    </form>
  );
}
