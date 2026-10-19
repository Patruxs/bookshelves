import { HStack } from "@astryxdesign/core/HStack";
import { Icon } from "@astryxdesign/core/Icon";
import { IconButton } from "@astryxdesign/core/IconButton";
import { Link } from "@astryxdesign/core/Link";
import { StackItem } from "@astryxdesign/core/Stack";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { VStack } from "@astryxdesign/core/VStack";
import { Download } from "lucide-react";
import { useIsDesktop } from "../lib/hooks";
import { bookPath } from "../lib/routes";
import { formatLabel, topicLeaf } from "../lib/text";
import type { Book } from "../lib/types";
import { BookCover } from "./BookCover";
import { RouterLink } from "./RouterLink";

export function BookRow({ book }: { book: Book }) {
  const isDesktop = useIsDesktop();
  const primaryFormat = book.formats.find(format => book.downloads[format]) ?? book.formats[0];
  const primaryUrl = primaryFormat ? book.downloads[primaryFormat] : undefined;
  return (
    <HStack gap={4} vAlign="center" className="book-row">
      <RouterLink href={bookPath(book.id)} className="book-row-cover" aria-hidden="true" tabIndex={-1}>
        <BookCover book={book} size="sm" />
      </RouterLink>
      <StackItem size="fill">
        <VStack gap={0.5}>
          <Link href={bookPath(book.id)} color="primary" weight="bold" isStandalone maxLines={1}>
            {book.title}
          </Link>
          <Text type="supporting" maxLines={1} hasTruncateTooltip={false}>
            {topicLeaf(book.topic)}
          </Text>
        </VStack>
      </StackItem>
      {isDesktop ? (
        <HStack gap={1} vAlign="center" className="book-row-formats">
          {book.formats.map(format => (
            <Token key={format} label={formatLabel(format)} size="sm" />
          ))}
        </HStack>
      ) : null}
      {primaryFormat ? (
        <IconButton
          label={`Download ${formatLabel(primaryFormat)}`}
          tooltip={`Download ${formatLabel(primaryFormat)}`}
          icon={<Icon icon={Download} />}
          size={isDesktop ? "sm" : "md"}
          variant="ghost"
          href={primaryUrl || undefined}
          isDisabled={!primaryUrl}
          target="_blank"
          rel="noopener noreferrer"
        />
      ) : null}
    </HStack>
  );
}
