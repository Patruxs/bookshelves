import { HStack } from "@astryxdesign/core/HStack";
import { Icon } from "@astryxdesign/core/Icon";
import { StackItem } from "@astryxdesign/core/Stack";
import { Text } from "@astryxdesign/core/Text";
import { VStack } from "@astryxdesign/core/VStack";
import { ArrowRight, Library, Tag } from "lucide-react";
import type { ReactNode } from "react";
import type { SearchItem } from "../lib/librarySearch";
import { normalizeForSearch } from "../lib/text";
import { BookCover } from "./BookCover";

function highlight(text: string, tokens: string[] | undefined): ReactNode {
  if (!tokens?.length) return text;
  const parts = text.split(/(\s+)/);
  return parts.map((part, index) => {
    if (!part.trim()) return part;
    const normalized = normalizeForSearch(part).replace(/^[^a-z0-9]+/, "");
    const hit = tokens.some(token => normalized.startsWith(token) || (token.length >= 3 && normalized.includes(token)));
    return hit ? <mark key={index}>{part}</mark> : part;
  });
}

export function SearchResultRow({ item }: { item: SearchItem }) {
  const data = item.auxiliaryData;
  if (data?.kind === "more") {
    return (
      <HStack gap={3} vAlign="center" className="palette-row palette-row-more">
        <span className="palette-icon">
          <Icon icon={ArrowRight} />
        </span>
        <Text type="label">{item.label}</Text>
      </HStack>
    );
  }
  const leading =
    data?.book ? (
      <BookCover book={data.book} size="sm" />
    ) : (
      <span className="palette-icon">
        <Icon icon={data?.kind === "topic" ? Tag : Library} />
      </span>
    );
  const detail = data?.field === "description" && data.snippet ? data.snippet : data?.detail;
  return (
    <HStack gap={3} vAlign="center" className="palette-row">
      {leading}
      <StackItem size="fill">
        <VStack gap={0}>
          <Text type="label" maxLines={1} hasTruncateTooltip={false}>
            {highlight(item.label, data?.tokens)}
          </Text>
          {detail ? (
            <Text type="supporting" maxLines={data?.field === "description" ? 2 : 1} hasTruncateTooltip={false}>
              {data?.field === "description" ? highlight(detail, data.tokens) : detail}
            </Text>
          ) : null}
        </VStack>
      </StackItem>
    </HStack>
  );
}
