const LOWER_WORDS = new Set(["a", "an", "the", "and", "or", "but", "in", "on", "of", "to", "for", "with", "by", "at", "from", "as", "is"]);

export function cleanTitle(title: string): string {
  return String(title || "")
    .replace(/[-_]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .map((word, index) => {
      const lower = word.toLowerCase();
      if (index > 0 && LOWER_WORDS.has(lower)) return lower;
      return lower.charAt(0).toUpperCase() + lower.slice(1);
    })
    .join(" ");
}

export function normalizeForSearch(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/đ/g, "d");
}

export function topicParts(topic: string): string[] {
  return String(topic || "")
    .split("/")
    .map(part => part.trim())
    .filter(Boolean);
}

export function topicLeaf(topic: string): string {
  const parts = topicParts(topic);
  return parts[parts.length - 1] || "";
}

export function hashString(value: string): number {
  let hashed = 0;
  for (let index = 0; index < value.length; index++) {
    hashed = (hashed << 5) - hashed + value.charCodeAt(index);
    hashed |= 0;
  }
  return Math.abs(hashed);
}

export function formatLabel(format: string): string {
  return format.toUpperCase();
}

export function excerpt(description: string, maxLength = 220): string {
  const text = String(description || "").replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) return text;
  const cut = text.slice(0, maxLength);
  const lastSpace = cut.lastIndexOf(" ");
  return `${cut.slice(0, lastSpace > 80 ? lastSpace : maxLength).trim()}...`;
}
