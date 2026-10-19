import { browsePath } from "../lib/routes";
import type { Book } from "../lib/types";
import { BookCover } from "./BookCover";
import { RouterLink } from "./RouterLink";

interface GenreTileProps {
  name: string;
  count: number;
  topicCount: number;
  covers: Book[];
  index: number;
}

const GRADIENT_COUNT = 6;

export function GenreTile({ name, count, topicCount, covers, index }: GenreTileProps) {
  const gradient = `var(--tile-gradient-${(index % GRADIENT_COUNT) + 1})`;
  return (
    <RouterLink
      href={browsePath({ category: name })}
      className="genre-tile"
      style={{ "--tile-gradient": gradient } as React.CSSProperties}
      aria-label={`${name}, ${count} books in ${topicCount} topics`}
    >
      <div className="genre-tile-covers" aria-hidden="true">
        {covers.map((book, coverIndex) => (
          <div key={book.id} className={`genre-tile-cover genre-tile-cover-${coverIndex}`}>
            <BookCover book={book} />
          </div>
        ))}
      </div>
      <span className="genre-tile-text">
        <span className="genre-tile-name">{name}</span>
        <span className="genre-tile-count">
          {count} books · {topicCount} topics
        </span>
      </span>
    </RouterLink>
  );
}
