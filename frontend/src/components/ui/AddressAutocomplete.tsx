import { useState, useRef, useCallback, useEffect } from 'react';
import { MapPin } from 'lucide-react';
import { api } from '../../lib/axios';

interface AddressAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  inputClassName?: string;
  disabled?: boolean;
  /**
   * Only fetch suggestions when the text looks like a street address
   * (leading street number, or a street-suffix word). Use this when the
   * field also accepts free-form notes, so prose doesn't trigger popups.
   */
  onlyWhenAddressLike?: boolean;
}

interface Suggestion {
  description: string;
  place_id: string;
  main_text: string;
  secondary_text: string;
}

const DEFAULT_INPUT_CLASS =
  'w-full pl-9 pr-4 py-2.5 bg-[var(--bg-secondary)] border border-[var(--border-default)] rounded-xl text-sm text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]/30 transition-colors';

const STREET_SUFFIX =
  /\b(st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|ln|lane|way|pkwy|parkway|hwy|highway|plaza|ct|court)\b/i;

function looksAddressLike(text: string): boolean {
  const t = text.trim();
  return /^\d+\s+\S/.test(t) || STREET_SUFFIX.test(t);
}

/**
 * Address input with typeahead suggestions.
 *
 * Suggestions come from our backend proxy (`GET /places/autocomplete`) —
 * never from Google directly: the legacy Places JSON API has no CORS
 * headers, and calling it client-side would mean shipping the API key in
 * the bundle. When the backend reports the key isn't configured, this
 * degrades silently into a plain text input. Free text is always allowed;
 * suggestions assist, they never restrict.
 */
export function AddressAutocomplete({
  value,
  onChange,
  placeholder = 'Enter an address...',
  className = '',
  inputClassName = DEFAULT_INPUT_CLASS,
  disabled = false,
  onlyWhenAddressLike = false,
}: AddressAutocompleteProps) {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const debounceRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const backendEnabledRef = useRef(true);
  const suppressNextFetchRef = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const closeList = useCallback(() => {
    setSuggestions([]);
    setIsOpen(false);
    setHighlightedIndex(-1);
  }, []);

  const fetchSuggestions = useCallback(
    async (input: string) => {
      const q = input.trim();
      if (
        !backendEnabledRef.current ||
        q.length < 3 ||
        (onlyWhenAddressLike && !looksAddressLike(q))
      ) {
        closeList();
        return;
      }

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const { data } = await api.get<{ enabled: boolean; suggestions: Suggestion[] }>(
          '/places/autocomplete',
          { params: { q }, signal: controller.signal },
        );
        if (data.enabled === false) {
          // Backend has no Places key — stop asking for this session.
          backendEnabledRef.current = false;
          closeList();
          return;
        }
        const items = (data.suggestions ?? []).slice(0, 6);
        setSuggestions(items);
        setIsOpen(items.length > 0);
        setHighlightedIndex(-1);
      } catch {
        // Aborted or transient failure — an assist should never surface errors.
        closeList();
      }
    },
    [closeList, onlyWhenAddressLike],
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = e.target.value;
      onChange(newValue);

      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (suppressNextFetchRef.current) {
        suppressNextFetchRef.current = false;
        return;
      }
      debounceRef.current = window.setTimeout(() => {
        fetchSuggestions(newValue);
      }, 300);
    },
    [onChange, fetchSuggestions],
  );

  const handleSelect = useCallback(
    (suggestion: Suggestion) => {
      suppressNextFetchRef.current = true;
      onChange(suggestion.description);
      closeList();
    },
    [onChange, closeList],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isOpen || suggestions.length === 0) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightedIndex((prev) => Math.min(prev + 1, suggestions.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === 'Enter' && highlightedIndex >= 0) {
        e.preventDefault();
        handleSelect(suggestions[highlightedIndex]);
      } else if (e.key === 'Escape') {
        setIsOpen(false);
      }
    },
    [isOpen, suggestions, highlightedIndex, handleSelect],
  );

  // Close on click outside; abort any in-flight fetch on unmount.
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      abortRef.current?.abort();
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <div className="relative">
        <MapPin
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-industrial-muted"
        />
        <input
          type="text"
          value={value}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setIsOpen(true)}
          placeholder={placeholder}
          disabled={disabled}
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          className={inputClassName}
        />
      </div>

      {isOpen && suggestions.length > 0 && (
        <div
          role="listbox"
          className="absolute z-50 w-full mt-1 bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-xl shadow-lg overflow-hidden"
        >
          {suggestions.map((suggestion, index) => (
            <button
              key={suggestion.place_id || suggestion.description}
              type="button"
              role="option"
              aria-selected={index === highlightedIndex}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => handleSelect(suggestion)}
              onMouseEnter={() => setHighlightedIndex(index)}
              className={`w-full px-4 py-2.5 text-left text-sm transition-colors flex items-start gap-2 ${
                index === highlightedIndex
                  ? 'bg-[var(--accent-subtle)] text-industrial'
                  : 'text-industrial-secondary hover:bg-[var(--bg-secondary)]'
              }`}
            >
              <MapPin size={14} className="mt-0.5 flex-shrink-0 text-industrial-muted" />
              <div>
                <div className="font-medium">{suggestion.main_text}</div>
                {suggestion.secondary_text && (
                  <div className="text-xs text-industrial-muted">{suggestion.secondary_text}</div>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
