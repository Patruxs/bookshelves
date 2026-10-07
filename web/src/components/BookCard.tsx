import { ClickableCard } from "@astryxdesign/core/ClickableCard";
import { Text } from "@astryxdesign/core/Text";
import { VStack } from "@astryxdesign/core/VStack";
import { bookPath } from "../lib/routes";
import { topicLeaf } from "../lib/text";
import type { Book } from "../lib/types";
import { BookCover } from "./BookCover";

interface BookCardProps {
  book: Book;
  showCategory?: boolean;
}

export function BookCard({ book, showCategory = false }: BookCardProps) {
  return (
    <ClickableCard label={book.title} href={bookPath(book.id)} variant="transparent" padding={0} className="book-card">
      <VStack gap={2}>
        <BookCover book={book} />
        <VStack gap={0.5}>
          <Text type="label" maxLines={2} hasTruncateTooltip={false}>
            {book.title}
          </Text>
          <Text type="supporting" maxLines={1} hasTruncateTooltip={false}>
            {showCategory ? book.category : topicLeaf(book.topic)}
          </Text>
        </VStack>
      </VStack>
    </ClickableCard>
  );
}
