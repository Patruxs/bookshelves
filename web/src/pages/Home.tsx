import { Button } from "@astryxdesign/core/Button";
import { Heading } from "@astryxdesign/core/Heading";
import { Icon } from "@astryxdesign/core/Icon";
import { Link } from "@astryxdesign/core/Link";
import { Skeleton } from "@astryxdesign/core/Skeleton";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { VStack } from "@astryxdesign/core/VStack";
import { Download, Shuffle } from "lucide-react";
import { useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { AmbientBackdrop } from "../components/AmbientBackdrop";
import { BookCover } from "../components/BookCover";
import { GenreTile } from "../components/GenreTile";
import { LoadErrorState } from "../components/LoadingState";
import { PageFrame } from "../components/PageFrame";
import { Shelf } from "../components/Shelf";
import { pickDailyBook, sampleCovers, topTopics } from "../lib/data";
import { useDocumentTitle, useIsPhone } from "../lib/hooks";
import { useLibrary } from "../lib/library";
import { bookPath, browsePath } from "../lib/routes";
import { excerpt, formatLabel, topicLeaf } from "../lib/text";
import type { Book } from "../lib/types";

const SHELF_LIMIT = 12;
const TOPIC_LIMIT = 12;

export function HomePage() {
  useDocumentTitle("");
  const navigate = useNavigate();
  const isPhone = useIsPhone();
  const { status, books, categories } = useLibrary();
  const daily = useMemo(() => pickDailyBook(books), [books]);
  const topics = useMemo(() => topTopics(books, TOPIC_LIMIT), [books]);
  const shelves = useMemo(
    () =>
      categories.map(category => {
        const categoryBooks = books.filter(book => book.category === category.name);
        return {
          category,
          books: categoryBooks.slice(0, SHELF_LIMIT),
          covers: sampleCovers(books, category.name, 3),
          topicCount: new Set(categoryBooks.map(book => book.topic)).size
        };
      }),
    [books, categories]
  );

  const surprise = useCallback(() => {
    const book = books[Math.floor(Math.random() * books.length)];
    if (book) navigate(bookPath(book.id));
  }, [books, navigate]);

  if (status === "error") {
    return (
      <PageFrame>
        <LoadErrorState />
      </PageFrame>
    );
  }

  if (status === "loading" || !daily) {
    return <HomeSkeleton />;
  }

  return (
    <>
      <Hero book={daily} onSurprise={surprise} isPhone={isPhone} />
      <PageFrame width="default">
        <VStack gap={10}>
          <VStack gap={4}>
            <div className="section-head">
              <Heading level={2}>Shelves</Heading>
            </div>
            <div className="genre-grid" style={{ "--genre-count": Math.min(shelves.length, 6) } as React.CSSProperties}>
              {shelves.map((shelf, index) => (
                <GenreTile
                  key={shelf.category.name}
                  name={shelf.category.name}
                  count={shelf.category.count}
                  topicCount={shelf.topicCount}
                  covers={shelf.covers}
                  index={index}
                />
              ))}
            </div>
          </VStack>

          <VStack gap={3}>
            <div className="section-head">
              <Heading level={3} accessibilityLevel={2}>
                Browse by topic
              </Heading>
            </div>
            <nav className="chip-row" aria-label="Topics">
              {topics.map(topic => (
                <Token
                  key={`${topic.category}::${topic.topic}`}
                  label={topic.leaf}
                  size="md"
                  href={browsePath({ category: topic.category, topic: topic.topic })}
                  endContent={
                    <Text type="supporting" hasTabularNumbers>
                      {topic.count}
                    </Text>
                  }
                />
              ))}
              <Button label="All topics" variant="ghost" size="sm" href="/browse" />
            </nav>
          </VStack>

          {shelves.map(shelf => (
            <Shelf
              key={shelf.category.name}
              title={shelf.category.name}
              count={shelf.category.count}
              books={shelf.books}
              href={browsePath({ category: shelf.category.name })}
            />
          ))}

          <VStack gap={3} hAlign="center" className="home-footer">
            <Text type="supporting">Don't know what to read?</Text>
            <Button label="Surprise me" variant="secondary" icon={<Icon icon={Shuffle} />} onClick={surprise} width={isPhone ? "100%" : undefined} />
          </VStack>
        </VStack>
      </PageFrame>
    </>
  );
}

function Hero({ book, onSurprise, isPhone }: { book: Book; onSurprise: () => void; isPhone: boolean }) {
  const primaryFormat = book.formats[0];
  const primaryUrl = book.downloads[primaryFormat] || "";
  return (
    <section className="hero-bleed" aria-label="Today's pick">
      <AmbientBackdrop book={book} />
      <div className="hero-bleed-inner">
        <div className="hero-grid">
          <VStack gap={isPhone ? 3 : 4} className="hero-body">
            <span className="eyebrow">
              <span className="eyebrow-accent">Today's pick</span>
              <span aria-hidden="true">·</span>
              <Link href={browsePath({ category: book.category })} color="inherit">
                {book.category}
              </Link>
              <span aria-hidden="true">/</span>
              <Link href={browsePath({ category: book.category, topic: book.topic })} color="inherit">
                {topicLeaf(book.topic)}
              </Link>
            </span>
            <Heading level={1} type={isPhone ? "display-3" : "display-1"} textWrap="balance" maxLines={3} hasTruncateTooltip={false}>
              {book.title}
            </Heading>
            {book.description ? (
              <Text type={isPhone ? "body" : "large"} color="secondary" maxLines={3} hasTruncateTooltip={false} as="p">
                {excerpt(book.description, 320)}
              </Text>
            ) : null}
            <div className="hero-actions">
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
              <Button label="Surprise me" variant="ghost" icon={<Icon icon={Shuffle} />} onClick={onSurprise} />
            </div>
          </VStack>
          <Link href={bookPath(book.id)} label={`Open ${book.title}`} className="cover-tilt">
            <BookCover book={book} priority />
          </Link>
        </div>
      </div>
    </section>
  );
}

function HomeSkeleton() {
  return (
    <>
      <section className="hero-bleed" aria-hidden="true">
        <div className="hero-bleed-inner">
          <div className="hero-grid">
            <VStack gap={4} className="hero-body">
              <Skeleton height={12} width={200} />
              <Skeleton height={56} width="90%" index={1} />
              <Skeleton height={20} width="80%" index={2} />
              <Skeleton height={40} width={320} index={3} />
            </VStack>
            <div className="cover-tilt">
              <div className="book-cover">
                <Skeleton radius={2} />
              </div>
            </div>
          </div>
        </div>
      </section>
      <PageFrame>
        <VStack gap={10} aria-hidden="true">
          <VStack gap={4}>
            <Skeleton height={28} width={120} />
            <div className="genre-grid">
              {Array.from({ length: 5 }, (_, index) => (
                <Skeleton key={index} height={110} width="100%" index={index} />
              ))}
            </div>
          </VStack>
        </VStack>
      </PageFrame>
    </>
  );
}
