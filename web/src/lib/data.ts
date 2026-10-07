import { cleanTitle, topicLeaf, topicParts } from "./text";
import type { Book, BookFormat, CategorySummary, RawBook, TopicNode } from "./types";

export const CATEGORY_ORDER = [
  "Computer Science Fundamentals",
  "Software Engineering",
  "Career and Professional Development",
  "Personal Development and Skills",
  "University Courses"
];

export function assetUrl(path: string): string {
  const clean = String(path || "").replace(/^\/+/, "");
  return `${import.meta.env.BASE_URL}${clean}`;
}

export async function loadRawBooks(): Promise<RawBook[]> {
  const response = await fetch(assetUrl("data.json"), { cache: "no-cache" });
  if (!response.ok) throw new Error(`data.json returned HTTP ${response.status}`);
  const payload = await response.json();
  if (!Array.isArray(payload)) throw new Error("data.json is not a list");
  return payload.filter((entry): entry is RawBook => entry && typeof entry === "object" && typeof entry.id === "string");
}

function isBookFormat(value: string): value is BookFormat {
  return value === "pdf" || value === "epub" || value === "docx";
}

export function mergeBooks(rawBooks: RawBook[]): Book[] {
  const groups = new Map<string, Book>();
  for (const raw of rawBooks) {
    const title = cleanTitle(raw.title);
    const key = `${raw.category}::${raw.topic}::${title.toLowerCase()}`;
    const format = isBookFormat(raw.format) ? raw.format : "pdf";
    const existing = groups.get(key);
    if (!existing) {
      groups.set(key, {
        id: raw.id,
        rawIds: [raw.id],
        title,
        rawTitle: raw.title,
        category: raw.category,
        topic: raw.topic,
        topicParts: topicParts(raw.topic),
        cover: raw.cover || "",
        description: raw.description || "",
        formats: [format],
        downloads: { [format]: raw.download_url || "" }
      });
      continue;
    }
    existing.rawIds.push(raw.id);
    if (!existing.formats.includes(format)) existing.formats.push(format);
    if (!existing.downloads[format]) existing.downloads[format] = raw.download_url || "";
    if (!existing.description && raw.description) existing.description = raw.description;
    if (!existing.cover && raw.cover) existing.cover = raw.cover;
  }
  const order = { pdf: 0, epub: 1, docx: 2 };
  return [...groups.values()]
    .map(book => ({ ...book, formats: [...book.formats].sort((a, b) => order[a] - order[b]) }))
    .sort((a, b) => a.title.localeCompare(b.title));
}

export function categoryRank(name: string): number {
  const index = CATEGORY_ORDER.indexOf(name);
  return index === -1 ? CATEGORY_ORDER.length : index;
}

export function buildCategories(books: Book[]): CategorySummary[] {
  const byCategory = new Map<string, Book[]>();
  for (const book of books) {
    const list = byCategory.get(book.category) || [];
    list.push(book);
    byCategory.set(book.category, list);
  }
  return [...byCategory.entries()]
    .map(([name, list]) => ({ name, count: list.length, topics: buildTopicTree(list) }))
    .sort((a, b) => categoryRank(a.name) - categoryRank(b.name) || a.name.localeCompare(b.name));
}

function buildTopicTree(books: Book[]): TopicNode[] {
  const roots: TopicNode[] = [];
  for (const book of books) {
    let level = roots;
    let path = "";
    for (const part of book.topicParts) {
      path = path ? `${path}/${part}` : part;
      let node = level.find(candidate => candidate.name === part);
      if (!node) {
        node = { name: part, path, count: 0, children: [] };
        level.push(node);
      }
      node.count += 1;
      level = node.children;
    }
  }
  const sortNodes = (nodes: TopicNode[]) => {
    nodes.sort((a, b) => a.name.localeCompare(b.name));
    nodes.forEach(node => sortNodes(node.children));
  };
  sortNodes(roots);
  return roots;
}

export function topicMatches(book: Book, topicPath: string): boolean {
  if (!topicPath) return true;
  return book.topic === topicPath || book.topic.startsWith(`${topicPath}/`);
}

export function pickDailyBook(books: Book[]): Book | null {
  if (!books.length) return null;
  const today = new Date();
  const seed = today.getFullYear() * 1000 + today.getMonth() * 40 + today.getDate();
  return books[seed % books.length];
}

export function sameTopicBooks(book: Book, books: Book[], limit = 16): Book[] {
  return books.filter(candidate => candidate.id !== book.id && candidate.topic === book.topic).slice(0, limit);
}

export function sameCategoryBooks(book: Book, books: Book[], limit = 16): Book[] {
  return books
    .filter(candidate => candidate.id !== book.id && candidate.category === book.category && candidate.topic !== book.topic)
    .slice(0, limit);
}

export function greetingForHour(hour: number): string {
  if (hour >= 5 && hour <= 11) return "Good morning.";
  if (hour >= 12 && hour <= 17) return "Good afternoon.";
  return "Good evening.";
}

export interface TopicSummary {
  category: string;
  topic: string;
  leaf: string;
  count: number;
}

export function topTopics(books: Book[], limit: number): TopicSummary[] {
  const byTopic = new Map<string, TopicSummary>();
  for (const book of books) {
    const key = `${book.category}::${book.topic}`;
    const existing = byTopic.get(key);
    if (existing) {
      existing.count += 1;
      continue;
    }
    byTopic.set(key, { category: book.category, topic: book.topic, leaf: topicLeaf(book.topic), count: 1 });
  }
  return [...byTopic.values()].sort((a, b) => b.count - a.count || a.leaf.localeCompare(b.leaf)).slice(0, limit);
}

export function sampleCovers(books: Book[], category: string, n: number): Book[] {
  return books.filter(book => book.category === category && book.cover).slice(0, n);
}

export function firstBookPerCategory(books: Book[], categories: CategorySummary[], n: number): Book[] {
  return categories
    .slice(0, n)
    .map(category => books.find(book => book.category === category.name))
    .filter((book): book is Book => Boolean(book));
}
