export type BookFormat = "pdf" | "epub" | "docx";

export interface RawBook {
  id: string;
  title: string;
  category: string;
  topic: string;
  file_path: string;
  cover: string;
  format: string;
  description: string;
  download_url: string;
}

export interface Book {
  id: string;
  rawIds: string[];
  title: string;
  rawTitle: string;
  category: string;
  topic: string;
  topicParts: string[];
  cover: string;
  description: string;
  formats: BookFormat[];
  downloads: Partial<Record<BookFormat, string>>;
}

export interface TopicNode {
  name: string;
  path: string;
  count: number;
  children: TopicNode[];
}

export interface CategorySummary {
  name: string;
  count: number;
  topics: TopicNode[];
}
