import { Text } from "@astryxdesign/core/Text";
import { VStack } from "@astryxdesign/core/VStack";
import { bookPath } from "../lib/routes";
import { topicLeaf } from "../lib/text";
import type { Book } from "../lib/types";
import { BookCover } from "./BookCover";
import { RouterLink } from "./RouterLink";

interface RankListProps {
  books: Book[];
  variant?: "horizontal" | "vertical";
  label?: string;
}

export function RankList({ books, variant = "horizontal", label }: RankListProps) {
  const isVertical = variant === "vertical";
  return (
    <ol className={isVertical ? "rank-list rank-list-vertical" : "rank-list"} aria-label={label}>
      {books.map((book, index) => (
        <li key={book.id} className="rank-item">
          <RouterLink href={bookPath(book.id)} className="rank-link" aria-label={`${index + 1}. ${book.title}`}>
            <span className="rank-number" aria-hidden="true">
              {index + 1}
            </span>
            <span className="rank-cover">
              <BookCover book={book} />
            </span>
            {isVertical ? (
              <VStack gap={0.5} className="rank-text">
                <Text type="label" maxLines={1} hasTruncateTooltip={false}>
                  {book.title}
                </Text>
                <Text type="supporting" maxLines={1} hasTruncateTooltip={false}>
                  {book.category} · {topicLeaf(book.topic)}
                </Text>
              </VStack>
            ) : null}
          </RouterLink>
        </li>
      ))}
    </ol>
  );
}
