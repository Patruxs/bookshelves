import type { Book } from "./types";

interface SearchIndex {
  title: string;
  topic: string;
  category: string;
  description: string;
}

const indexCache = new WeakMap<Book, SearchIndex>();

function indexOf(book: Book): SearchIndex {
  const cached = indexCache.get(book);
  if (cached) return cached;
  const index = {
    title: `${book.title} ${book.rawTitle}`.toLowerCase(),
    topic: book.topic.toLowerCase(),
    category: book.category.toLowerCase(),
    description: book.description.toLowerCase()
  };
  indexCache.set(book, index);
  return index;
}

export function scoreBook(book: Book, query: string): number {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return 0;
  const { title, topic, category, description } = indexOf(book);
  const tokens = normalized.split(/\s+/).filter(Boolean);
  let score = 0;
  if (title.includes(normalized)) score += 100;
  if (topic.includes(normalized)) score += 60;
  if (category.includes(normalized)) score += 40;
  if (description.includes(normalized)) score += 20;
  for (const token of tokens) {
    if (title.includes(token)) score += 30;
    if (topic.includes(token)) score += 15;
    if (category.includes(token)) score += 10;
    if (description.includes(token)) score += 5;
  }
  if (book.title.toLowerCase().startsWith(normalized)) score += 50;
  return score;
}

export function searchBooks(books: Book[], query: string, limit = Infinity): Book[] {
  const normalized = query.trim();
  if (!normalized) return books.slice(0, limit);
  return books
    .map(book => ({ book, score: scoreBook(book, normalized) }))
    .filter(entry => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.book.title.localeCompare(b.book.title))
    .slice(0, limit)
    .map(entry => entry.book);
}
