import { Button } from "@astryxdesign/core/Button";
import { Card } from "@astryxdesign/core/Card";
import { DropdownMenu } from "@astryxdesign/core/DropdownMenu";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { Heading } from "@astryxdesign/core/Heading";
import { HStack } from "@astryxdesign/core/HStack";
import { Icon } from "@astryxdesign/core/Icon";
import { IconButton } from "@astryxdesign/core/IconButton";
import { Link } from "@astryxdesign/core/Link";
import { MetadataList, MetadataListItem } from "@astryxdesign/core/MetadataList";
import { Skeleton } from "@astryxdesign/core/Skeleton";
import { StackItem } from "@astryxdesign/core/Stack";
import { Text } from "@astryxdesign/core/Text";
import { useToast } from "@astryxdesign/core/Toast";
import { Token } from "@astryxdesign/core/Token";
import { VStack } from "@astryxdesign/core/VStack";
import { ArrowLeft, Download, Eye, Share2 } from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { AmbientBackdrop } from "../components/AmbientBackdrop";
import { BookCover } from "../components/BookCover";
import { LoadErrorState } from "../components/LoadingState";
import { PageFrame } from "../components/PageFrame";
import { RankList } from "../components/RankList";
import { sameCategoryBooks, sameTopicBooks } from "../lib/data";
import { useDocumentTitle, useIsDesktop } from "../lib/hooks";
import { useLibrary } from "../lib/library";
import { browsePath, viewerUrl } from "../lib/routes";
import { formatLabel, topicLeaf } from "../lib/text";
import type { Book } from "../lib/types";
import "./book.css";
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
      <div aria-hidden="true">
        <section className="hero-bleed book-detail-hero">
          <div className="hero-bleed-inner">
            <div className="hero-grid">
              <VStack gap={3} className="hero-body book-detail-text">
                <Skeleton height={28} width={160} />
                <Skeleton height={12} width={120} index={1} />
                <Skeleton height={24} width={240} index={2} />
                <Skeleton height={56} width="85%" index={3} />
                <Skeleton height={14} width={100} index={4} />
                <Skeleton height={40} width={320} index={5} />
              </VStack>
              <div className="book-detail-cover">
                <div className="book-cover">
                  <Skeleton radius={2} />
                </div>
              </div>
            </div>
          </div>
        </section>
        <PageFrame>
          <div className="book-detail-body">
            <VStack gap={4}>
              <Skeleton height={28} width={120} index={6} />
              <Skeleton height={14} width="95%" index={7} />
              <Skeleton height={14} width="90%" index={8} />
              <Skeleton height={14} width="70%" index={9} />
            </VStack>
            <VStack gap={3}>
              <Skeleton height={180} index={10} />
              <Skeleton height={56} index={11} />
              <Skeleton height={56} index={12} />
            </VStack>
          </div>
        </PageFrame>
      </div>
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
    ? { title: `More in ${topicLeaf(book.topic)}`, books: sameTopic, href: browsePath({ category: book.category, topic: book.topic }) }
    : sameCategory.length
      ? { title: `More in ${book.category}`, books: sameCategory, href: browsePath({ category: book.category }) }
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

  const hero = (
    <section className="hero-bleed book-detail-hero" aria-label={book.title}>
      <AmbientBackdrop book={book} />
      <div className="hero-bleed-inner">
        <div className="hero-grid">
          <VStack gap={3} hAlign={isDesktop ? "start" : "center"} className="hero-body book-detail-text">
            {isDesktop ? (
              <Button
                label={`Back to ${topicLeaf(book.topic)}`}
                variant="ghost"
                size="sm"
                icon={<Icon icon={ArrowLeft} />}
                href={browsePath({ category: book.category, topic: book.topic })}
                className="book-back"
              />
            ) : null}
            <Link href={browsePath({ category: book.category })} color="inherit" className="eyebrow">
              {book.category}
            </Link>
            <HStack gap={1.5} vAlign="center" hAlign={isDesktop ? "start" : "center"} wrap="wrap" aria-label="Topic path">
              {topicCrumbs.map(crumb => (
                <Token key={crumb.path} label={crumb.label} size="sm" href={topicHref(crumb.path)} />
              ))}
            </HStack>
            <Heading level={1} type="display-1" textWrap="balance" className="book-title">
              {book.title}
            </Heading>
            <Text type="supporting">{book.formats.map(formatLabel).join(" · ")}</Text>
            {isDesktop ? (
              <div className="hero-actions">
                <DownloadAction book={book} />
                <ReadOnlineButton book={book} />
                <Button label="Share" variant="ghost" icon={<Icon icon={Share2} />} onClick={share} />
              </div>
            ) : null}
          </VStack>
          <div className="cover-tilt book-detail-cover">
            <BookCover book={book} size="lg" priority />
          </div>
        </div>
      </div>
    </section>
  );

  const details = (
    <Card className="book-details">
      <VStack gap={3}>
        <Heading level={2}>Details</Heading>
        <MetadataList>
          <MetadataListItem label="Category">
            <Link href={browsePath({ category: book.category })} color="primary">
              {book.category}
            </Link>
          </MetadataListItem>
          <MetadataListItem label="Topic">
            <Link href={topicHref(book.topic)} color="primary">
              {book.topicParts.join(" / ")}
            </Link>
          </MetadataListItem>
          <MetadataListItem label="Formats">{book.formats.map(formatLabel).join(", ")}</MetadataListItem>
          <MetadataListItem label="File name">
            <span className="book-file-name">{book.rawTitle}</span>
          </MetadataListItem>
        </MetadataList>
      </VStack>
    </Card>
  );

  const relatedList = related ? (
    <VStack gap={3}>
      <div className="section-head">
        <Heading level={2}>{related.title}</Heading>
        <span className="section-head-fill" />
        <Link href={related.href} isStandalone size="sm">
          See all
        </Link>
      </div>
      <RankList books={related.books} variant="vertical" label={related.title} />
    </VStack>
  ) : null;

  if (!isDesktop) {
    return (
      <>
        {hero}
        <PageFrame>
          <VStack gap={8} className="book-detail-mobile">
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
            {details}
            {relatedList}
          </VStack>
        </PageFrame>

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
      </>
    );
  }

  return (
    <>
      {hero}
      <PageFrame>
        <div className="book-detail-body">
          <VStack gap={4} className="book-detail-main">
            <Heading level={2}>About</Heading>
            {book.description ? (
              <Description text={book.description} />
            ) : (
              <Text type="body" color="secondary">
                No description yet.
              </Text>
            )}
          </VStack>
          <aside className="book-detail-side">
            <VStack gap={8}>
              {details}
              {relatedList}
            </VStack>
          </aside>
        </div>
      </PageFrame>
    </>
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
