import { useState } from "react";
import { assetUrl } from "../lib/data";
import type { Book } from "../lib/types";

interface BookCoverProps {
  book: Book;
  size?: "sm" | "md" | "lg";
  priority?: boolean;
}

export function BookCover({ book, size = "md", priority = false }: BookCoverProps) {
  const [failed, setFailed] = useState(false);
  const showImage = book.cover && !failed;
  return (
    <div className={`book-cover book-cover-${size}`} aria-hidden={showImage ? undefined : true}>
      {showImage ? (
        <img
          src={assetUrl(book.cover)}
          alt=""
          loading={priority ? "eager" : "lazy"}
          fetchPriority={priority ? "high" : "auto"}
          decoding="async"
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="book-cover-fallback">
          <span>{book.title}</span>
        </div>
      )}
    </div>
  );
}
