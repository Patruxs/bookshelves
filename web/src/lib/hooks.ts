import { useEffect, useLayoutEffect, useState } from "react";

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => (typeof window === "undefined" ? false : window.matchMedia(query).matches));
  useEffect(() => {
    const media = window.matchMedia(query);
    const onChange = () => setMatches(media.matches);
    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [query]);
  return matches;
}

export const PHONE_QUERY = "(max-width: 639px)";
export const DESKTOP_QUERY = "(min-width: 1024px)";

export function useIsPhone(): boolean {
  return useMediaQuery(PHONE_QUERY);
}

export function useIsDesktop(): boolean {
  return useMediaQuery(DESKTOP_QUERY);
}

export function useCanHover(): boolean {
  return useMediaQuery("(hover: hover)");
}

export function useDocumentTitle(title: string): void {
  useEffect(() => {
    const previous = document.title;
    document.title = title ? `${title} | My Bookshelves` : "My Bookshelves";
    return () => {
      document.title = previous;
    };
  }, [title]);
}

export function scrollToTop(): void {
  const main = document.getElementById("astryx-app-shell-main") ?? document.querySelector("main");
  main?.scrollTo({ top: 0 });
  window.scrollTo({ top: 0 });
}

export function useGridColumns(): [(element: HTMLElement | null) => void, number] {
  const [element, setElement] = useState<HTMLElement | null>(null);
  const [columns, setColumns] = useState(0);
  useLayoutEffect(() => {
    if (!element) return;
    const measure = () => {
      const tracks = getComputedStyle(element).gridTemplateColumns.split(/\s+/).filter(Boolean);
      setColumns(Math.max(1, tracks.length));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [element]);
  return [setElement, columns];
}
