import { Card } from "@astryxdesign/core/Card";
import { Heading } from "@astryxdesign/core/Heading";
import { Link } from "@astryxdesign/core/Link";
import { Text } from "@astryxdesign/core/Text";
import { VStack } from "@astryxdesign/core/VStack";
import { bookPath } from "../lib/routes";
import { topicLeaf } from "../lib/text";
import type { Book } from "../lib/types";
import { BookCover } from "./BookCover";
import { RouterLink } from "./RouterLink";

interface RecentListProps {
  title: string;
  books: Book[];
  variant?: "card" | "plain";
}

export function RecentList({ title, books, variant = "card" }: RecentListProps) {
  if (variant === "plain") {
    return (
      <VStack gap={2}>
        <Heading level={2}>{title}</Heading>
        <ul className="plain-book-list">
          {books.map(book => (
            <li key={book.id}>
              <RouterLink href={bookPath(book.id)} className="plain-book-row">
                <BookCover book={book} size="sm" />
                <VStack gap={0.5} className="recent-text">
                  <Text type="label" maxLines={1} hasTruncateTooltip={false}>
                    {book.title}
                  </Text>
                  <Text type="supporting" maxLines={1} hasTruncateTooltip={false}>
                    {book.category} · {topicLeaf(book.topic)}
                  </Text>
                </VStack>
              </RouterLink>
            </li>
          ))}
        </ul>
      </VStack>
    );
  }

  return (
    <Card padding={5} height="100%" className="recent-card">
      <VStack gap={3}>
        <Heading level={2}>{title}</Heading>
        <ol className="recent-list">
          {books.map((book, index) => (
            <li key={book.id} className="recent-row">
              <span className="recent-index">
                <Text type="large" color="secondary" hasTabularNumbers>
                  {index + 1}
                </Text>
              </span>
              <BookCover book={book} size="sm" />
              <VStack gap={0.5} className="recent-text">
                <Link href={bookPath(book.id)} color="primary" maxLines={1}>
                  {book.title}
                </Link>
                <Text type="supporting" maxLines={1} hasTruncateTooltip={false}>
                  {book.category} · {topicLeaf(book.topic)}
                </Text>
              </VStack>
            </li>
          ))}
        </ol>
      </VStack>
    </Card>
  );
}
