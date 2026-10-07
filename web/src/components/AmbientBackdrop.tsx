import { assetUrl } from "../lib/data";
import type { Book } from "../lib/types";

export function AmbientBackdrop({ book }: { book: Book }) {
  if (!book.cover) return null;
  return (
    <div className="ambient" aria-hidden="true">
      <img src={assetUrl(book.cover)} alt="" decoding="async" />
    </div>
  );
}
