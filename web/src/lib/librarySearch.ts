import type { SearchableItem } from "@astryxdesign/core/Typeahead";
import { useMemo } from "react";
import { useLibrary } from "./library";
import { bookPath, browsePath } from "./routes";
import { searchBooks } from "./search";
import type { Book } from "./types";

export interface SearchItemData {
  group: string;
  detail: string;
  book?: Book;
}

export type SearchItem = SearchableItem<SearchItemData>;

export interface LibrarySearch {
  bootstrap: () => SearchItem[];
  search: (query: string) => SearchItem[];
}

const RECENT_LIMIT = 6;
const GROUP_LIMIT = 8;
const RESULT_LIMIT = 24;
const BOOK_PREFIX = "book:";
const CATEGORY_PREFIX = "category:";

function bookDetail(book: Book): string {
  const topicLeaf = book.topicParts[book.topicParts.length - 1] ?? book.topic;
  return [topicLeaf, book.formats.map(format => format.toUpperCase()).join(", ")].filter(Boolean).join(" · ");
}

function bookItem(book: Book, group: string): SearchItem {
  return { id: `${BOOK_PREFIX}${book.id}`, label: book.title, auxiliaryData: { group, detail: bookDetail(book), book } };
}

function groupByCategory(matches: Book[]): SearchItem[] {
  const groups = new Map<string, Book[]>();
  let total = 0;
  for (const book of matches) {
    if (total >= RESULT_LIMIT) break;
    const group = groups.get(book.category) ?? [];
    if (group.length >= GROUP_LIMIT) continue;
    group.push(book);
    groups.set(book.category, group);
    total += 1;
  }
  return [...groups].flatMap(([category, groupBooks]) => groupBooks.map(book => bookItem(book, category)));
}

export function searchItemHref(id: string): string | null {
  if (id.startsWith(BOOK_PREFIX)) return bookPath(id.slice(BOOK_PREFIX.length));
  if (id.startsWith(CATEGORY_PREFIX)) return browsePath({ category: id.slice(CATEGORY_PREFIX.length) });
  return null;
}

export function useLibrarySearch(shelvesGroup: string): LibrarySearch {
  const { books, categories, recentIds, findBook } = useLibrary();

  return useMemo<LibrarySearch>(() => {
    const categoryItems: SearchItem[] = categories.map(category => ({
      id: `${CATEGORY_PREFIX}${category.name}`,
      label: category.name,
      auxiliaryData: { group: shelvesGroup, detail: `${category.count} ${category.count === 1 ? "book" : "books"}` }
    }));
    const bootstrap = () => {
      const recentItems = recentIds
        .map(id => findBook(id))
        .filter((book): book is Book => Boolean(book))
        .slice(0, RECENT_LIMIT)
        .map(book => bookItem(book, "Recently viewed"));
      return [...recentItems, ...categoryItems];
    };
    return {
      bootstrap,
      search: (query: string) => (query.trim() ? groupByCategory(searchBooks(books, query)) : bootstrap())
    };
  }, [books, categories, recentIds, findBook, shelvesGroup]);
}
