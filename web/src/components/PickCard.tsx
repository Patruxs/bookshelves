import { Button } from "@astryxdesign/core/Button";
import { ClickableCard } from "@astryxdesign/core/ClickableCard";
import { Heading } from "@astryxdesign/core/Heading";
import { HStack } from "@astryxdesign/core/HStack";
import { Icon } from "@astryxdesign/core/Icon";
import { Link } from "@astryxdesign/core/Link";
import { StackItem } from "@astryxdesign/core/Stack";
import { Text } from "@astryxdesign/core/Text";
import { VStack } from "@astryxdesign/core/VStack";
import { Download } from "lucide-react";
import { useIsPhone } from "../lib/hooks";
import { bookPath, browsePath } from "../lib/routes";
import { excerpt, formatLabel, topicLeaf } from "../lib/text";
import type { Book } from "../lib/types";
import { AmbientBackdrop } from "./AmbientBackdrop";
import { BookCover } from "./BookCover";

export function PickCard({ book }: { book: Book }) {
  const isPhone = useIsPhone();
  if (isPhone) return <CompactPickCard book={book} />;
  const primaryFormat = book.formats[0];
  const primaryUrl = book.downloads[primaryFormat] || "";
  return (
    <section className="pick-card ambient-host" aria-label="Today's pick">
      <AmbientBackdrop book={book} />
      <div className="pick-grid">
        <Link href={bookPath(book.id)} label={`Open ${book.title}`} className="pick-cover">
          <BookCover book={book} size="lg" priority />
        </Link>
        <VStack gap={3} className="pick-body">
          <span className="pick-eyebrow">
            <Text type="supporting">Today's pick</Text>
          </span>
          <HStack gap={2} vAlign="center" wrap="wrap" className="pick-path">
            <Link href={browsePath({ category: book.category })} color="secondary" isStandalone size="sm">
              {book.category}
            </Link>
            <Text type="supporting">/</Text>
            <Link href={browsePath({ category: book.category, topic: book.topic })} color="secondary" isStandalone size="sm">
              {topicLeaf(book.topic)}
            </Link>
          </HStack>
          <Heading level={2} type="display-3" textWrap="balance" maxLines={2}>
            {book.title}
          </Heading>
          {book.description ? (
            <Text type="body" color="secondary" maxLines={2} hasTruncateTooltip={false} as="p">
              {excerpt(book.description, 260)}
            </Text>
          ) : null}
          <HStack gap={2} wrap="wrap" className="pick-actions">
            <Button
              label={`Download ${formatLabel(primaryFormat)}`}
              variant="primary"
              icon={<Icon icon={Download} />}
              href={primaryUrl || undefined}
              isDisabled={!primaryUrl}
              target="_blank"
              rel="noopener noreferrer"
            />
            <Button label="Open" variant="secondary" href={bookPath(book.id)} />
          </HStack>
        </VStack>
      </div>
    </section>
  );
}

function CompactPickCard({ book }: { book: Book }) {
  return (
    <ClickableCard label={`Today's pick: ${book.title}`} href={bookPath(book.id)} padding={4} className="pick-card-compact ambient-host">
      <AmbientBackdrop book={book} />
      <HStack gap={4} vAlign="center">
        <div className="pick-compact-cover">
          <BookCover book={book} priority />
        </div>
        <StackItem size="fill">
          <VStack gap={1}>
            <span className="pick-eyebrow">
              <Text type="supporting">Today's pick</Text>
            </span>
            <Heading level={3} accessibilityLevel={2} maxLines={3} hasTruncateTooltip={false}>
              {book.title}
            </Heading>
            <Text type="supporting" maxLines={2} hasTruncateTooltip={false}>
              {book.category} · {topicLeaf(book.topic)}
            </Text>
          </VStack>
        </StackItem>
      </HStack>
    </ClickableCard>
  );
}
