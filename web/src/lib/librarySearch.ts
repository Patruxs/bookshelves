import type { SearchableItem } from "@astryxdesign/core/Typeahead";
import { useMemo } from "react";
import { useLibrary } from "./library";
import { bookPath, browsePath } from "./routes";
import { searchHits, searchTokens, type SearchField } from "./search";
import { normalizeForSearch, topicLeaf } from "./text";
import type { Book, CategorySummary, TopicNode } from "./types";

export interface SearchItemData {
  group: string;
  detail: string;
  book?: Book;
  field?: SearchField;
  snippet?: string;
  tokens?: string[];
  kind: "book" | "category" | "topic" | "more";
}

export type SearchItem = SearchableItem<SearchItemData>;

export interface LibrarySearch {
  bootstrap: () => SearchItem[];
  search: (query: string) => SearchItem[];
}

const RECENT_LIMIT = 6;
const BOOK_LIMIT = 12;
const TOPIC_LIMIT = 4;
const BOOK_PREFIX = "book:";
const CATEGORY_PREFIX = "category:";
const TOPIC_PREFIX = "topic:";
const MORE_PREFIX = "more:";

function bookDetail(book: Book): string {
  return [book.category, topicLeaf(book.topic), book.formats.map(format => format.toUpperCase()).join(", ")].filter(Boolean).join(" · ");
}

function bookItem(book: Book, group: string, extra: Partial<SearchItemData> = {}): SearchItem {
  return { id: `${BOOK_PREFIX}${book.id}`, label: book.title, auxiliaryData: { group, detail: bookDetail(book), book, kind: "book", ...extra } };
}

interface TopicEntry {
  category: string;
  node: TopicNode;
}

function flattenTopics(categories: CategorySummary[]): TopicEntry[] {
  const entries: TopicEntry[] = [];
  const walk = (category: string, nodes: TopicNode[]) => {
    for (const node of nodes) {
      entries.push({ category, node });
      walk(category, node.children);
    }
  };
  for (const category of categories) walk(category.name, category.topics);
  return entries;
}

function nameMatches(name: string, tokens: string[]): boolean {
  const normalized = normalizeForSearch(name);
  const parts = normalized.split(/[^a-z0-9+#.]+/).filter(Boolean);
  return tokens.every(token => parts.some(part => part.startsWith(token)) || normalized.includes(token));
}

export function searchItemHref(id: string): string | null {
  if (id.startsWith(BOOK_PREFIX)) return bookPath(id.slice(BOOK_PREFIX.length));
  if (id.startsWith(CATEGORY_PREFIX)) return browsePath({ category: id.slice(CATEGORY_PREFIX.length) });
  if (id.startsWith(TOPIC_PREFIX)) {
    const [category, topic] = id.slice(TOPIC_PREFIX.length).split("\u0000");
    return browsePath({ category, topic });
  }
  if (id.startsWith(MORE_PREFIX)) return browsePath({ q: id.slice(MORE_PREFIX.length) });
  return null;
}

export function useLibrarySearch(shelvesGroup: string): LibrarySearch {
  const { books, categories, recentIds, findBook } = useLibrary();

  return useMemo<LibrarySearch>(() => {
    const categoryItems: SearchItem[] = categories.map(category => ({
      id: `${CATEGORY_PREFIX}${category.name}`,
      label: category.name,
      auxiliaryData: { group: shelvesGroup, detail: `${category.count} ${category.count === 1 ? "book" : "books"}`, kind: "category" }
    }));
    const topicEntries = flattenTopics(categories);

    const bootstrap = () => {
      const recentItems = recentIds
        .map(id => findBook(id))
        .filter((book): book is Book => Boolean(book))
        .slice(0, RECENT_LIMIT)
        .map(book => bookItem(book, "Recently viewed"));
      return [...recentItems, ...categoryItems];
    };

    const search = (query: string): SearchItem[] => {
      const trimmed = query.trim();
      if (!trimmed) return bootstrap();
      const tokens = searchTokens(trimmed);
      const hits = searchHits(books, trimmed);
      const items: SearchItem[] = hits
        .slice(0, BOOK_LIMIT)
        .map(hit => bookItem(hit.book, "Books", { field: hit.field, snippet: hit.snippet, tokens }));
      const topicItems: SearchItem[] = topicEntries
        .filter(entry => nameMatches(entry.node.name, tokens))
        .slice(0, TOPIC_LIMIT)
        .map(entry => ({
          id: `${TOPIC_PREFIX}${entry.category}\u0000${entry.node.path}`,
          label: entry.node.name,
          auxiliaryData: {
            group: "Topics",
            detail: `${entry.category} · ${entry.node.count} ${entry.node.count === 1 ? "book" : "books"}`,
            kind: "topic",
            tokens
          }
        }));
      const shelfItems = categoryItems
        .filter(item => nameMatches(item.label, tokens))
        .map(item => ({ ...item, auxiliaryData: { ...item.auxiliaryData!, group: "Shelves", tokens } }));
      const more: SearchItem[] =
        hits.length > BOOK_LIMIT
          ? [
              {
                id: `${MORE_PREFIX}${trimmed}`,
                label: `See all ${hits.length} results in Browse`,
                auxiliaryData: { group: "Books", detail: "", kind: "more" }
              }
            ]
          : [];
      return [...items, ...more, ...topicItems, ...shelfItems];
    };

    return { bootstrap, search };
  }, [books, categories, recentIds, findBook, shelvesGroup]);
}
