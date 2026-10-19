import { Icon } from "@astryxdesign/core/Icon";
import { IconButton } from "@astryxdesign/core/IconButton";
import { Kbd } from "@astryxdesign/core/Kbd";
import { Text } from "@astryxdesign/core/Text";
import { BookOpen, ChevronLeft, House, LibraryBig, Moon, Search, Sun, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { scrollToTop, useIsDesktop } from "../lib/hooks";
import { useLibrary } from "../lib/library";
import { browsePath } from "../lib/routes";
import { topicLeaf } from "../lib/text";
import { GitHubIcon } from "./GitHubIcon";
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

export function Shell({ mode, onToggleMode, children }: ShellProps) {
  const location = useLocation();
  const isDesktop = useIsDesktop();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
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
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    scrollToTop();
  }, [location.pathname]);

  const isBookRoute = location.pathname.startsWith("/book/");
  const section: Section | null =
    location.pathname.startsWith("/browse") || location.pathname.startsWith("/book")
      ? "browse"
      : location.pathname.startsWith("/home")
        ? "home"
        : null;

  const themeToggle = (
    <IconButton
      label={mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      tooltip={mode === "dark" ? "Light theme" : "Dark theme"}
      icon={<Icon icon={mode === "dark" ? Sun : Moon} />}
      variant="ghost"
      size="md"
      onClick={onToggleMode}
    />
  );

  return (
    <>
      <a className="skip-link" href={`#${MAIN_ID}`}>
        Skip to content
      </a>
      <header className="topbar" data-scrolled={scrolled || undefined}>
        <div className="topbar-inner">
          {!isDesktop && isBookRoute ? (
            <BookNavTitle />
          ) : (
            <Link to="/home" className="topbar-brand">
              <BookOpen size={20} strokeWidth={2.25} aria-hidden="true" />
              <span>Bookshelves</span>
            </Link>
          )}
          {isDesktop ? (
            <>
              <nav className="topbar-links" aria-label="Main">
                <TopLink to="/home" label="Home" isSelected={section === "home"} />
                <TopLink to="/browse" label="Browse" isSelected={section === "browse"} />
              </nav>
              <button type="button" className="topbar-search" onClick={openPalette}>
                <Search size={16} aria-hidden="true" />
                <span className="topbar-search-text">Search books, topics, shelves</span>
                <Kbd keys="mod+k" />
              </button>
              <div className="topbar-controls">
                {themeToggle}
                <IconButton
                  label="GitHub repository"
                  tooltip="GitHub"
                  icon={<Icon icon={GitHubIcon} />}
                  variant="ghost"
                  size="md"
                  href={REPO_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                />
              </div>
            </>
          ) : (
            <div className="topbar-controls">
              <IconButton label="Search" tooltip="Search" icon={<Icon icon={Search} />} variant="ghost" size="md" onClick={openPalette} />
              {themeToggle}
            </div>
          )}
        </div>
      </header>
      <main id={MAIN_ID} tabIndex={-1} className="shell-main">
        {children}
      </main>
      {isDesktop ? (
        <SearchPalette isOpen={paletteOpen} onOpenChange={setPaletteOpen} />
      ) : (
        <>
          {isBookRoute ? null : <TabBar section={section} isSearchOpen={paletteOpen} onSearch={openPalette} />}
          <SearchSheet isOpen={paletteOpen} onOpenChange={setPaletteOpen} />
        </>
      )}
    </>
  );
}

function TopLink({ to, label, isSelected }: { to: string; label: string; isSelected: boolean }) {
  return (
    <Link to={to} className="topbar-link" aria-current={isSelected ? "page" : undefined}>
      {label}
    </Link>
  );
}

function BookNavTitle() {
  const location = useLocation();
  const { findBook } = useLibrary();
  const book = findBook(decodeURIComponent(location.pathname.slice("/book/".length)));
  const scopeName = book ? topicLeaf(book.topic) || book.category : "Browse";
  const scopeHref = book ? browsePath({ category: book.category, topic: book.topic }) : "/browse";
  return (
    <div className="topbar-title">
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
