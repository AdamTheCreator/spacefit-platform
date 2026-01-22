import { useState, useEffect, useRef } from 'react';
import type { RefObject } from 'react';

export type ScrollDirection = 'up' | 'down' | null;

interface UseScrollDirectionOptions {
  threshold?: number; // Minimum scroll distance before detecting direction
  initialVisible?: boolean; // Whether header should be visible initially
}

export function useScrollDirection(
  containerRef?: RefObject<HTMLElement | null>,
  options: UseScrollDirectionOptions = {}
) {
  const { threshold = 10, initialVisible = true } = options;
  const [isVisible, setIsVisible] = useState(initialVisible);
  const [scrollDirection, setScrollDirection] = useState<ScrollDirection>(null);
  const lastScrollY = useRef(0);
  const ticking = useRef(false);

  useEffect(() => {
    const container = containerRef?.current || window;
    const getScrollY = () => {
      if (containerRef?.current) {
        return containerRef.current.scrollTop;
      }
      return window.scrollY;
    };

    const updateScrollDirection = () => {
      const scrollY = getScrollY();
      const diff = scrollY - lastScrollY.current;

      // Only update if we've scrolled past the threshold
      if (Math.abs(diff) < threshold) {
        ticking.current = false;
        return;
      }

      // At the very top, always show
      if (scrollY < 50) {
        setIsVisible(true);
        setScrollDirection(null);
      } else if (diff > 0) {
        // Scrolling down
        setIsVisible(false);
        setScrollDirection('down');
      } else {
        // Scrolling up
        setIsVisible(true);
        setScrollDirection('up');
      }

      lastScrollY.current = scrollY;
      ticking.current = false;
    };

    const onScroll = () => {
      if (!ticking.current) {
        window.requestAnimationFrame(updateScrollDirection);
        ticking.current = true;
      }
    };

    container.addEventListener('scroll', onScroll, { passive: true });
    return () => container.removeEventListener('scroll', onScroll);
  }, [containerRef, threshold]);

  return { isVisible, scrollDirection };
}
