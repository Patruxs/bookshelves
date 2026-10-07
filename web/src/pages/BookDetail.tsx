import { Badge } from "@astryxdesign/core/Badge";
import { Button } from "@astryxdesign/core/Button";
import { DropdownMenu } from "@astryxdesign/core/DropdownMenu";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { Heading } from "@astryxdesign/core/Heading";
import { HStack } from "@astryxdesign/core/HStack";
import { Icon } from "@astryxdesign/core/Icon";
import { IconButton } from "@astryxdesign/core/IconButton";
import { Link } from "@astryxdesign/core/Link";
import { Skeleton } from "@astryxdesign/core/Skeleton";
import { StackItem } from "@astryxdesign/core/Stack";
import { Text } from "@astryxdesign/core/Text";
import { useToast } from "@astryxdesign/core/Toast";
import { VStack } from "@astryxdesign/core/VStack";
import { ArrowLeft, Download, Eye, Share2 } from "lucide-react";
import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { AmbientBackdrop } from "../components/AmbientBackdrop";
import { BookCover } from "../components/BookCover";
import { LoadErrorState } from "../components/LoadingState";
import { PageFrame } from "../components/PageFrame";
import { RecentList } from "../components/RecentList";
import { Shelf } from "../components/Shelf";
import { sameCategoryBooks, sameTopicBooks } from "../lib/data";
import { useDocumentTitle, useIsDesktop } from "../lib/hooks";
import { useLibrary } from "../lib/library";
import { browsePath, viewerUrl } from "../lib/routes";
import { formatLabel, topicLeaf } from "../lib/text";
import type { Book } from "../lib/types";

export function BookDetailPage() {
  const { id = "" } = useParams();
  const { status, books, findBook, markViewed } = useLibrary();
  const book = findBook(decodeURIComponent(id));
  useDocumentTitle(book ? book.title : "Book");

  useEffect(() => {
    if (book) markViewed(book.id);
  }, [book, markViewed]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [id]);

  if (status === "error") {
    return (
      <PageFrame>
        <LoadErrorState />
      </PageFrame>
    );
  }

  if (status === "loading") {
    return (
      <PageFrame>
        <VStack gap={8} aria-hidden="true">
          <Skeleton height={28} width={160} />
          <section className="book-hero">
            <div className="book-hero-grid">
              <div className="book-hero-cover">
                <div className="book-cover">
                  <Skeleton radius={2} />
                </div>
              </div>
              <VStack gap={3} className="book-hero-body">
                <Skeleton height={12} width={120} index={1} />
                <Skeleton height={14} width={240} index={2} />
                <Skeleton height={48} width="80%" index={3} />
                <Skeleton height={14} width={100} index={4} />
                <Skeleton height={32} width={320} index={5} />
              </VStack>
            </div>
          </section>
          <div className="book-body">
            <VStack gap={4} className="book-body-main">
              <Skeleton height={24} width={120} index={6} />
              <Skeleton height={14} width="95%" index={7} />
              <Skeleton height={14} width="90%" index={8} />
              <Skeleton height={14} width="70%" index={9} />
            </VStack>
            <div className="book-body-side recent-card-skeleton">
              <VStack gap={3}>
                <Skeleton height={24} width={160} index={10} />
                <Skeleton height={56} index={11} />
                <Skeleton height={56} index={12} />
                <Skeleton height={56} index={13} />
              </VStack>
            </div>
          </div>
        </VStack>
      </PageFrame>
    );
  }

  if (!book) {
    return (
      <PageFrame>
        <EmptyState
          title="Book not found"
          description="This book may have been moved or renamed."
          actions={<Button label="Browse the library" variant="primary" href="/browse" />}
        />
      </PageFrame>
    );
  }

  return <BookDetail book={book} books={books} />;
}

interface BookDetailProps {
  book: Book;
  books: Book[];
}

function BookDetail({ book, books }: BookDetailProps) {
  const toast = useToast();
  const isDesktop = useIsDesktop();
  const sameTopic = useMemo(() => sameTopicBooks(book, books).slice(0, 5), [book, books]);
  const sameCategory = useMemo(() => sameCategoryBooks(book, books).slice(0, 5), [book, books]);
  const related = sameTopic.length
    ? { title: `More in ${topicLeaf(book.topic)}`, books: sameTopic, href: browsePath({ category: book.category, topic: book.topic }), label: `View all in ${topicLeaf(book.topic)}` }
    : sameCategory.length
      ? { title: `More in ${book.category}`, books: sameCategory, href: browsePath({ category: book.category }), label: `View all in ${book.category}` }
      : null;
  const topicHref = (path: string) => browsePath({ category: book.category, topic: path });
  const topicCrumbs = book.topicParts.map((part, index) => ({
    label: part,
    path: book.topicParts.slice(0, index + 1).join("/")
  }));

  const share = async () => {
    const url = window.location.href;
    try {
      if (navigator.share) {
        await navigator.share({ title: book.title, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      toast({ body: "Link copied to clipboard" });
    } catch {
      toast({ body: "Could not share this link", type: "error" });
    }
  };

  if (!isDesktop) {
    return (
      <PageFrame>
        <VStack gap={8} className="book-page-mobile">
          <section className="book-hero-mobile ambient-host" aria-label={book.title}>
            <AmbientBackdrop book={book} />
            <VStack gap={3} hAlign="center" className="book-hero-mobile-body">
              <div className="book-hero-mobile-cover">
                <BookCover book={book} size="lg" priority />
              </div>
              <Text type="supporting" textWrap="balance">
                {[{ label: book.category, href: browsePath({ category: book.category }) }, ...topicCrumbs.map(crumb => ({ label: crumb.label, href: topicHref(crumb.path) }))].map(
                  (crumb, index, crumbs) => (
                    <Fragment key={crumb.href}>
                      <span className="crumb-segment">
                        <Link href={crumb.href} color="secondary">
                          {crumb.label}
                        </Link>
                        {index < crumbs.length - 1 ? " /" : null}
                      </span>
                      {index < crumbs.length - 1 ? " " : null}
                    </Fragment>
                  )
                )}
              </Text>
              <Heading level={1} textWrap="balance">
                {book.title}
              </Heading>
              <HStack gap={1} hAlign="center" wrap="wrap">
                {book.formats.map(format => (
                  <Badge key={format} label={formatLabel(format)} />
                ))}
              </HStack>
            </VStack>
          </section>

          <VStack gap={4}>
            <Heading level={2}>About</Heading>
            {book.description ? (
              <ClampedDescription text={book.description} />
            ) : (
              <Text type="body" color="secondary">
                No description yet.
              </Text>
            )}
          </VStack>

          {related ? <Shelf title={related.title} books={related.books} href={related.href} linkLabel="View all" headingLevel={2} /> : null}
        </VStack>

        <div className="book-action-bar" role="group" aria-label="Book actions">
          <HStack gap={2} vAlign="center">
            <StackItem size="fill">
              <DownloadAction book={book} />
            </StackItem>
            {book.downloads.pdf ? (
              <IconButton
                label="Read online"
                tooltip="Read online in Google Docs Viewer"
                variant="secondary"
                icon={<Icon icon={Eye} />}
                href={viewerUrl(book.downloads.pdf)}
                target="_blank"
                rel="noopener noreferrer"
              />
            ) : null}
            <IconButton label="Share" tooltip="Share" variant="secondary" icon={<Icon icon={Share2} />} onClick={share} />
          </HStack>
        </div>
      </PageFrame>
    );
  }

  return (
    <PageFrame>
      <VStack gap={8}>
        <div>
          <Button
            label={`Back to ${topicLeaf(book.topic)}`}
            variant="ghost"
            size="sm"
            icon={<Icon icon={ArrowLeft} />}
            href={browsePath({ category: book.category, topic: book.topic })}
          />
        </div>

        <section className="book-hero ambient-host" aria-label={book.title}>
          <AmbientBackdrop book={book} />
          <div className="book-hero-grid">
            <div className="book-hero-cover">
              <BookCover book={book} size="lg" priority />
            </div>
            <VStack gap={3} className="book-hero-body">
              <span className="pick-eyebrow">
                <Text type="supporting">{book.category}</Text>
              </span>
              <HStack gap={2} vAlign="center" wrap="wrap" className="pick-path">
                {topicCrumbs.map((crumb, index) => (
                  <Fragment key={crumb.path}>
                    {index > 0 ? <Text type="supporting">/</Text> : null}
                    <Link href={topicHref(crumb.path)} color="secondary" isStandalone size="sm">
                      {crumb.label}
                    </Link>
                  </Fragment>
                ))}
              </HStack>
              <Heading level={1} type="display-2" textWrap="balance">
                {book.title}
              </Heading>
              <Text type="supporting">{book.formats.map(formatLabel).join(" · ")}</Text>
              <div className="book-actions">
                <DownloadAction book={book} />
                <ReadOnlineButton book={book} />
                <IconButton className="book-share" label="Share" tooltip="Share" variant="ghost" icon={<Icon icon={Share2} />} onClick={share} />
              </div>
            </VStack>
          </div>
        </section>

        <div className="book-body">
          <VStack gap={4} className="book-body-main">
            <Heading level={2}>About</Heading>
            {book.description ? (
              <Description text={book.description} />
            ) : (
              <Text type="body" color="secondary">
                No description yet.
              </Text>
            )}
          </VStack>
          <aside className="book-body-side">
            {related ? (
              <VStack gap={3}>
                <RecentList title={related.title} books={related.books} />
                <Link href={related.href} isStandalone size="sm">
                  {related.label}
                </Link>
              </VStack>
            ) : null}
          </aside>
        </div>
      </VStack>
    </PageFrame>
  );
}

function DownloadAction({ book }: { book: Book }) {
  if (book.formats.length === 1) {
    const format = book.formats[0];
    const url = book.downloads[format] || "";
    return (
      <Button
        className="book-action book-action-primary"
        label={`Download ${formatLabel(format)}`}
        variant="primary"
        icon={<Icon icon={Download} />}
        href={url || undefined}
        isDisabled={!url}
        target="_blank"
        rel="noopener noreferrer"
      />
    );
  }
  const items = book.formats.flatMap(format => {
    const url = book.downloads[format];
    if (!url) return [];
    return [{ id: format, label: formatLabel(format), onClick: () => window.open(url, "_blank", "noopener,noreferrer") }];
  });
  return (
    <DropdownMenu
      button={{ label: "Download", variant: "primary", icon: <Icon icon={Download} />, className: "book-action book-action-primary" }}
      presentation="adaptive"
      items={items}
    />
  );
}

function ReadOnlineButton({ book }: { book: Book }) {
  const pdfUrl = book.downloads.pdf;
  if (!pdfUrl) return null;
  return (
    <Button
      className="book-action"
      label="Read online"
      tooltip="Opens in Google Docs Viewer; large files may not load"
      variant="secondary"
      icon={<Icon icon={Eye} />}
      href={viewerUrl(pdfUrl)}
      target="_blank"
      rel="noopener noreferrer"
    />
  );
}

interface DescriptionBlock {
  kind: "paragraph" | "list";
  lines: string[];
}

function parseDescription(text: string): DescriptionBlock[] {
  const blocks: DescriptionBlock[] = [];
  for (const chunk of text.split(/\n{2,}/)) {
    const lines = chunk
      .split("\n")
      .map(line => line.trim())
      .filter(Boolean);
    if (!lines.length) continue;
    const bulletLines = lines.filter(line => /^[•\-*]\s*/.test(line));
    if (bulletLines.length === lines.length) {
      blocks.push({ kind: "list", lines: lines.map(line => line.replace(/^[•\-*]\s*/, "")) });
    } else {
      blocks.push({ kind: "paragraph", lines: [lines.join(" ")] });
    }
  }
  return blocks;
}

const DESCRIPTION_LINE_LIMIT = 8;

function ClampedDescription({ text }: { text: string }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isClamped, setIsClamped] = useState(false);
  const clampRef = useRef<HTMLElement>(null);
  const plainText = useMemo(
    () =>
      parseDescription(text)
        .map(block => (block.kind === "list" ? block.lines.map(line => `• ${line}`).join("\n") : block.lines[0]))
        .join("\n"),
    [text]
  );

  useLayoutEffect(() => {
    const element = clampRef.current;
    if (element) setIsClamped(element.scrollHeight > element.clientHeight + 1);
  }, [plainText]);

  if (isExpanded) return <Description text={text} />;

  return (
    <VStack gap={2} hAlign="start">
      <Text
        ref={clampRef}
        type="body"
        as="p"
        textWrap="pretty"
        maxLines={DESCRIPTION_LINE_LIMIT}
        hasTruncateTooltip={false}
        className="description-clamp"
      >
        {plainText}
      </Text>
      {isClamped ? <Button label="Read more" variant="ghost" onClick={() => setIsExpanded(true)} /> : null}
    </VStack>
  );
}

function Description({ text }: { text: string }) {
  const blocks = useMemo(() => parseDescription(text), [text]);
  return (
    <VStack gap={3} className="detail-description">
      {blocks.map((block, index) =>
        block.kind === "list" ? (
          <ul key={index} className="detail-list">
            {block.lines.map((line, lineIndex) => (
              <li key={lineIndex}>
                <Text type="body" textWrap="pretty">
                  {line}
                </Text>
              </li>
            ))}
          </ul>
        ) : (
          <Text key={index} type="body" as="p" textWrap="pretty">
            {block.lines[0]}
          </Text>
        )
      )}
    </VStack>
  );
}
