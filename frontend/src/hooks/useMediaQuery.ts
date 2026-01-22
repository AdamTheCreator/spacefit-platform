import { useState, useEffect } from 'react';

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.matchMedia(query).matches;
    }
    return false;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia(query);
    setMatches(mediaQuery.matches);

    const handler = (event: MediaQueryListEvent) => {
      setMatches(event.matches);
    };

    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, [query]);

  return matches;
}

// Convenience hooks for common breakpoints (Tailwind defaults)
export function useIsDesktop() {
  return useMediaQuery('(min-width: 1024px)'); // lg breakpoint
}

export function useIsTablet() {
  return useMediaQuery('(min-width: 768px)'); // md breakpoint
}

export function useIsMobile() {
  return !useMediaQuery('(min-width: 640px)'); // below sm breakpoint
}
