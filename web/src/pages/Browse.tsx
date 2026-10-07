import { BottomSheet } from "@astryxdesign/core/BottomSheet";
import { BreadcrumbItem, Breadcrumbs } from "@astryxdesign/core/Breadcrumbs";
import { Button } from "@astryxdesign/core/Button";
import { Divider } from "@astryxdesign/core/Divider";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { Grid } from "@astryxdesign/core/Grid";
import { Heading } from "@astryxdesign/core/Heading";
import { HStack } from "@astryxdesign/core/HStack";
import { Icon } from "@astryxdesign/core/Icon";
import { IconButton } from "@astryxdesign/core/IconButton";
import { List, ListItem } from "@astryxdesign/core/List";
import { Pagination } from "@astryxdesign/core/Pagination";
import { Popover } from "@astryxdesign/core/Popover";
import { ScrollableArea } from "@astryxdesign/core/ScrollableArea";
import { SegmentedControl, SegmentedControlItem } from "@astryxdesign/core/SegmentedControl";
import { StackItem } from "@astryxdesign/core/Stack";
import { Text } from "@astryxdesign/core/Text";
import { TextInput } from "@astryxdesign/core/TextInput";
import { Token } from "@astryxdesign/core/Token";
import { VStack } from "@astryxdesign/core/VStack";
import {
  ArrowLeft,
  ArrowUpDown,
  Check,
  ChevronRight,
  FileText,
  LayoutGrid,
  Library,
  List as ListIcon,
  type LucideIcon,
  Search,
  SlidersHorizontal,
  Tag
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BookCard } from "../components/BookCard";
import { BookRow } from "../components/BookRow";
import { CoverSkeletonGrid, LoadErrorState } from "../components/LoadingState";
import { PageFrame } from "../components/PageFrame";
import { topicMatches } from "../lib/data";
import { scrollToTop, useDocumentTitle, useGridColumns, useIsDesktop, useIsPhone } from "../lib/hooks";
import { useLibrary } from "../lib/library";
import { browsePath } from "../lib/routes";
import { searchBooks } from "../lib/search";
import { STORAGE_KEYS, useStoredState } from "../lib/storage";
import { formatLabel, normalizeForSearch, topicLeaf, topicParts } from "../lib/text";
import type { Book, BookFormat, TopicNode } from "../lib/types";

const PAGE_SIZE = 24;
const GRID_ROWS_PER_PAGE = 4;
const ALL_FORMATS = "all";
const CONTROL_SIZE = "md";
const DEFAULT_SORT: SortKey = "title-asc";

type SortKey = "title-asc" | "title-desc" | "category";
type ViewMode = "grid" | "list";
type FacetKey = "shelf" | "topic" | "format" | "sort";
type SheetLevel = "root" | "shelf" | "topic";

const FACETS: { key: FacetKey; label: string; icon: LucideIcon }[] = [
  { key: "shelf", label: "Shelf", icon: Library },
  { key: "topic", label: "Topic", icon: Tag },
  { key: "format", label: "Format", icon: FileText },
  { key: "sort", label: "Sort", icon: ArrowUpDown }
];

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "title-asc", label: "Title A–Z" },
  { value: "title-desc", label: "Title Z–A" },
  { value: "category", label: "By category" }
];

function isFormat(value: string): value is BookFormat {
  return value === "pdf" || value === "epub" || value === "docx";
}

function parseFormat(value: string | null): BookFormat | null {
  return (value || "").split(",").find(isFormat) ?? null;
}

function byTitle(a: Book, b: Book): number {
  return a.title.localeCompare(b.title);
}

interface TopicChip {
  path: string;
  label: string;
  count: number;
}

function topicChipsOf(nodes: TopicNode[], parentName = ""): TopicChip[] {
  return nodes.flatMap(node => [
    { path: node.path, label: parentName ? `${parentName} / ${node.name}` : node.name, count: node.count },
    ...topicChipsOf(node.children, node.name)
  ]);
}

interface FacetRow {
  key: string;
  label: string;
  count: number;
  isSelected: boolean;
  select: () => void;
}

interface FacetGroup {
  key: string;
  header?: string;
  rows: FacetRow[];
}

function FacetList({ label, placeholder, groups, header }: { label: string; placeholder: string; groups: FacetGroup[]; header?: ReactNode }) {
  const [search, setSearch] = useState("");
  const needle = normalizeForSearch(search.trim());
  const visibleGroups = needle
    ? groups
        .map(group => ({ ...group, rows: group.rows.filter(row => normalizeForSearch(`${group.header ?? ""} ${row.label}`).includes(needle)) }))
        .filter(group => group.rows.length)
    : groups;

  return (
    <div className="facet-list">
      {header}
      <TextInput
        label={`Search ${label.toLowerCase()}`}
        isLabelHidden
        startIcon={Search}
        placeholder={placeholder}
        value={search}
        onChange={setSearch}
        hasClear
        width="100%"
      />
      <div className="facet-list-scroll">
        <ScrollableArea label={label} height="100%" overscroll="contain">
          {visibleGroups.length ? (
            visibleGroups.map(group => (
              <List
                key={group.key}
                header={
                  group.header ? (
                    <span className="facet-group-header">
                      <Text type="supporting">{group.header}</Text>
                    </span>
                  ) : undefined
                }
              >
                {group.rows.map(row => (
                  <ListItem
                    key={row.key}
                    label={row.label}
                    isSelected={row.isSelected}
                    onClick={row.select}
                    endContent={
                      <span className="facet-row-end">
                        <Text type="supporting" hasTabularNumbers>
                          {row.count}
                        </Text>
                        <span className="facet-row-check">{row.isSelected ? <Icon icon={Check} size="sm" /> : null}</span>
                      </span>
                    }
                  />
                ))}
              </List>
            ))
          ) : (
            <div className="facet-list-empty">
              <Text type="supporting">No matches</Text>
            </div>
          )}
        </ScrollableArea>
      </div>
    </div>
  );
}

export function BrowsePage() {
  const { status, books, categories } = useLibrary();
  const [params, setParams] = useSearchParams();
  const isDesktop = useIsDesktop();
  const isPhone = useIsPhone();
  const [view, setView] = useStoredState<ViewMode>(STORAGE_KEYS.view, "grid");
  const [gridRef, gridColumns] = useGridColumns();

  const categoryName = params.get("category") || "";
  const topic = params.get("topic") || "";
  const query = params.get("q") || "";
  const sort = (params.get("sort") as SortKey) || DEFAULT_SORT;
  const format = parseFormat(params.get("format"));
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [draftQuery, setDraftQuery] = useState(query);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [activeFacet, setActiveFacet] = useState<FacetKey>("shelf");
  const [sheetLevel, setSheetLevel] = useState<SheetLevel>("root");

  useEffect(() => {
    setDraftQuery(query);
  }, [query]);

  useDocumentTitle(categoryName ? `${categoryName}${topic ? ` / ${topic}` : ""}` : "Browse");

  const updateParams = useCallback(
    (changes: Record<string, string | null>, resetPage = true) => {
      const next = new URLSearchParams(params);
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      if (resetPage) next.delete("page");
      setParams(next, { replace: false });
    },
    [params, setParams]
  );

  useEffect(() => {
    const handle = window.setTimeout(() => {
      if (draftQuery !== query) updateParams({ q: draftQuery || null });
    }, 250);
    return () => window.clearTimeout(handle);
  }, [draftQuery, query, updateParams]);

  const categoryHref = useCallback(
    (name: string | null) => {
      const next = new URLSearchParams(params);
      if (name) next.set("category", name);
      else next.delete("category");
      next.delete("topic");
      next.delete("page");
      const search = next.toString();
      return search ? `/browse?${search}` : "/browse";
    },
    [params]
  );

  const scopeHref = useCallback(
    (topicPath: string | null) => {
      const href = topicPath === null ? browsePath() : browsePath({ category: categoryName, topic: topicPath || undefined });
      if (!format) return href;
      return `${href}${href.includes("?") ? "&" : "?"}format=${format}`;
    },
    [categoryName, format]
  );


  const category = useMemo(() => categories.find(entry => entry.name === categoryName) || null, [categories, categoryName]);
  const nodeName = topic ? topicLeaf(topic) : categoryName;
  const availableFormats = useMemo<BookFormat[]>(() => {
    const present = new Set<BookFormat>();
    for (const book of books) book.formats.forEach(entry => present.add(entry));
    return (["pdf", "epub", "docx"] as BookFormat[]).filter(entry => present.has(entry));
  }, [books]);

  const filtered = useMemo(() => {
    let list: Book[] = books;
    if (categoryName) list = list.filter(book => book.category === categoryName);
    if (topic) list = list.filter(book => topicMatches(book, topic));
    if (format) list = list.filter(book => book.formats.includes(format));
    if (query.trim()) return searchBooks(list, query);
    const sorted = [...list];
    if (sort === "title-desc") sorted.sort((a, b) => b.title.localeCompare(a.title));
    else if (sort === "category") sorted.sort((a, b) => a.category.localeCompare(b.category) || a.topic.localeCompare(b.topic) || byTitle(a, b));
    else sorted.sort(byTitle);
    return sorted;
  }, [books, categoryName, topic, format, query, sort]);

  const topicChips = useMemo(() => (category ? topicChipsOf(category.topics) : []), [category]);
  const libraryTopics = useMemo(
    () => categories.map(entry => ({ name: entry.name, chips: topicChipsOf(entry.topics) })).filter(entry => entry.chips.length),
    [categories]
  );

  const pageSize = isDesktop && view === "grid" && gridColumns ? gridColumns * GRID_ROWS_PER_PAGE : PAGE_SIZE;
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const pageItems = isDesktop
    ? filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)
    : filtered.slice(0, currentPage * pageSize);
  const scrollResetPage = isDesktop ? currentPage : 0;

  useEffect(() => {
    scrollToTop();
  }, [scrollResetPage, categoryName, topic]);

  useEffect(() => {
    if (isDesktop) return;
    for (const row of document.querySelectorAll<HTMLElement>(".browse-chrome .chip-row")) {
      const selectedChip = row.querySelector<HTMLElement>('[data-color="blue"]');
      if (!selectedChip) continue;
      const rowRect = row.getBoundingClientRect();
      const chipRect = selectedChip.getBoundingClientRect();
      row.scrollLeft += chipRect.left - rowRect.left - (rowRect.width - chipRect.width) / 2;
    }
  }, [categoryName, topic, categories, isDesktop]);

  const hasActiveFilters = Boolean(format || query.trim());
  const resetFilters = () => updateParams({ q: null, format: null });
  const resetAllFilters = () => updateParams({ q: null, format: null, sort: null, category: null, topic: null });
  const filterCount = [categoryName, topic, format, sort !== DEFAULT_SORT].filter(Boolean).length;
  const changeFiltersOpen = (isOpen: boolean) => {
    setFiltersOpen(isOpen);
    if (isOpen) setActiveFacet(categoryName ? "topic" : "shelf");
    else setSheetLevel("root");
  };

  if (status === "error") {
    return (
      <PageFrame width="wide">
        <LoadErrorState />
      </PageFrame>
    );
  }

  const filterInput = (
    <TextInput
      label="Filter results"
      isLabelHidden
      size="md"
      startIcon={Search}
      placeholder="Filter titles…"
      value={draftQuery}
      onChange={setDraftQuery}
      hasClear
      width="100%"
    />
  );

  const activeFilters = [
    categoryName ? { key: "category", label: `Shelf: ${categoryName}`, remove: () => updateParams({ category: null, topic: null }) } : null,
    topic ? { key: "topic", label: `Topic: ${topicParts(topic).join(" / ")}`, remove: () => updateParams({ topic: null }) } : null,
    format ? { key: "format", label: formatLabel(format), remove: () => updateParams({ format: null }) } : null,
    sort !== DEFAULT_SORT
      ? { key: "sort", label: SORT_OPTIONS.find(option => option.value === sort)?.label ?? sort, remove: () => updateParams({ sort: null }) }
      : null,
    query.trim() ? { key: "q", label: `“${query.trim()}”`, remove: () => updateParams({ q: null }) } : null
  ].filter(entry => entry !== null);

  const activeFilterRow = activeFilters.length ? (
    <HStack gap={2} vAlign="center" wrap="wrap" role="group" aria-label="Active filters">
      {activeFilters.map(entry => (
        <Token key={entry.key} label={entry.label} onRemove={entry.remove} />
      ))}
      <Button label="Clear all" variant="ghost" size="sm" onClick={resetAllFilters} />
    </HStack>
  ) : null;

  const filterTrigger = (
    <Button
      label={filterCount ? `Filters · ${filterCount}` : "Filters"}
      variant="secondary"
      size={CONTROL_SIZE}
      icon={<Icon icon={SlidersHorizontal} />}
      aria-haspopup="dialog"
      className={filterCount ? "filter-trigger-active" : undefined}
      onClick={isDesktop ? undefined : () => changeFiltersOpen(true)}
    />
  );

  const pickFilter = (changes: Record<string, string | null>) => {
    updateParams(changes);
    setSheetLevel("root");
  };

  const shelfGroups: FacetGroup[] = [
    {
      key: "shelves",
      rows: [
        { key: "", label: "All shelves", count: books.length, isSelected: !categoryName, select: () => pickFilter({ category: null, topic: null }) },
        ...categories.map(entry => ({
          key: entry.name,
          label: entry.name,
          count: entry.count,
          isSelected: entry.name === categoryName,
          select: () => pickFilter({ category: entry.name, topic: null })
        }))
      ]
    }
  ];

  const topicGroups: FacetGroup[] = category
    ? [
        {
          key: category.name,
          rows: [
            { key: "", label: "All topics", count: category.count, isSelected: !topic, select: () => pickFilter({ topic: null }) },
            ...topicChips.map(chip => ({
              key: chip.path,
              label: chip.label,
              count: chip.count,
              isSelected: chip.path === topic,
              select: () => pickFilter({ topic: chip.path })
            }))
          ]
        }
      ]
    : [
        {
          key: "all",
          rows: [{ key: "", label: "All topics", count: books.length, isSelected: true, select: () => pickFilter({ topic: null }) }]
        },
        ...libraryTopics.map(entry => ({
          key: entry.name,
          header: entry.name,
          rows: entry.chips.map(chip => ({
            key: chip.path,
            label: chip.label,
            count: chip.count,
            isSelected: false,
            select: () => pickFilter({ category: entry.name, topic: chip.path })
          }))
        }))
      ];

  const shelfFacetProps = { label: "Shelves", placeholder: "Search shelves…", groups: shelfGroups };
  const topicFacetProps = { label: "Topics", placeholder: "Search topics…", groups: topicGroups };
  const topicTotal = category ? topicChips.length : libraryTopics.reduce((sum, entry) => sum + entry.chips.length, 0);
  const facetCountLabel: Record<"shelf" | "topic", string> = {
    shelf: `${categories.length} ${categories.length === 1 ? "shelf" : "shelves"}`,
    topic: `${topicTotal} ${topicTotal === 1 ? "topic" : "topics"}`
  };

  const sortLabel = SORT_OPTIONS.find(option => option.value === sort)?.label ?? sort;
  const facetSummary: Record<FacetKey, string> = {
    shelf: categoryName || "All",
    topic: topic ? topicParts(topic).join(" / ") : "All",
    format: format ? formatLabel(format) : "All",
    sort: sortLabel
  };
  const facetIsSet: Record<FacetKey, boolean> = {
    shelf: Boolean(categoryName),
    topic: Boolean(topic),
    format: Boolean(format),
    sort: sort !== DEFAULT_SORT
  };
  const facetValue = (key: FacetKey) => <span className={facetIsSet[key] ? "facet-value-active" : undefined}>{facetSummary[key]}</span>;
  const facetHeader = (key: "shelf" | "topic", title: string) => (
    <HStack gap={2} vAlign="center">
      <Text type="label">{title}</Text>
      <StackItem size="fill">
        <span />
      </StackItem>
      <Text type="supporting" hasTabularNumbers>
        {facetCountLabel[key]}
      </Text>
    </HStack>
  );

  const formatSection = (
    <VStack gap={2}>
      <Text type="label">Format</Text>
      <SegmentedControl
        label="Format"
        layout="fill"
        value={format ?? ALL_FORMATS}
        onChange={value => updateParams({ format: isFormat(value) ? value : null })}
      >
        <SegmentedControlItem value={ALL_FORMATS} label="All" />
        {availableFormats.map(entry => (
          <SegmentedControlItem key={entry} value={entry} label={formatLabel(entry)} />
        ))}
      </SegmentedControl>
    </VStack>
  );

  const sortSection = (
    <VStack gap={2}>
      <Text type="label">Sort</Text>
      <SegmentedControl
        label="Sort"
        layout="fill"
        value={sort}
        onChange={value => updateParams({ sort: value === DEFAULT_SORT ? null : value })}
        isDisabled={Boolean(query.trim())}
        disabledMessage="Results are ranked by relevance while a search is active"
      >
        {SORT_OPTIONS.map(option => (
          <SegmentedControlItem key={option.value} value={option.value} label={option.label} />
        ))}
      </SegmentedControl>
    </VStack>
  );

  const facetContent: Record<FacetKey, ReactNode> = {
    shelf: <FacetList {...shelfFacetProps} header={facetHeader("shelf", "Shelf")} />,
    topic: <FacetList {...topicFacetProps} header={facetHeader("topic", "Topic")} />,
    format: formatSection,
    sort: sortSection
  };

  const filterFooter = (
    <HStack gap={2} vAlign="center" className="filter-panel-footer">
      <Button label="Clear all" variant="ghost" size="sm" onClick={resetAllFilters} />
      <StackItem size="fill">
        <span />
      </StackItem>
      <Button label={`Show ${filtered.length} ${filtered.length === 1 ? "book" : "books"}`} variant="primary" onClick={() => changeFiltersOpen(false)} />
    </HStack>
  );

  const results =
    status === "loading" ? (
      <CoverSkeletonGrid />
    ) : filtered.length === 0 ? (
      <EmptyState
        title="No books match"
        description={hasActiveFilters ? "Try a different search or format." : "This shelf has no books yet."}
        actions={hasActiveFilters ? <Button label="Reset filters" variant="secondary" onClick={resetFilters} /> : undefined}
      />
    ) : view === "grid" ? (
      <Grid
        ref={gridRef}
        columns={{ minWidth: isDesktop ? 160 : isPhone ? 104 : 132 }}
        gap={isPhone ? 3 : 5}
        rowGap={isPhone ? 5 : 8}
        className="book-grid"
      >
        {pageItems.map(book => (
          <BookCard key={book.id} book={book} showCategory={!categoryName} />
        ))}
      </Grid>
    ) : (
      <VStack gap={0} className="book-list">
        {pageItems.map(book => (
          <BookRow key={book.id} book={book} />
        ))}
      </VStack>
    );

  const countLabel = status === "ready" ? `${filtered.length} ${filtered.length === 1 ? "book" : "books"}` : "";

  if (!isDesktop) {
    return (
      <PageFrame width="wide">
        <VStack gap={4} className="browse-main">
          <div className="browse-chrome">
            <nav className="chip-row" aria-label="Categories">
              <Token
                label="All"
                size="sm"
                href={categoryHref(null)}
                color={categoryName ? "default" : "blue"}
                endContent={books.length || undefined}
              />
              {categories.map(entry => (
                <Token
                  key={entry.name}
                  label={entry.name}
                  size="sm"
                  href={categoryHref(entry.name)}
                  color={entry.name === categoryName ? "blue" : "default"}
                  endContent={entry.count}
                />
              ))}
            </nav>
            {category && topicChips.length ? (
              <nav className="chip-row" aria-label={`Topics in ${category.name}`}>
                <Token label="All" size="sm" href={scopeHref("")} color={topic ? "default" : "blue"} endContent={category.count} />
                {topicChips.map(chip => (
                  <Token
                    key={chip.path}
                    label={chip.label}
                    size="sm"
                    href={scopeHref(chip.path)}
                    color={chip.path === topic ? "blue" : "default"}
                    endContent={chip.count}
                  />
                ))}
              </nav>
            ) : null}
            <HStack gap={2} vAlign="center" role="search">
              <StackItem size="fill">{filterInput}</StackItem>
              {filterTrigger}
            </HStack>
          </div>

          {activeFilterRow}

          <HStack gap={3} vAlign="center" wrap="wrap">
            <Heading level={2} accessibilityLevel={1}>
              {nodeName || "All books"}
            </Heading>
            <Text type="supporting" hasTabularNumbers>
              {countLabel}
            </Text>
          </HStack>

          {results}

          {pageItems.length < filtered.length ? (
            <VStack gap={2} hAlign="center" className="load-more">
              <Button label="Load more" variant="secondary" onClick={() => updateParams({ page: String(currentPage + 1) }, false)} />
              <Text type="supporting" hasTabularNumbers>
                Showing {pageItems.length} of {filtered.length}
              </Text>
            </VStack>
          ) : null}
        </VStack>

        <BottomSheet isOpen={filtersOpen} onOpenChange={changeFiltersOpen} label="Filter and sort" height="tall">
          <div className="filter-panel filter-panel-sheet">
            {sheetLevel === "root" ? (
              <>
                <div className="filter-panel-header">
                  <Heading level={2}>Filters</Heading>
                </div>
                <VStack gap={5} className="filter-panel-body">
                  <List hasDividers>
                    <ListItem
                      label="Shelf"
                      description={facetValue("shelf")}
                      startContent={<Icon icon={Library} />}
                      endContent={<Icon icon={ChevronRight} />}
                      onClick={() => setSheetLevel("shelf")}
                    />
                    <ListItem
                      label="Topic"
                      description={facetValue("topic")}
                      startContent={<Icon icon={Tag} />}
                      endContent={<Icon icon={ChevronRight} />}
                      onClick={() => setSheetLevel("topic")}
                    />
                  </List>
                  <Divider />
                  {formatSection}
                  {sortSection}
                  <VStack gap={2}>
                    <Text type="label">View</Text>
                    <SegmentedControl label="View" layout="fill" value={view} onChange={value => setView(value as ViewMode)}>
                      <SegmentedControlItem value="grid" label="Grid" icon={<Icon icon={LayoutGrid} />} />
                      <SegmentedControlItem value="list" label="List" icon={<Icon icon={ListIcon} />} />
                    </SegmentedControl>
                  </VStack>
                </VStack>
              </>
            ) : (
              <>
                <HStack gap={2} vAlign="center" className="filter-panel-header">
                  <IconButton label="Back to filters" icon={<Icon icon={ArrowLeft} />} variant="ghost" onClick={() => setSheetLevel("root")} />
                  <Heading level={2}>{sheetLevel === "shelf" ? "Shelf" : "Topic"}</Heading>
                  <StackItem size="fill">
                    <span />
                  </StackItem>
                  <Text type="supporting" hasTabularNumbers>
                    {facetCountLabel[sheetLevel]}
                  </Text>
                </HStack>
                <div className="filter-panel-body filter-panel-body-fill">
                  <FacetList key={sheetLevel} {...(sheetLevel === "shelf" ? shelfFacetProps : topicFacetProps)} />
                </div>
              </>
            )}
            {filterFooter}
          </div>
        </BottomSheet>
      </PageFrame>
    );
  }

  const filterPopover = (
    <Popover
      label="Filter and sort"
      placement="below"
      alignment="start"
      padding={0}
      width={560}
      isOpen={filtersOpen}
      onOpenChange={changeFiltersOpen}
      content={
        <div className="filter-panel filter-panel-popover">
          <div className="facet-panes">
            <nav className="facet-nav" aria-label="Filter facets">
              <List>
                {FACETS.map(facet => (
                  <ListItem
                    key={facet.key}
                    label={facet.label}
                    description={facetValue(facet.key)}
                    startContent={<Icon icon={facet.icon} />}
                    isSelected={activeFacet === facet.key}
                    onClick={() => setActiveFacet(facet.key)}
                  />
                ))}
              </List>
            </nav>
            <div className="facet-pane-stack">
              {FACETS.map(facet => (
                <div key={facet.key} className="facet-pane" inert={activeFacet !== facet.key}>
                  {facetContent[facet.key]}
                </div>
              ))}
            </div>
          </div>
          {filterFooter}
        </div>
      }
    >
      {filterTrigger}
    </Popover>
  );

  const viewToggle = (
    <SegmentedControl label="View" size={CONTROL_SIZE} value={view} onChange={value => setView(value as ViewMode)}>
      <SegmentedControlItem value="grid" label="Grid" icon={<Icon icon={LayoutGrid} />} isLabelHidden />
      <SegmentedControlItem value="list" label="List" icon={<Icon icon={ListIcon} />} isLabelHidden />
    </SegmentedControl>
  );

  const trail = topicParts(topic).map((part, index, parts) => ({ name: part, path: parts.slice(0, index + 1).join("/") }));

  return (
    <PageFrame width="wide">
      <VStack gap={5} className="browse-main">
        <VStack gap={2}>
          {categoryName ? (
            <Breadcrumbs label="Shelf path">
              <BreadcrumbItem href={scopeHref(null)}>Library</BreadcrumbItem>
              <BreadcrumbItem href={topic ? scopeHref("") : undefined} isCurrent={!topic}>
                {categoryName}
              </BreadcrumbItem>
              {trail.map(step => (
                <BreadcrumbItem key={step.path} href={step.path === topic ? undefined : scopeHref(step.path)} isCurrent={step.path === topic}>
                  {step.name}
                </BreadcrumbItem>
              ))}
            </Breadcrumbs>
          ) : null}
          <HStack gap={3} vAlign="center" wrap="wrap">
            <Heading level={1}>{nodeName || "All books"}</Heading>
            <Text type="supporting" hasTabularNumbers>
              {countLabel}
            </Text>
          </HStack>
        </VStack>

        <div className="browse-toolbar" role="group" aria-label="Filter and sort">
          {filterPopover}
          <div className="browse-toolbar-end">{viewToggle}</div>
        </div>

        {activeFilterRow}

        {results}

        {pageCount > 1 ? (
          <HStack hAlign="center">
            <StackItem>
              <Pagination
                page={currentPage}
                totalItems={filtered.length}
                pageSize={pageSize}
                onChange={next => updateParams({ page: next > 1 ? String(next) : null }, false)}
                label="Results pages"
              />
            </StackItem>
          </HStack>
        ) : null}
      </VStack>
    </PageFrame>
  );
}
