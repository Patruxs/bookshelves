import { HStack } from "@astryxdesign/core/HStack";
import { StackItem } from "@astryxdesign/core/Stack";
import { Text } from "@astryxdesign/core/Text";
import { VStack } from "@astryxdesign/core/VStack";
import type { SearchItem } from "../lib/librarySearch";
import { BookCover } from "./BookCover";

export function SearchResultRow({ item }: { item: SearchItem }) {
  const data = item.auxiliaryData;
  return (
    <HStack gap={3} vAlign="center" className="palette-row">
      {data?.book ? <BookCover book={data.book} size="sm" /> : null}
      <StackItem size="fill">
        <VStack gap={0}>
          <Text type="label" maxLines={1} hasTruncateTooltip={false}>
            {item.label}
          </Text>
          {data?.detail ? (
            <Text type="supporting" maxLines={1} hasTruncateTooltip={false}>
              {data.detail}
            </Text>
          ) : null}
        </VStack>
      </StackItem>
    </HStack>
  );
}
