import { BottomSheet } from "@astryxdesign/core/BottomSheet";
import { BreadcrumbItem, Breadcrumbs } from "@astryxdesign/core/Breadcrumbs";
import { Button } from "@astryxdesign/core/Button";
import { CheckboxInput } from "@astryxdesign/core/CheckboxInput";
import { Divider } from "@astryxdesign/core/Divider";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { Grid } from "@astryxdesign/core/Grid";
import { Heading } from "@astryxdesign/core/Heading";
import { HStack } from "@astryxdesign/core/HStack";
import { Icon } from "@astryxdesign/core/Icon";
import { IconButton } from "@astryxdesign/core/IconButton";
import { Link } from "@astryxdesign/core/Link";
import { List, ListItem } from "@astryxdesign/core/List";
import { Pagination } from "@astryxdesign/core/Pagination";
import { ScrollableArea } from "@astryxdesign/core/ScrollableArea";
import { SegmentedControl, SegmentedControlItem } from "@astryxdesign/core/SegmentedControl";
import { Selector } from "@astryxdesign/core/Selector";
import { StackItem } from "@astryxdesign/core/Stack";
import { Text } from "@astryxdesign/core/Text";
import { TextInput } from "@astryxdesign/core/TextInput";
import { Token } from "@astryxdesign/core/Token";
import { VStack } from "@astryxdesign/core/VStack";
import { AlignLeft, ArrowLeft, Check, ChevronRight, Copy, History, Layers, LayoutGrid, Library, List as ListIcon, Search, SlidersHorizontal, Tag } from "lucide-react";
import { type CSSProperties, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
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
import type { Book, BookFormat, CategorySummary, TopicNode } from "../lib/types";
import "./browse.css";

const PAGE_SIZE = 24;
const GRID_ROWS_PER_PAGE = 4;
const CONTROL_SIZE = "md";
const DEFAULT_SORT: SortKey = "title-asc";
const SELECTED_TOKEN_COLOR = "orange";

type SortKey = "title-asc" | "title-desc" | "category";
type GroupKey = "topic" | "category" | "format";
type QuickKey = "described" | "multi" | "viewed";

const GROUP_OPTIONS: { value: GroupKey | "none"; label: string }[] = [
  { value: "none", label: "No grouping" },
  { value: "topic", label: "By topic" },
  { value: "category", label: "By shelf" },
  { value: "format", label: "By format" }
];

const QUICK_FILTERS: { key: QuickKey; label: string; icon: typeof Copy }[] = [
  { key: "described", label: "Has description", icon: AlignLeft },
  { key: "multi", label: "Multiple formats", icon: Copy },
  { key: "viewed", label: "Viewed", icon: History }
];

function isGroupKey(value: string | null): value is GroupKey {
  return value === "topic" || value === "category" || value === "format";
}
type ViewMode = "grid" | "list";
type FacetKey = "shelf" | "topic";
type SheetLevel = "root" | "shelf" | "topic";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "title-asc", label: "Title A–Z" },
  { value: "title-desc", label: "Title Z–A" },
  { value: "category", label: "By category" }
];

function isFormat(value: string): value is BookFormat {
  return value === "pdf" || value === "epub" || value === "docx";
}

function parseFormats(value: string | null): BookFormat[] {
  return [...new Set((value || "").split(",").filter(isFormat))];
}

function sameSet(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every(entry => b.includes(entry));
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

interface TopicRow {
  path: string;
  name: string;
  count: number;
  depth: number;
}

function topicRowsOf(nodes: TopicNode[], depth = 0): TopicRow[] {
  return nodes.flatMap(node => [{ path: node.path, name: node.name, count: node.count, depth }, ...topicRowsOf(node.children, depth + 1)]);
}

interface RailRowProps {
  label: string;
  count: number;
  href?: string;
  onClick?: () => void;
  isSelected: boolean;
  depth?: number;
  isTopic?: boolean;
}

function RailRow({ label, count, href, onClick, isSelected, depth = 0, isTopic = false }: RailRowProps) {
  return (
    <ListItem
      className={isTopic ? "browse-rail-row browse-rail-topic" : "browse-rail-row"}
      style={{ "--rail-depth": depth } as CSSProperties}
      label={label}
      href={href}
      onClick={onClick}
      isSelected={isSelected}
      endContent={
        <Text type="supporting" hasTabularNumbers>
          {count}
        </Text>
      }
    />
  );
}

interface FilterPanelProps {
  scopedBooks: Book[];
  availableFormats: BookFormat[];
  formats: BookFormat[];
  quick: QuickKey[];
  recentIds: string[];
  onApply: (formats: BookFormat[], quick: QuickKey[]) => void;
}

function quickMatches(book: Book, key: QuickKey, recentIds: string[]): boolean {
  if (key === "described") return book.description.trim().length > 0;
  if (key === "multi") return book.formats.length > 1;
  return book.rawIds.some(id => recentIds.includes(id));
}

function FilterPanel({ scopedBooks, availableFormats, formats, quick, recentIds, onApply }: FilterPanelProps) {
  const [draftFormats, setDraftFormats] = useState<BookFormat[]>(formats);
  const [draftQuick, setDraftQuick] = useState<QuickKey[]>(quick);
  const appliedKey = `${formats.join(",")}|${quick.join(",")}`;
  const [syncedKey, setSyncedKey] = useState(appliedKey);
  if (syncedKey !== appliedKey) {
    setSyncedKey(appliedKey);
    setDraftFormats(formats);
    setDraftQuick(quick);
  }
  const isDirty = !sameSet(draftFormats, formats) || !sameSet(draftQuick, quick);
  const hasAny = draftFormats.length > 0 || draftQuick.length > 0;
  const formatCount = (entry: BookFormat) => scopedBooks.filter(book => book.formats.includes(entry)).length;
  const quickCount = (key: QuickKey) =>
    scopedBooks.filter(book => (!draftFormats.length || book.formats.some(entry => draftFormats.includes(entry))) && quickMatches(book, key, recentIds)).length;
  const toggleFormat = (entry: BookFormat, on: boolean) =>
    setDraftFormats(current => (on ? [...current, entry] : current.filter(item => item !== entry)));
  const toggleQuick = (key: QuickKey, on: boolean) => setDraftQuick(current => (on ? [...current, key] : current.filter(item => item !== key)));

  return (
    <div className="filter-panel-stack" role="group" aria-label="Filters">
      <VStack gap={1} className="filter-panel-group">
        <span className="eyebrow">Format</span>
        {availableFormats.map(entry => (
          <label key={entry} className="filter-check">
            <CheckboxInput label={formatLabel(entry)} value={draftFormats.includes(entry)} onChange={checked => toggleFormat(entry, checked)} />
            <Text type="supporting" hasTabularNumbers>
              {formatCount(entry)}
            </Text>
          </label>
        ))}
      </VStack>
      <VStack gap={1} className="filter-panel-group">
        <span className="eyebrow">More</span>
        {QUICK_FILTERS.map(entry => (
          <label key={entry.key} className="filter-check">
            <CheckboxInput label={entry.label} value={draftQuick.includes(entry.key)} onChange={checked => toggleQuick(entry.key, checked)} />
            <Text type="supporting" hasTabularNumbers>
              {quickCount(entry.key)}
            </Text>
          </label>
        ))}
      </VStack>
      <HStack gap={2} vAlign="center" className="filter-panel-actions">
        <Button label="Apply" variant="primary" size="sm" isDisabled={!isDirty} onClick={() => onApply(draftFormats, draftQuick)} />
        <Button
          label="Reset"
          variant="ghost"
          size="sm"
          isDisabled={!hasAny && !formats.length && !quick.length}
          onClick={() => {
            setDraftFormats([]);
            setDraftQuick([]);
            onApply([], []);
          }}
        />
      </HStack>
    </div>
  );
}

interface BrowseRailProps {
  books: Book[];
  categories: CategorySummary[];
  category: CategorySummary | null;
  topic: string;
  categoryHref: (name: string | null) => string;
  scopeHref: (topicPath: string | null) => string;
  filterPanel: ReactNode;
}

function BrowseRail({ books, categories, category, topic, categoryHref, scopeHref, filterPanel }: BrowseRailProps) {
  const topicRows = useMemo(() => (category ? topicRowsOf(category.topics) : []), [category]);

  return (
    <aside className="browse-rail" aria-label="Library filters">
      <nav className="browse-rail-block" aria-label="Shelves">
        <Heading level={3} accessibilityLevel={2}>
          Library
        </Heading>
        <List density="compact">
          <RailRow label="All books" count={books.length} href={categoryHref(null)} isSelected={!category} />
          {categories.map(entry => (
            <RailRow key={entry.name} label={entry.name} count={entry.count} href={categoryHref(entry.name)} isSelected={entry === category} />
          ))}
        </List>
      </nav>

      {category && topicRows.length ? (
        <nav className="browse-rail-block" aria-label={`Topics in ${category.name}`}>
          <span className="eyebrow">Topics</span>
          <List density="compact">
            <RailRow label="All topics" count={category.count} href={scopeHref("")} isSelected={!topic} />
            {topicRows.map(row => (
              <RailRow key={row.path} label={row.name} count={row.count} href={scopeHref(row.path)} isSelected={row.path === topic} depth={row.depth + 1} isTopic />
            ))}
          </List>
        </nav>
      ) : null}

      <div className="browse-rail-block">{filterPanel}</div>
    </aside>
  );
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

function FacetList({ label, placeholder, groups }: { label: string; placeholder: string; groups: FacetGroup[] }) {
  const [search, setSearch] = useState("");
  const needle = normalizeForSearch(search.trim());
  const visibleGroups = needle
    ? groups
        .map(group => ({ ...group, rows: group.rows.filter(row => normalizeForSearch(`${group.header ?? ""} ${row.label}`).includes(needle)) }))
        .filter(group => group.rows.length)
    : groups;

  return (
    <div className="facet-list">
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
  const { status, books, categories, recentIds } = useLibrary();
  const [params, setParams] = useSearchParams();
  const isDesktop = useIsDesktop();
  const isPhone = useIsPhone();
  const [view, setView] = useStoredState<ViewMode>(STORAGE_KEYS.view, "grid");
  const [gridRef, gridColumns] = useGridColumns();

  const categoryName = params.get("category") || "";
  const topic = params.get("topic") || "";
  const query = params.get("q") || "";
  const sort = (params.get("sort") as SortKey) || DEFAULT_SORT;
  const formats = parseFormats(params.get("format"));
  const formatKey = formats.join(",");
  const page = Math.max(1, Number(params.get("page")) || 1);
  const groupParam = params.get("group");
  const groupBy: GroupKey | null = isGroupKey(groupParam) ? groupParam : null;
  const grouped = groupBy !== null;
  const quick = QUICK_FILTERS.map(entry => entry.key).filter(key => params.get(key) === "1");
  const quickSet = new Set<QuickKey>(quick);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [sheetLevel, setSheetLevel] = useState<SheetLevel>("root");

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
      if (!formatKey) return href;
      return `${href}${href.includes("?") ? "&" : "?"}format=${formatKey}`;
    },
    [categoryName, formatKey]
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
    if (formats.length) list = list.filter(book => book.formats.some(entry => formats.includes(entry)));
    for (const key of quick) list = list.filter(book => quickMatches(book, key, recentIds));
    if (query.trim()) return searchBooks(list, query);
    const sorted = [...list];
    if (sort === "title-desc") sorted.sort((a, b) => b.title.localeCompare(a.title));
    else if (sort === "category") sorted.sort((a, b) => a.category.localeCompare(b.category) || a.topic.localeCompare(b.topic) || byTitle(a, b));
    else sorted.sort(byTitle);
    return sorted;
  }, [books, categoryName, topic, formatKey, query, sort, quick.join(","), recentIds]);

  const topicChips = useMemo(() => (category ? topicChipsOf(category.topics) : []), [category]);
  const libraryTopics = useMemo(
    () => categories.map(entry => ({ name: entry.name, chips: topicChipsOf(entry.topics) })).filter(entry => entry.chips.length),
    [categories]
  );

  const topicSections = useMemo(() => {
    if (!groupBy) return [];
    const sections = new Map<string, { key: string; title: string; href: string | null; books: Book[] }>();
    for (const book of filtered) {
      let key: string;
      let title: string;
      let href: string | null;
      if (groupBy === "topic") {
        const relative = topic ? book.topic.slice(topic.length).replace(/^\//, "") : book.topic;
        title = categoryName ? relative || topicLeaf(book.topic) : `${book.category} / ${book.topic}`;
        key = `${book.category}::${book.topic}`;
        href = browsePath({ category: book.category, topic: book.topic });
      } else if (groupBy === "category") {
        title = book.category;
        key = book.category;
        href = browsePath({ category: book.category });
      } else {
        const primary = book.formats[0];
        title = book.formats.map(formatLabel).join(" + ");
        key = book.formats.join("+");
        href = book.formats.length === 1 ? browsePath({ category: categoryName || undefined, topic: topic || undefined }) + `${categoryName || topic ? "&" : "?"}format=${primary}` : null;
      }
      const section = sections.get(key) ?? { key, title, href, books: [] };
      section.books.push(book);
      sections.set(key, section);
    }
    return [...sections.values()].sort((a, b) => a.title.localeCompare(b.title));
  }, [groupBy, filtered, topic, categoryName]);

  const pageSize = isDesktop && view === "grid" && gridColumns ? gridColumns * GRID_ROWS_PER_PAGE : PAGE_SIZE;
  const pageCount = grouped ? 1 : Math.max(1, Math.ceil(filtered.length / pageSize));
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
      const selectedChip = row.querySelector<HTMLElement>(`[data-color="${SELECTED_TOKEN_COLOR}"]`);
      if (!selectedChip) continue;
      const rowRect = row.getBoundingClientRect();
      const chipRect = selectedChip.getBoundingClientRect();
      row.scrollLeft += chipRect.left - rowRect.left - (rowRect.width - chipRect.width) / 2;
    }
  }, [categoryName, topic, categories, isDesktop]);

  const quickReset = QUICK_FILTERS.reduce<Record<string, string | null>>((acc, entry) => ({ ...acc, [entry.key]: null }), {});
  const hasActiveFilters = Boolean(formats.length || query.trim() || quick.length);
  const resetFilters = () => updateParams({ q: null, format: null, ...quickReset });
  const resetAllFilters = () => updateParams({ q: null, format: null, sort: null, category: null, topic: null, group: null, ...quickReset });
  const filterCount = [categoryName, topic, sort !== DEFAULT_SORT, ...formats, ...quick].filter(Boolean).length;
  const changeFiltersOpen = (isOpen: boolean) => {
    setFiltersOpen(isOpen);
    if (!isOpen) setSheetLevel("root");
  };

  if (status === "error") {
    return (
      <PageFrame width="wide">
        <LoadErrorState />
      </PageFrame>
    );
  }

  const groupSelector = (
    <Selector
      label="Group"
      isLabelHidden
      size={CONTROL_SIZE}
      width={164}
      startIcon={Layers}
      options={GROUP_OPTIONS}
      value={groupBy ?? "none"}
      onChange={value => updateParams({ group: isGroupKey(value) ? value : null })}
    />
  );

  const groupSection = (
    <VStack gap={2}>
      <Text type="label">Group</Text>
      <SegmentedControl label="Group" layout="fill" value={groupBy ?? "none"} onChange={value => updateParams({ group: isGroupKey(value) ? value : null })}>
        <SegmentedControlItem value="none" label="None" />
        <SegmentedControlItem value="topic" label="Topic" />
        <SegmentedControlItem value="category" label="Shelf" />
        <SegmentedControlItem value="format" label="Format" />
      </SegmentedControl>
    </VStack>
  );

  const activeFilters = [
    categoryName ? { key: "category", label: `Shelf: ${categoryName}`, remove: () => updateParams({ category: null, topic: null }) } : null,
    topic ? { key: "topic", label: `Topic: ${topicParts(topic).join(" / ")}`, remove: () => updateParams({ topic: null }) } : null,
    ...formats.map(entry => ({ key: `format-${entry}`, label: formatLabel(entry), remove: () => updateParams({ format: formats.filter(item => item !== entry).join(",") || null }) })),
    sort !== DEFAULT_SORT
      ? { key: "sort", label: SORT_OPTIONS.find(option => option.value === sort)?.label ?? sort, remove: () => updateParams({ sort: null }) }
      : null,
    query.trim() ? { key: "q", label: `“${query.trim()}”`, remove: () => updateParams({ q: null }) } : null,
    ...QUICK_FILTERS.filter(entry => quickSet.has(entry.key)).map(entry => ({ key: entry.key, label: entry.label, remove: () => updateParams({ [entry.key]: null }) }))
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
      onClick={() => changeFiltersOpen(true)}
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
  const facetCountLabel: Record<FacetKey, string> = {
    shelf: `${categories.length} ${categories.length === 1 ? "shelf" : "shelves"}`,
    topic: `${topicTotal} ${topicTotal === 1 ? "topic" : "topics"}`
  };

  const facetSummary: Record<FacetKey, string> = {
    shelf: categoryName || "All",
    topic: topic ? topicParts(topic).join(" / ") : "All"
  };
  const facetIsSet: Record<FacetKey, boolean> = {
    shelf: Boolean(categoryName),
    topic: Boolean(topic)
  };
  const facetValue = (key: FacetKey) => <span className={facetIsSet[key] ? "facet-value-active" : undefined}>{facetSummary[key]}</span>;

  const scopedBooks = useMemo(
    () => books.filter(book => (!categoryName || book.category === categoryName) && (!topic || topicMatches(book, topic))),
    [books, categoryName, topic]
  );
  const applyFilters = (nextFormats: BookFormat[], nextQuick: QuickKey[]) =>
    updateParams({
      format: nextFormats.join(",") || null,
      ...Object.fromEntries(QUICK_FILTERS.map(entry => [entry.key, nextQuick.includes(entry.key) ? "1" : null]))
    });
  const filterPanel = (
    <FilterPanel scopedBooks={scopedBooks} availableFormats={availableFormats} formats={formats} quick={quick} recentIds={recentIds} onApply={applyFilters} />
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
    ) : grouped ? (
      <VStack gap={10} className="browse-groups">
        {topicSections.map(section => (
          <section key={section.key} className="browse-group" aria-label={section.title}>
            <div className="section-head">
              <Heading level={2}>{section.title}</Heading>
              <Text type="supporting" hasTabularNumbers>
                {section.books.length} {section.books.length === 1 ? "book" : "books"}
              </Text>
              <span className="section-head-fill" />
              {section.href && section.href !== browsePath({ category: categoryName, topic }) ? (
                <Link href={section.href} isStandalone size="sm">
                  {groupBy === "category" ? "Open shelf" : groupBy === "format" ? "Only this format" : "Open topic"}
                </Link>
              ) : null}
            </div>
            {view === "grid" ? (
              <Grid columns={{ minWidth: isDesktop ? 160 : 120 }} gap={isPhone ? 3 : 5} rowGap={isPhone ? 6 : 8} className="book-grid">
                {section.books.map(book => (
                  <BookCard key={book.id} book={book} showCategory={!categoryName} />
                ))}
              </Grid>
            ) : (
              <VStack gap={0} className="book-list">
                {section.books.map(book => (
                  <BookRow key={book.id} book={book} />
                ))}
              </VStack>
            )}
          </section>
        ))}
      </VStack>
    ) : view === "grid" ? (
      <Grid
        ref={gridRef}
        columns={{ minWidth: isDesktop ? 160 : 120 }}
        gap={isPhone ? 3 : 5}
        rowGap={isPhone ? 6 : 8}
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
                color={categoryName ? "default" : SELECTED_TOKEN_COLOR}
                endContent={books.length || undefined}
              />
              {categories.map(entry => (
                <Token
                  key={entry.name}
                  label={entry.name}
                  size="sm"
                  href={categoryHref(entry.name)}
                  color={entry.name === categoryName ? SELECTED_TOKEN_COLOR : "default"}
                  endContent={entry.count}
                />
              ))}
            </nav>
            {category && topicChips.length ? (
              <nav className="chip-row" aria-label={`Topics in ${category.name}`}>
                <Token label="All" size="sm" href={scopeHref("")} color={topic ? "default" : SELECTED_TOKEN_COLOR} endContent={category.count} />
                {topicChips.map(chip => (
                  <Token
                    key={chip.path}
                    label={chip.label}
                    size="sm"
                    href={scopeHref(chip.path)}
                    color={chip.path === topic ? SELECTED_TOKEN_COLOR : "default"}
                    endContent={chip.count}
                  />
                ))}
              </nav>
            ) : null}
            <HStack gap={2} vAlign="center">
              <StackItem size="fill">{groupSelector}</StackItem>
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

          {!grouped && pageItems.length < filtered.length ? (
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
                  {filterPanel}
                  {groupSection}
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

  const viewToggle = (
    <SegmentedControl label="View" size={CONTROL_SIZE} value={view} onChange={value => setView(value as ViewMode)}>
      <SegmentedControlItem value="grid" label="Grid" icon={<Icon icon={LayoutGrid} />} isLabelHidden />
      <SegmentedControlItem value="list" label="List" icon={<Icon icon={ListIcon} />} isLabelHidden />
    </SegmentedControl>
  );

  const sortSelector = (
    <Selector
      label="Sort"
      isLabelHidden
      size={CONTROL_SIZE}
      width={160}
      options={SORT_OPTIONS}
      value={sort}
      onChange={value => updateParams({ sort: value === DEFAULT_SORT ? null : value })}
      isDisabled={Boolean(query.trim())}
      disabledMessage="Results are ranked by relevance while a search is active"
    />
  );

  const trail = topicParts(topic).map((part, index, parts) => ({ name: part, path: parts.slice(0, index + 1).join("/") }));

  return (
    <PageFrame width="wide">
      <div className="browse-layout">
        <BrowseRail
          books={books}
          categories={categories}
          category={category}
          topic={topic}
          categoryHref={categoryHref}
          scopeHref={scopeHref}
          filterPanel={filterPanel}
        />

        <VStack gap={5} className="browse-main">
          <VStack gap={1}>
            <HStack gap={3} vAlign="end" wrap="wrap">
              <Heading level={1}>{categoryName || "All books"}</Heading>
              <Text type="supporting" hasTabularNumbers>
                {countLabel}
              </Text>
            </HStack>
            {topic ? (
              <Breadcrumbs label="Topic path">
                <BreadcrumbItem href={scopeHref("")}>{categoryName}</BreadcrumbItem>
                {trail.map(step => (
                  <BreadcrumbItem key={step.path} href={step.path === topic ? undefined : scopeHref(step.path)} isCurrent={step.path === topic}>
                    {step.name}
                  </BreadcrumbItem>
                ))}
              </Breadcrumbs>
            ) : null}
          </VStack>

          <div className="browse-toolbar" role="group" aria-label="Filter, group, sort and view">
            {groupSelector}
            <div className="browse-toolbar-end">
              {sortSelector}
              {viewToggle}
            </div>
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
      </div>
    </PageFrame>
  );
}
