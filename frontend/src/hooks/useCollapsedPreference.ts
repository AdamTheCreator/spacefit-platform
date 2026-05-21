import { useCallback, useState } from 'react';

export function useCollapsedPreference(
  storageKey: string,
  defaultValue = false,
) {
  const [collapsed, setCollapsedState] = useState<boolean>(() => {
    if (typeof window === 'undefined') return defaultValue;
    const stored = window.localStorage.getItem(storageKey);
    if (stored === null) return defaultValue;
    return stored === 'true';
  });

  const setCollapsed = useCallback(
    (value: boolean | ((prev: boolean) => boolean)) => {
      setCollapsedState((prev) => {
        const next = typeof value === 'function' ? value(prev) : value;
        try {
          window.localStorage.setItem(storageKey, String(next));
        } catch {
          // ignore quota / privacy-mode failures; the in-memory state still updates
        }
        return next;
      });
    },
    [storageKey],
  );

  const toggle = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, [setCollapsed]);

  return [collapsed, toggle, setCollapsed] as const;
}
