import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { buildCategories, loadRawBooks, mergeBooks } from "./data";
import { STORAGE_KEYS, useStoredState } from "./storage";
import type { Book, CategorySummary } from "./types";

type LoadStatus = "loading" | "ready" | "error";

interface LibraryValue {
  status: LoadStatus;
  error: string;
  books: Book[];
  categories: CategorySummary[];
  findBook: (id: string) => Book | undefined;
  recentIds: string[];
  markViewed: (id: string) => void;
  reload: () => void;
}

const LibraryContext = createContext<LibraryValue | null>(null);

const RECENT_LIMIT = 12;

export function LibraryProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<LoadStatus>("loading");
  const [error, setError] = useState("");
  const [books, setBooks] = useState<Book[]>([]);
  const [attempt, setAttempt] = useState(0);
  const [recentIds, setRecentIds] = useStoredState<string[]>(STORAGE_KEYS.recent, []);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    loadRawBooks()
      .then(raw => {
        if (cancelled) return;
        setBooks(mergeBooks(raw));
        setStatus("ready");
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setError(reason instanceof Error ? reason.message : String(reason));
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const categories = useMemo(() => buildCategories(books), [books]);
  const byId = useMemo(() => {
    const map = new Map<string, Book>();
    for (const book of books) {
      for (const rawId of book.rawIds) map.set(rawId, book);
    }
    return map;
  }, [books]);

  const findBook = useCallback((id: string) => byId.get(id), [byId]);
  const markViewed = useCallback(
    (id: string) => {
      setRecentIds(current => [id, ...current.filter(entry => entry !== id)].slice(0, RECENT_LIMIT));
    },
    [setRecentIds]
  );
  const reload = useCallback(() => setAttempt(current => current + 1), []);

  const value = useMemo<LibraryValue>(
    () => ({
      status,
      error,
      books,
      categories,
      findBook,
      recentIds,
      markViewed,
      reload
    }),
    [status, error, books, categories, findBook, recentIds, markViewed, reload]
  );

  return <LibraryContext.Provider value={value}>{children}</LibraryContext.Provider>;
}

export function useLibrary(): LibraryValue {
  const value = useContext(LibraryContext);
  if (!value) throw new Error("useLibrary must be used inside LibraryProvider");
  return value;
}
