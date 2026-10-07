import { AppShell } from "@astryxdesign/core/AppShell";
import { Button } from "@astryxdesign/core/Button";
import { Icon } from "@astryxdesign/core/Icon";
import { IconButton } from "@astryxdesign/core/IconButton";
import { Kbd } from "@astryxdesign/core/Kbd";
import { SideNav, SideNavHeading, SideNavItem, SideNavSection } from "@astryxdesign/core/SideNav";
import { Text } from "@astryxdesign/core/Text";
import { BookOpen, ChevronLeft, Folder, House, LibraryBig, Moon, Search, Sun, type LucideIcon } from "lucide-react";
import { GitHubIcon } from "./GitHubIcon";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { scrollToTop, useIsDesktop } from "../lib/hooks";
import { useLibrary } from "../lib/library";
import { bookPath, browsePath } from "../lib/routes";
import { topicLeaf, topicParts } from "../lib/text";
import type { Book, CategorySummary, TopicNode } from "../lib/types";
import { SearchPalette } from "./SearchPalette";
import { SearchSheet } from "./SearchSheet";

export type ColorMode = "light" | "dark";

type Section = "home" | "browse";

interface ShellProps {
  mode: ColorMode;
  onToggleMode: () => void;
  children: ReactNode;
}

const REPO_URL = "https://github.com/Patruxs/bookshelves";
const MAIN_ID = "main-content";
const RECENT_LIMIT = 3;

export function Shell({ mode, onToggleMode, children }: ShellProps) {
  const location = useLocation();
  const isDesktop = useIsDesktop();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const openPalette = useCallback(() => setPaletteOpen(true), []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(current => !current);
      }
      if (event.key === "/" && !paletteOpen) {
        const target = event.target as HTMLElement | null;
        const tag = target?.tagName?.toLowerCase();
        if (tag === "input" || tag === "textarea" || target?.isContentEditable) return;
        event.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [paletteOpen]);

  useEffect(() => {
    scrollToTop();
  }, [location.pathname]);

  const isBookRoute = location.pathname.startsWith("/book/");
  const section: Section | null = location.pathname.startsWith("/browse") || location.pathname.startsWith("/book")
    ? "browse"
    : location.pathname.startsWith("/home")
      ? "home"
      : null;

  const themeToggle = (size?: "md") => (
    <IconButton
      label={mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      tooltip={mode === "dark" ? "Light theme" : "Dark theme"}
      icon={<Icon icon={mode === "dark" ? Sun : Moon} />}
      variant="ghost"
      size={size}
      onClick={onToggleMode}
    />
  );

  if (isDesktop) {
    return (
      <AppShell
        height="fill"
        variant="section"
        mobileNav={false}
        contentPadding={0}
        sideNav={<Sidebar section={section} onSearch={openPalette} themeToggle={themeToggle()} />}
      >
        {children}
        <SearchPalette isOpen={paletteOpen} onOpenChange={setPaletteOpen} />
      </AppShell>
    );
  }

  return (
    <>
      <a className="skip-link" href={`#${MAIN_ID}`}>
        Skip to content
      </a>
      <header className="nav">
        <div className="nav-inner">
          {isBookRoute ? (
            <BookNavTitle />
          ) : (
            <Link to="/home" className="nav-brand">
              <BookOpen size={20} strokeWidth={2} aria-hidden="true" />
              <span>Bookshelves</span>
            </Link>
          )}
          <div className="nav-controls">{themeToggle("md")}</div>
        </div>
      </header>
      <main id={MAIN_ID} tabIndex={-1} className="shell-main">
        {children}
      </main>
      {isBookRoute ? null : <TabBar section={section} isSearchOpen={paletteOpen} onSearch={openPalette} />}
      <SearchSheet isOpen={paletteOpen} onOpenChange={setPaletteOpen} />
    </>
  );
}

interface SidebarProps {
  section: Section | null;
  onSearch: () => void;
  themeToggle: ReactNode;
}

function Sidebar({ section, onSearch, themeToggle }: SidebarProps) {
  const location = useLocation();
  const { categories, recentIds, findBook } = useLibrary();
  const [isCollapsed, setIsCollapsed] = useState(false);

  const isBrowsePath = location.pathname.startsWith("/browse");
  const browseParams = isBrowsePath ? new URLSearchParams(location.search) : null;
  const activeCategory = browseParams?.get("category") ?? null;
  const activeShelf = categories.find(category => category.name === activeCategory) ?? null;
  const selectedTopicPath = activeShelf ? existingTopicPath(activeShelf, browseParams?.get("topic") ?? "") : null;
  const { isExpanded, setExpanded } = useShelfExpansion(activeShelf, selectedTopicPath);
  const activeBookId = location.pathname.startsWith("/book/") ? decodeURIComponent(location.pathname.slice("/book/".length)) : null;
  const recentBooks = recentIds
    .map(id => findBook(id))
    .filter((book): book is Book => Boolean(book))
    .slice(0, RECENT_LIMIT);
  const isShelfSelected = activeShelf !== null;
  const isRecentSelected = recentBooks.some(book => book.id === activeBookId);
  const isBrowseSelected = section === "browse" && !isShelfSelected && !isRecentSelected;

  return (
    <SideNav
      collapsible={{ isCollapsed, onCollapsedChange: setIsCollapsed }}
      header={
        <SideNavHeading
          className="wordmark"
          icon={<Icon icon={BookOpen} />}
          heading="Bookshelves"
          headingHref="/home"
        />
      }
      topContent={
        isCollapsed ? (
          <div className="side-search-collapsed">
            <IconButton label="Search" tooltip="Search" icon={<Icon icon={Search} />} variant="ghost" onClick={onSearch} />
          </div>
        ) : (
          <button type="button" className="side-search" onClick={onSearch}>
            <Search size={16} aria-hidden="true" />
            <span className="side-search-text">Search</span>
            <Kbd keys="mod+k" />
          </button>
        )
      }
      footerIcons={
        <>
          {themeToggle}
          <Button
            label="GitHub repository"
            icon={<Icon icon={GitHubIcon} />}
            isIconOnly
            variant="ghost"
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            tooltip="GitHub"
          />
        </>
      }
    >
      <SideNavSection title="Main" isHeaderHidden>
        <SideNavItem label="Home" icon={House} href="/home" isSelected={section === "home"} />
        <SideNavItem label="Browse" icon={LibraryBig} href="/browse" isSelected={isBrowseSelected} />
      </SideNavSection>
      <SideNavSection title="Shelves" className="side-tree">
        {categories.map(category => (
          <SideNavItem
            key={category.name}
            label={category.name}
            icon={isCollapsed ? Folder : undefined}
            href={browsePath({ category: category.name })}
            isSelected={category === activeShelf && selectedTopicPath === null}
            endContent={<SideCount count={category.count} />}
            collapsible={{
              isCollapsed: !isExpanded(category.name),
              onCollapsedChange: collapsed => setExpanded(category.name, !collapsed),
            }}
            onClick={() => setExpanded(category.name, true)}
          >
            {category.topics.length > 0 ? (
              <TopicItems
                category={category}
                nodes={category.topics}
                selectedPath={category === activeShelf ? selectedTopicPath : null}
                isExpanded={isExpanded}
                setExpanded={setExpanded}
              />
            ) : undefined}
          </SideNavItem>
        ))}
      </SideNavSection>
      {recentBooks.length > 0 ? (
        <SideNavSection title="Recently viewed">
          {recentBooks.map(book => (
            <SideNavItem
              key={book.id}
              label={book.title}
              icon={isCollapsed ? BookOpen : undefined}
              href={bookPath(book.id)}
              isSelected={book.id === activeBookId}
            />
          ))}
        </SideNavSection>
      ) : null}
    </SideNav>
  );
}

function existingTopicPath(category: CategorySummary, path: string): string | null {
  let nodes = category.topics;
  let found: TopicNode | undefined;
  for (const part of topicParts(path)) {
    found = nodes.find(node => node.name === part);
    if (!found) return null;
    nodes = found.children;
  }
  return found?.path ?? null;
}

function topicKey(category: string, path: string): string {
  return `${category}\u0000${path}`;
}

function useShelfExpansion(activeShelf: CategorySummary | null, selectedTopicPath: string | null) {
  const urlKeys = activeShelf ? [activeShelf.name] : [];
  if (activeShelf && selectedTopicPath) {
    let path = "";
    for (const part of topicParts(selectedTopicPath)) {
      path = path ? `${path}/${part}` : part;
      urlKeys.push(topicKey(activeShelf.name, path));
    }
  }
  const urlSignature = urlKeys.join("\n");
  const [expandedKeys, setExpandedKeys] = useState<ReadonlySet<string>>(() => new Set(urlKeys));
  const [syncedSignature, setSyncedSignature] = useState(urlSignature);

  if (syncedSignature !== urlSignature) {
    setSyncedSignature(urlSignature);
    setExpandedKeys(current => (urlKeys.every(key => current.has(key)) ? current : new Set([...current, ...urlKeys])));
  }

  const isExpanded = useCallback((key: string) => expandedKeys.has(key), [expandedKeys]);
  const setExpanded = useCallback((key: string, expanded: boolean) => {
    setExpandedKeys(current => {
      if (current.has(key) === expanded) return current;
      const next = new Set(current);
      if (expanded) next.add(key);
      else next.delete(key);
      return next;
    });
  }, []);

  return { isExpanded, setExpanded };
}

interface TopicItemsProps {
  category: CategorySummary;
  nodes: TopicNode[];
  selectedPath: string | null;
  isExpanded: (key: string) => boolean;
  setExpanded: (key: string, expanded: boolean) => void;
}

function TopicItems({ category, nodes, selectedPath, isExpanded, setExpanded }: TopicItemsProps) {
  return (
    <>
      {nodes.map(node => {
        const key = topicKey(category.name, node.path);
        const hasChildren = node.children.length > 0;
        return (
          <SideNavItem
            key={node.path}
            label={node.name}
            href={browsePath({ category: category.name, topic: node.path })}
            isSelected={node.path === selectedPath}
            endContent={<SideCount count={node.count} hasToggleGap={!hasChildren} />}
            collapsible={
              hasChildren ? { isCollapsed: !isExpanded(key), onCollapsedChange: collapsed => setExpanded(key, !collapsed) } : false
            }
            onClick={hasChildren ? () => setExpanded(key, true) : undefined}
          >
            {hasChildren ? (
              <TopicItems
                category={category}
                nodes={node.children}
                selectedPath={selectedPath}
                isExpanded={isExpanded}
                setExpanded={setExpanded}
              />
            ) : undefined}
          </SideNavItem>
        );
      })}
    </>
  );
}

function SideCount({ count, hasToggleGap = false }: { count: number; hasToggleGap?: boolean }) {
  return (
    <Text type="supporting" hasTabularNumbers className={hasToggleGap ? "side-count-leaf" : undefined}>
      {count}
    </Text>
  );
}

function BookNavTitle() {
  const location = useLocation();
  const { findBook } = useLibrary();
  const book = findBook(decodeURIComponent(location.pathname.slice("/book/".length)));
  const scopeName = book ? topicLeaf(book.topic) || book.category : "Browse";
  const scopeHref = book ? browsePath({ category: book.category, topic: book.topic }) : "/browse";
  return (
    <div className="nav-title">
      <IconButton label={`Back to ${scopeName}`} icon={<Icon icon={ChevronLeft} />} variant="ghost" size="md" href={scopeHref} />
      <Text type="label" maxLines={1} hasTruncateTooltip={false}>
        {scopeName}
      </Text>
    </div>
  );
}

interface TabBarProps {
  section: Section | null;
  isSearchOpen: boolean;
  onSearch: () => void;
}

function TabBar({ section, isSearchOpen, onSearch }: TabBarProps) {
  return (
    <nav className="tabbar" aria-label="Sections">
      <TabBarLink to="/home" icon={House} label="Home" isSelected={!isSearchOpen && section === "home"} />
      <TabBarLink to="/browse" icon={LibraryBig} label="Browse" isSelected={!isSearchOpen && section === "browse"} />
      <button
        type="button"
        className="tabbar-item"
        aria-haspopup="dialog"
        aria-expanded={isSearchOpen}
        data-selected={isSearchOpen || undefined}
        onClick={onSearch}
      >
        <Icon icon={Search} />
        <span>Search</span>
      </button>
    </nav>
  );
}

function TabBarLink({ to, icon, label, isSelected }: { to: string; icon: LucideIcon; label: string; isSelected: boolean }) {
  return (
    <Link to={to} className="tabbar-item" aria-current={isSelected ? "page" : undefined} data-selected={isSelected || undefined}>
      <Icon icon={icon} />
      <span>{label}</span>
    </Link>
  );
}
