import { Button } from "@astryxdesign/core/Button";
import { Grid } from "@astryxdesign/core/Grid";
import { Heading } from "@astryxdesign/core/Heading";
import { Icon } from "@astryxdesign/core/Icon";
import { Skeleton } from "@astryxdesign/core/Skeleton";
import { Text } from "@astryxdesign/core/Text";
import { Token } from "@astryxdesign/core/Token";
import { VStack } from "@astryxdesign/core/VStack";
import { Shuffle } from "lucide-react";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { CategoryTile } from "../components/CategoryTile";
import { LoadErrorState } from "../components/LoadingState";
import { PageFrame } from "../components/PageFrame";
import { PickCard } from "../components/PickCard";
import { RecentList } from "../components/RecentList";
import { Shelf } from "../components/Shelf";
import { firstBookPerCategory, greetingForHour, pickDailyBook, sampleCovers, topTopics } from "../lib/data";
import { useDocumentTitle, useIsPhone } from "../lib/hooks";
import { useLibrary } from "../lib/library";
import { bookPath, browsePath } from "../lib/routes";
import type { Book } from "../lib/types";

const PHONE_RECENT_LIMIT = 3;

export function HomePage() {
  useDocumentTitle("");
  const navigate = useNavigate();
  const isPhone = useIsPhone();
  const { status, books, categories, recentIds, findBook } = useLibrary();
  const daily = useMemo(() => pickDailyBook(books), [books]);
  const recent = useMemo(
    () =>
      recentIds
        .map(id => findBook(id))
        .filter((book): book is Book => Boolean(book))
        .slice(0, 4),
    [recentIds, findBook]
  );
  const starters = useMemo(() => firstBookPerCategory(books, categories, 4), [books, categories]);
  const topics = useMemo(() => topTopics(books, 12), [books]);
  const shelves = useMemo(
    () =>
      categories.map(category => {
        const categoryBooks = books.filter(book => book.category === category.name);
        return {
          category,
          books: categoryBooks.slice(0, 12),
          covers: sampleCovers(books, category.name, 3),
          topicCount: new Set(categoryBooks.map(book => book.topic)).size,
          topicLine: topTopics(categoryBooks, 4)
            .map(topic => topic.leaf)
            .join(" · ")
        };
      }),
    [books, categories]
  );

  if (status === "error") {
    return (
      <PageFrame>
        <LoadErrorState />
      </PageFrame>
    );
  }

  if (status === "loading" || !daily) {
    return (
      <PageFrame>
        <HomeSkeleton isPhone={isPhone} />
      </PageFrame>
    );
  }

  const surprise = () => {
    const book = books[Math.floor(Math.random() * books.length)];
    if (book) navigate(bookPath(book.id));
  };

  const greeting = (
    <VStack gap={2} className="home-greeting">
      <Heading level={1} type={isPhone ? undefined : "display-2"}>
        {greetingForHour(new Date().getHours())}
      </Heading>
      <Text type={isPhone ? "body" : "large"} color="secondary">
        {books.length} books on {categories.length} shelves. Pick one.
      </Text>
    </VStack>
  );

  const topicStrip = (
    <VStack gap={3} className="topic-strip">
      <Heading level={3}>Browse by topic</Heading>
      <nav className="chip-row" aria-label="Topics">
        {topics.map(topic => (
          <Token
            key={`${topic.category}::${topic.topic}`}
            label={topic.leaf}
            size={isPhone ? "sm" : "md"}
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
  );

  const shelfList = shelves.map(shelf => (
    <Shelf
      key={shelf.category.name}
      title={shelf.category.name}
      description={isPhone ? undefined : shelf.topicLine}
      count={shelf.category.count}
      books={shelf.books}
      href={browsePath({ category: shelf.category.name })}
      variant={isPhone ? "compact" : "default"}
    />
  ));

  const footer = (
    <VStack gap={3} hAlign="center" className="home-footer">
      <Text type="supporting">Don't know what to read?</Text>
      <Button
        label="Surprise me"
        variant="secondary"
        icon={<Icon icon={Shuffle} />}
        onClick={surprise}
        width={isPhone ? "100%" : undefined}
      />
    </VStack>
  );

  const recentTitle = recent.length ? "Jump back in" : "Start here";
  const recentBooks = recent.length ? recent : starters;

  if (isPhone) {
    return (
      <PageFrame>
        <VStack gap={8}>
          {greeting}
          <PickCard book={daily} />
          {topicStrip}
          <RecentList variant="plain" title={recentTitle} books={recentBooks.slice(0, PHONE_RECENT_LIMIT)} />
          {shelfList}
          {footer}
        </VStack>
      </PageFrame>
    );
  }

  return (
    <PageFrame>
      <VStack gap={10}>
        {greeting}

        <div className="home-hero">
          <PickCard book={daily} />
          <RecentList title={recentTitle} books={recentBooks} />
        </div>

        <VStack gap={4} className="category-tiles">
          <Heading level={2}>Your shelves</Heading>
          <Grid columns={{ minWidth: 200 }} gap={4}>
            {shelves.map(shelf => (
              <CategoryTile
                key={shelf.category.name}
                name={shelf.category.name}
                count={shelf.category.count}
                topicCount={shelf.topicCount}
                covers={shelf.covers}
              />
            ))}
          </Grid>
        </VStack>

        {topicStrip}

        {shelfList}

        {footer}
      </VStack>
    </PageFrame>
  );
}

function HomeSkeleton({ isPhone }: { isPhone: boolean }) {
  if (isPhone) {
    return (
      <VStack gap={8}>
        <VStack gap={3}>
          <Skeleton height={32} width={220} />
          <Skeleton height={18} width={260} index={1} />
        </VStack>
        <Skeleton height={176} width="100%" index={2} />
        <VStack gap={3}>
          <Skeleton height={24} width={160} index={3} />
          <Skeleton height={24} width="100%" index={4} />
        </VStack>
        <div className="shelf-skeleton">
          {Array.from({ length: 4 }, (_, index) => (
            <div key={index} className="shelf-item">
              <div className="book-cover">
                <Skeleton index={index + 5} radius={2} />
              </div>
            </div>
          ))}
        </div>
      </VStack>
    );
  }
  return (
    <VStack gap={10}>
      <VStack gap={3}>
        <Skeleton height={36} width={280} />
        <Skeleton height={18} width={320} index={1} />
      </VStack>
      <div className="home-hero">
        <div className="pick-card">
          <div className="pick-grid">
            <div className="pick-cover">
              <div className="book-cover">
                <Skeleton radius={2} />
              </div>
            </div>
            <VStack gap={3} className="pick-body">
              <Skeleton height={12} width={96} index={1} />
              <Skeleton height={32} width="85%" index={2} />
              <Skeleton height={40} width="95%" index={3} />
              <Skeleton height={36} width={220} index={4} />
            </VStack>
          </div>
        </div>
        <div className="recent-card-skeleton">
          <VStack gap={3}>
            <Skeleton height={24} width={160} />
            {Array.from({ length: 4 }, (_, index) => (
              <Skeleton key={index} height={56} width="100%" index={index + 1} />
            ))}
          </VStack>
        </div>
      </div>
      <Grid columns={{ minWidth: 200 }} gap={4}>
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} height={112} width="100%" index={index} />
        ))}
      </Grid>
      <VStack gap={3}>
        <Skeleton height={24} width={240} />
        <div className="shelf-skeleton">
          {Array.from({ length: 8 }, (_, index) => (
            <div key={index} className="shelf-item">
              <div className="book-cover">
                <Skeleton index={index} radius={2} />
              </div>
            </div>
          ))}
        </div>
      </VStack>
    </VStack>
  );
}
