import { Carousel } from "@astryxdesign/core/Carousel";
import { Heading } from "@astryxdesign/core/Heading";
import { Link } from "@astryxdesign/core/Link";
import { Text } from "@astryxdesign/core/Text";
import { VStack } from "@astryxdesign/core/VStack";
import { useCanHover } from "../lib/hooks";
import type { Book } from "../lib/types";
import { BookCard } from "./BookCard";

interface ShelfProps {
  title: string;
  books: Book[];
  count?: number;
  href?: string;
  linkLabel?: string;
  showCategory?: boolean;
  headingLevel?: 2 | 3;
}

export function Shelf({ title, books, count, href, linkLabel = "See all", showCategory = false, headingLevel = 2 }: ShelfProps) {
  const canHover = useCanHover();
  if (!books.length) return null;
  return (
    <VStack gap={4} className="shelf">
      <div className="section-head">
        <Heading level={headingLevel}>{title}</Heading>
        {typeof count === "number" ? (
          <Text type="supporting" hasTabularNumbers>
            {count} {count === 1 ? "book" : "books"}
          </Text>
        ) : null}
        <span className="section-head-fill" />
        {href ? (
          <Link href={href} isStandalone size="sm">
            {linkLabel}
          </Link>
        ) : null}
      </div>
      <Carousel gap={4} hasSnap hasButtons={canHover} aria-label={title} className="shelf-carousel">
        {books.map(book => (
          <div key={book.id} className="shelf-item">
            <BookCard book={book} showCategory={showCategory} />
          </div>
        ))}
      </Carousel>
    </VStack>
  );
}
