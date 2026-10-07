# Mobile UX redesign

Scope: the `web/` app at viewports under 1024px, with the phone layout (≤ 639px) as the primary target. Desktop (≥ 1024px) must not change visually. Tablet (640–1023px) keeps the mobile shell but may use wider grids.

Audit date: 2026-10-07, iPhone 13 viewport (390×844), light mode, `vite preview` of the current build.

## What is wrong today

Measured from screenshots of the current build.

| Screen | Problem |
| --- | --- |
| Home | Page is ~11 800px tall (≈14 screens). Greeting + hero pick take 1.5 screens before any other book is visible. Hero cover is centered at 140px with eyebrow, path, a 3-line display title, excerpt and two buttons. |
| Home | Five stacked category tiles (each ~110px of mostly empty card with a 32px cover fan) followed by five carousels for the same five categories, plus a topic chip row. Three navigations to the same place. |
| Home | "Start here" list sits in a bordered card with numbers; titles truncate at ~20 characters. |
| Browse | ~1 000px of chrome before the first cover: chip row, breadcrumb (wraps to 2 lines), display heading, count, large text input, then two rows of `lg` controls (Topics, Format, Sort, view toggle). The selected chip, the breadcrumb and the heading repeat the same name three times. |
| Browse | Grid is 2 columns of 132px+ min cards, so each cover renders ~165px wide and ~250px tall. Only two books fit per screen. |
| Browse | Pagination renders a desktop page-number strip. |
| Book | Ghost "Back to X" button, then a bordered card inside the page padding (double frame), 180px centered cover, uppercase eyebrow, topic, display title, "PDF" text, then a 2×2 button grid where the share icon sits alone in a cell. Related books are in a card with a dangling "View all" link under it. |
| Search | The desktop command palette opens as a centered dialog with a keyboard-hint footer (↑ ↓ Navigate, Enter Select, Esc Close). The on-screen keyboard will cover the lower half. |
| Shell | 52px top bar + 56px tab bar with only two tabs. Search, the most used action, is a small icon in the top-right corner, out of thumb reach. |

## Design principles

1. Covers are the content. Chrome above the first cover on any screen ≤ 250px.
2. One way to reach each place. No duplicated navigation on the same screen.
3. Thumb reach. Primary actions live in the bottom 40% of the screen.
4. Native feel. Sheets instead of dialogs, "Load more" instead of page numbers, no keyboard hints on touch.
5. Astryx first. Use Astryx components and tokens; custom CSS only in `web/src/styles.css` and only with tokens. Look up every prop with `npx astryx component <Name>` from `web/` before using it.

## Breakpoints

| Name | Query | Used for |
| --- | --- | --- |
| phone | `(max-width: 639px)` | All layout rules below unless stated |
| tablet | `(min-width: 640px) and (max-width: 1023px)` | Mobile shell, wider grids |
| desktop | `(min-width: 1024px)` | Unchanged |

Keep `useMediaQuery` in `web/src/lib/hooks.ts`; add named helpers if it reduces repetition (`useIsPhone`, `useIsDesktop`).

## Shell (phone + tablet)

Top bar, 48px, sticky, translucent as today:
- Home and Browse routes: wordmark left, theme toggle right. Nothing else.
- Book route: back `IconButton` (chevron left) at the left that navigates to the book's topic in Browse, then the topic name as a single-line `Text type="label"`. No wordmark. Theme toggle stays right.

Bottom tab bar, 56px + safe area, three tabs:
- Home, Browse, Search. Equal width. Selected tab uses `color-text-primary` and the label gets `font-weight-semibold`; unselected uses `color-text-secondary`.
- Search is a button, not a link; it opens the search sheet (below). While the sheet is open the Search tab shows as selected.
- Hide the tab bar on the Book route; the book action bar takes its place (see Book).
- Remove the `/` and `mod+k` keyboard shortcuts' visual hints on mobile (they are already hidden; keep the listeners).

## Search (phone + tablet)

Replace `CommandPalette` on mobile with a full-height `BottomSheet` (check `height` options with `npx astryx component BottomSheet`; if it has no full option, use the tallest and accept it).

Layout inside the sheet:
- Row: `TextInput` (size `md`, `startIcon={Search}`, `hasClear`, autofocus on open, placeholder "Search titles, topics, descriptions") filling the width, and a ghost "Cancel" `Button` that closes the sheet.
- Empty query: section "Recently viewed" (up to 6 rows) then "Shelves" (one row per category with count). Section titles use `Text type="supporting"` uppercase eyebrow styling already in `.pick-eyebrow`.
- With a query: results from `searchBooks`, grouped by category with the same section title style, up to 24 rows. Each row is a 44px-minimum tappable row: 36px cover, title (1 line), `topic leaf · PDF` (1 line). Reuse the `PaletteRow` markup, extracted into its own component.
- Tapping a row navigates and closes the sheet. No keyboard hint footer.

Desktop keeps `CommandPalette` exactly as it is. Split `SearchPalette.tsx` so the search source and the row component are shared and only the container differs.

## Home (phone)

Section order, top to bottom. Target total height ≈ 4–5 screens.

1. Greeting. `Heading level={1} type="heading-1"` (not display), subtitle `Text type="body" color="secondary"`. Top padding `spacing-5`.
2. Today's pick: a horizontal `ClickableCard` (whole card goes to the book), ambient backdrop kept. Left: cover at 96px wide. Right, `VStack gap={1}`: eyebrow "Today's pick", title `Heading level={2} type="heading-3" maxLines={3}`, `Text type="supporting"` with `category · topic leaf`. No excerpt and no buttons on phone. Card padding `spacing-4`. Target height ≤ 180px.
3. Browse by topic: single-line horizontally scrolling chip row (`Token size="sm"`), 12 topics, then "All topics" ghost button at the end. Add a fade mask on the right edge using a CSS mask with tokens (`mask-image: linear-gradient(...)`). Remove `scrollbar-width: thin` padding tricks; hide the scrollbar on touch.
4. Jump back in / Start here: no card, no numbers. A plain list of up to 3 rows with `spacing-3` row padding and `color-border` dividers, cover 40px, title 1 line, `category · topic leaf` 1 line. Heading `level={2}` above with the section title.
5. Shelves: one block per category, this is the only category navigation on phone. Delete the "Your shelves" tile grid on phone (keep it on tablet and desktop). Each block:
   - Head row: `Heading level={2} type="heading-3"` with the category name, `Text type="supporting"` count, and a chevron-right `IconButton` on the far right that goes to `browsePath({ category })`. Tapping the heading text also navigates. Drop the topic description line on phone.
   - Carousel of the first 12 books with `--shelf-cover-width: 104px` on phone so 3.5 covers show with a peek. `BookCard` title 2 lines, `label` text, topic 1 line.
6. Surprise me: full-width secondary button, `spacing-8` above.

Section gap: `VStack gap={8}` on phone instead of 10.

## Browse (phone)

Chrome, top to bottom, sticky as a group below the top bar (background `color-background-body` at 92% with blur, same recipe as `.nav`):

1. Category chips: single-line scrolling row of `Token size="sm"`: "All" first, then each category with its count. Selected chip stays `color="blue"`; keep the existing auto-scroll-into-view effect. This replaces the breadcrumb and the Topics button.
2. Topic chips (only when a category is selected and it has topics): second single-line row. "All" first, then the category's topics flattened depth-first. Children render as `Parent / Child` leaf labels. Selected topic chip is `color="blue"`. Tapping navigates with `scopeHref`.
3. Toolbar row (`HStack gap={2}`): `TextInput` size `md` filling the width (placeholder "Filter titles…", `hasClear`), then a `Filter` `IconButton` (lucide `SlidersHorizontal`) size `md` variant `secondary`. When any of format or sort differs from default, show a `Badge` dot or count on the button.

Below the sticky group, non-sticky: one line `HStack`: `Heading level={1} type="heading-2"` with the scope name ("All books", category or topic leaf) and the count as `Text type="supporting"`. This is the only place the name appears besides the chip.

Filter sheet (`BottomSheet height="hug"`), opened by the Filter button:
- "Format" as `SegmentedControl` with All + available formats (full width).
- "Sort" as a `RadioGroup` or `Selector` with the three sort options; disabled with the existing message while a query is active.
- "View" as the grid/list `SegmentedControl`.
- Footer row: ghost "Reset" (clears format, sort, query) and primary "Done" that closes the sheet. Look up `RadioGroup` and `SegmentedControl` props before use.

Remove the `Topics` button and the `TreeList` topics sheet on phone and tablet.

Results:
- Grid: `Grid columns={{ minWidth: 104 }} gap={3} rowGap={5}` on phone (3 columns on a 390px viewport), `minWidth: 132` on tablet. `BookCard` text: title `label` 2 lines, subline 1 line.
- List: keep `BookRow`. Row min height 64px. Keep the download icon button.
- Replace `Pagination` on phone and tablet with a centered secondary "Load more" button plus `Text type="supporting"` "Showing 24 of 150". `page` in the URL now means "pages loaded": render `filtered.slice(0, page * PAGE_SIZE)`; the button sets `page + 1` without scrolling to top. Desktop keeps `Pagination` and its current slicing.
- Empty state unchanged.

## Book (phone)

- Remove the ghost "Back to X" button; the top bar back chevron replaces it.
- Hero: no bordered card. The ambient backdrop bleeds to the viewport edges (negative inline margin equal to the page padding, or render the hero outside `PageFrame`). Content centered: cover 150px wide, then `Text type="supporting"` with linked `Category / Topic` on one wrapping line, `Heading level={1} type="heading-1" textWrap="balance"`, then a row of `Badge` chips for formats (PDF, EPUB, DOCX). Hero bottom padding `spacing-6`.
- About: `Heading level={2}` + description as today. If the description is longer than 8 lines, clamp with `Text maxLines={8}` and a ghost "Read more" button that removes the clamp.
- Related: reuse `Shelf` with `headingLevel={2}`, title "More in {topic leaf}" (or category), the 5 related books, `href` to the scope and `linkLabel="View all"`. No `RecentList` card and no dangling link on phone.
- Sticky bottom action bar replaces the tab bar on this route: fixed, 56px + safe area, same translucent recipe as `.tabbar`, padding `spacing-3` inline. Contents (`HStack gap={2}`): `DownloadAction` as primary filling the remaining width, "Read online" as `IconButton` variant `secondary` with the `Eye` icon and a tooltip (only when a PDF exists), Share as `IconButton` variant `secondary`. Add bottom padding to the page equal to the bar height so content is not hidden.
- Desktop is unchanged, including the back button, the card hero, the two-column body and the side list.

## Global phone polish

- All tappable rows and buttons ≥ 44px. Controls use size `md`, never `lg`, on phone.
- `.page-frame` phone padding: `spacing-4` top, `spacing-4` inline, bottom = `spacing-8 + tabbar height + safe area`.
- `--shelf-cover-width`: 104px phone, 132px tablet, 150px desktop.
- `--cover-shadow` on phone: `0 1px 2px rgba(0,0,0,.12), 0 4px 10px -6px rgba(0,0,0,.3)` (lighter).
- Display headings are used only for the greeting on desktop. On phone, no `display-*` types anywhere.
- Scrollable chip rows: `overscroll-behavior-x: contain`, `scrollbar-width: none`, `-webkit-overflow-scrolling: touch`, snap off.
- Keep `prefers-reduced-motion` rules and extend them to any new transition.
- Dark mode: verify every new surface uses tokens; no hardcoded colors except the shadow rgba values already in use.

## Acceptance

Run from `web/`:
1. `npm run build` passes (type check + build).
2. From repo root `python scripts/cli.py smoke --base-dir .` passes.
3. Screenshots at 390×844 (iPhone 13 preset in Playwright) of `/home`, `/browse`, `/browse?category=Computer%20Science%20Fundamentals`, a `/book/:id`, the open search sheet and the open filter sheet, in light and dark mode. Chrome above the first cover must be ≤ 250px on Home and Browse. Home full-page height under 5 000px with the current 150 books.
4. Desktop screenshot at 1440×900 of `/home` and `/browse` shows no change from the current build.
6. Do not commit; report the diff summary and screenshot paths back.

## Reference: current component map

| File | Role |
| --- | --- |
| `web/src/components/Shell.tsx` | AppShell on desktop, header + tab bar on mobile, search palette host |
| `web/src/components/SearchPalette.tsx` | CommandPalette wrapper and row renderer |
| `web/src/pages/Home.tsx` | Greeting, PickCard, RecentList, CategoryTile grid, topic chips, Shelf per category |
| `web/src/pages/Browse.tsx` | Chip row, breadcrumbs, toolbar, grid/list, pagination, topics BottomSheet |
| `web/src/pages/BookDetail.tsx` | Back button, hero card, about, related RecentList |
| `web/src/components/{BookCard,BookRow,Shelf,PickCard,RecentList,CategoryTile,BookCover}.tsx` | Building blocks |
| `web/src/styles.css` | All custom CSS, token-based |
