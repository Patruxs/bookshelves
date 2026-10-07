import { Carousel } from "@astryxdesign/core/Carousel";
import { Heading } from "@astryxdesign/core/Heading";
import { HStack } from "@astryxdesign/core/HStack";
import { Icon } from "@astryxdesign/core/Icon";
import { IconButton } from "@astryxdesign/core/IconButton";
import { Link } from "@astryxdesign/core/Link";
import { StackItem } from "@astryxdesign/core/Stack";
import { Text } from "@astryxdesign/core/Text";
import { VStack } from "@astryxdesign/core/VStack";
import { ChevronRight } from "lucide-react";
import { useCanHover } from "../lib/hooks";
import type { Book } from "../lib/types";
import { BookCard } from "./BookCard";

interface ShelfProps {
  title: string;
  description?: string;
  books: Book[];
  count?: number;
  href?: string;
  linkLabel?: string;
  showCategory?: boolean;
  headingLevel?: 2 | 3;
  variant?: "default" | "compact";
}

export function Shelf({
  title,
  description,
  books,
  count,
  href,
  linkLabel = "View all",
  showCategory = false,
  headingLevel = 2,
  variant = "default"
}: ShelfProps) {
  const canHover = useCanHover();
  if (!books.length) return null;
  const countText =
    typeof count === "number" ? (
      <Text type="supporting" hasTabularNumbers>
        {count} {count === 1 ? "book" : "books"}
      </Text>
    ) : null;
  return (
    <VStack gap={3} className="shelf">
      {variant === "compact" ? (
        <HStack gap={2} vAlign="center" className="shelf-head">
          <StackItem size="fill">
            <HStack gap={2} vAlign="center" wrap="wrap">
              <Heading level={3} accessibilityLevel={headingLevel}>
                {href ? (
                  <Link href={href} color="inherit">
                    {title}
                  </Link>
                ) : (
                  title
                )}
              </Heading>
              {countText}
            </HStack>
          </StackItem>
          {href ? (
            <IconButton label={`${linkLabel}: ${title}`} icon={<Icon icon={ChevronRight} />} variant="ghost" size="md" href={href} />
          ) : null}
        </HStack>
      ) : (
        <VStack gap={1}>
          <HStack gap={3} vAlign="center" className="shelf-head">
            <Heading level={headingLevel}>{title}</Heading>
            {countText}
            <StackItem size="fill">
              <span />
            </StackItem>
            {href ? (
              <Link href={href} isStandalone>
                {linkLabel}
              </Link>
            ) : null}
          </HStack>
          {description ? (
            <Text type="supporting" maxLines={1} hasTruncateTooltip={false}>
              {description}
            </Text>
          ) : null}
        </VStack>
      )}
      <Carousel gap={variant === "compact" ? 3 : 4} hasSnap hasButtons={canHover} aria-label={title} className="shelf-carousel">
        {books.map(book => (
          <div key={book.id} className="shelf-item">
            <BookCard book={book} showCategory={showCategory} />
          </div>
        ))}
      </Carousel>
    </VStack>
  );
}
