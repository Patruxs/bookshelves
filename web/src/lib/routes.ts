export function bookPath(id: string): string {
  return `/book/${encodeURIComponent(id)}`;
}

export function browsePath(params: { category?: string; topic?: string; q?: string } = {}): string {
  const search = new URLSearchParams();
  if (params.category) search.set("category", params.category);
  if (params.topic) search.set("topic", params.topic);
  if (params.q) search.set("q", params.q);
  const query = search.toString();
  return query ? `/browse?${query}` : "/browse";
}

export function viewerUrl(pdfUrl: string): string {
  return `https://docs.google.com/viewer?url=${encodeURIComponent(pdfUrl)}`;
}
