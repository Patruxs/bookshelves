import { ClickableCard } from "@astryxdesign/core/ClickableCard";
import { Heading } from "@astryxdesign/core/Heading";
import { Text } from "@astryxdesign/core/Text";
import { VStack } from "@astryxdesign/core/VStack";
import { browsePath } from "../lib/routes";
import type { Book } from "../lib/types";
import { BookCover } from "./BookCover";

interface CategoryTileProps {
  name: string;
  count: number;
  topicCount: number;
  covers: Book[];
}

export function CategoryTile({ name, count, topicCount, covers }: CategoryTileProps) {
  return (
    <ClickableCard label={name} href={browsePath({ category: name })} padding={4} className="category-tile">
      <VStack gap={2} className="category-tile-body">
        <div className="cover-fan" aria-hidden="true">
          {covers.map((book, index) => (
            <div key={book.id} className={`cover-fan-item cover-fan-item-${index}`}>
              <BookCover book={book} size="sm" />
            </div>
          ))}
        </div>
        <VStack gap={1} className="category-tile-text">
          <Heading level={3} maxLines={2} hasTruncateTooltip={false}>
            {name}
          </Heading>
          <Text type="supporting" hasTabularNumbers>
            {count} {count === 1 ? "book" : "books"} · {topicCount} {topicCount === 1 ? "topic" : "topics"}
          </Text>
        </VStack>
      </VStack>
    </ClickableCard>
  );
}
