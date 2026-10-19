import { normalizeForSearch } from "./text";
import type { Book } from "./types";

export type SearchField = "title" | "topic" | "category" | "description";

export interface SearchHit {
  book: Book;
  score: number;
  field: SearchField;
  snippet: string;
}

interface SearchIndex {
  title: string;
  titleWords: string[];
  acronym: string;
  topic: string;
  topicWords: string[];
  category: string;
  categoryWords: string[];
  description: string;
  descriptionWords: string[];
}

const indexCache = new WeakMap<Book, SearchIndex>();

function words(value: string): string[] {
  return value.split(/[^a-z0-9+#.]+/).filter(Boolean);
}

function indexOf(book: Book): SearchIndex {
  const cached = indexCache.get(book);
  if (cached) return cached;
  const title = normalizeForSearch(`${book.title} ${book.rawTitle.replace(/[-_]/g, " ")}`);
  const titleWords = words(normalizeForSearch(book.title));
  const topic = normalizeForSearch(book.topic);
  const category = normalizeForSearch(book.category);
  const description = normalizeForSearch(book.description);
  const index: SearchIndex = {
    title,
    titleWords,
    acronym: titleWords.map(word => word[0]).join(""),
    topic,
    topicWords: words(topic),
    category,
    categoryWords: words(category),
    description,
    descriptionWords: words(description)
  };
  indexCache.set(book, index);
  return index;
}

export function searchTokens(query: string): string[] {
  return words(normalizeForSearch(query.trim()));
}

function editDistanceWithin(a: string, b: string, max: number): boolean {
  if (Math.abs(a.length - b.length) > max) return false;
  let previous = Array.from({ length: b.length + 1 }, (_, index) => index);
  for (let i = 1; i <= a.length; i++) {
    const current = [i];
    let rowMin = i;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      current[j] = Math.min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost);
      rowMin = Math.min(rowMin, current[j]);
    }
    if (rowMin > max) return false;
    previous = current;
  }
  return previous[b.length] <= max;
}

function matchWords(token: string, fieldWords: string[]): number {
  let best = 0;
  for (const word of fieldWords) {
    if (word === token) return 1;
    if (word.startsWith(token)) best = Math.max(best, 0.8);
    else if (token.length >= 5 && word.length >= 5 && editDistanceWithin(token, word, 1)) best = Math.max(best, 0.5);
    else if (token.length >= 3 && word.includes(token)) best = Math.max(best, 0.4);
  }
  return best;
}

const FIELD_WEIGHT: Record<SearchField, number> = { title: 100, topic: 55, category: 35, description: 18 };

function snippetAround(text: string, tokens: string[], radius = 70): string {
  const lower = normalizeForSearch(text);
  let position = -1;
  for (const token of tokens) {
    position = lower.indexOf(token);
    if (position >= 0) break;
  }
  if (position < 0) return text.slice(0, radius * 2).trim();
  const start = Math.max(0, position - radius);
  const end = Math.min(text.length, position + token0(tokens).length + radius);
  const slice = text.slice(start, end).replace(/\s+/g, " ").trim();
  return `${start > 0 ? "…" : ""}${slice}${end < text.length ? "…" : ""}`;
}

function token0(tokens: string[]): string {
  return tokens[0] ?? "";
}

export function scoreBook(book: Book, query: string): SearchHit | null {
  const tokens = searchTokens(query);
  if (!tokens.length) return null;
  const phrase = tokens.join(" ");
  const index = indexOf(book);
  let score = 0;
  let bestField: SearchField = "title";
  let bestFieldScore = 0;

  const fieldWords: Record<SearchField, string[]> = {
    title: index.titleWords,
    topic: index.topicWords,
    category: index.categoryWords,
    description: index.descriptionWords
  };

  for (const token of tokens) {
    let tokenBest = 0;
    for (const field of ["title", "topic", "category", "description"] as SearchField[]) {
      const strength = matchWords(token, fieldWords[field]);
      if (strength <= 0) continue;
      const value = strength * FIELD_WEIGHT[field];
      score += value;
      tokenBest = Math.max(tokenBest, value);
      if (value > bestFieldScore) {
        bestFieldScore = value;
        bestField = field;
      }
    }
    if (tokenBest === 0) {
      if (tokens.length === 1 && token.length >= 3 && index.acronym.startsWith(token)) {
        score += 90;
        bestField = "title";
      } else {
        return null;
      }
    }
  }

  if (tokens.length > 1) {
    if (index.title.includes(phrase)) score += 80;
    else if (index.topic.includes(phrase)) score += 40;
    else if (index.description.includes(phrase)) score += 25;
  }
  if (index.title.startsWith(phrase)) score += 60;
  if (tokens.length === 1 && index.acronym === tokens[0]) score += 120;
  score += Math.max(0, 12 - index.titleWords.length);

  const snippet = bestField === "description" ? snippetAround(book.description, tokens) : "";
  return { book, score, field: bestField, snippet };
}

export function searchHits(books: Book[], query: string, limit = Infinity): SearchHit[] {
  if (!query.trim()) return [];
  const hits: SearchHit[] = [];
  for (const book of books) {
    const hit = scoreBook(book, query);
    if (hit) hits.push(hit);
  }
  return hits.sort((a, b) => b.score - a.score || a.book.title.localeCompare(b.book.title)).slice(0, limit);
}

export function searchBooks(books: Book[], query: string, limit = Infinity): Book[] {
  if (!query.trim()) return books.slice(0, limit);
  return searchHits(books, query, limit).map(hit => hit.book);
}
