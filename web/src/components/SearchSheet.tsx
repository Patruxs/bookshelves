import { BottomSheet } from "@astryxdesign/core/BottomSheet";
import { Button } from "@astryxdesign/core/Button";
import { HStack } from "@astryxdesign/core/HStack";
import { StackItem } from "@astryxdesign/core/Stack";
import { Text } from "@astryxdesign/core/Text";
import { TextInput } from "@astryxdesign/core/TextInput";
import { VStack } from "@astryxdesign/core/VStack";
import { Search } from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { searchItemHref, useLibrarySearch, type SearchItem } from "../lib/librarySearch";
import { RouterLink } from "./RouterLink";
import { SearchResultRow } from "./SearchResultRow";

interface SearchSheetProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}

interface SearchSection {
  title: string;
  items: SearchItem[];
}

function sectionsOf(items: SearchItem[]): SearchSection[] {
  const sections: SearchSection[] = [];
  for (const item of items) {
    const title = item.auxiliaryData?.group ?? "";
    const last = sections[sections.length - 1];
    if (last && last.title === title) last.items.push(item);
    else sections.push({ title, items: [item] });
  }
  return sections;
}

export function SearchSheet({ isOpen, onOpenChange }: SearchSheetProps) {
  const { search } = useLibrarySearch("Shelves");
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const inputRef = useRef<HTMLInputElement>(null);
  const sections = useMemo(() => sectionsOf(search(deferredQuery)), [search, deferredQuery]);
  const close = () => onOpenChange(false);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
    else setQuery("");
  }, [isOpen]);

  return (
    <BottomSheet isOpen={isOpen} onOpenChange={onOpenChange} label="Search the library" height="tall">
      <VStack gap={5} className="search-sheet">
        <HStack gap={2} vAlign="center" className="search-sheet-bar">
          <StackItem size="fill">
            <TextInput
              ref={inputRef}
              label="Search the library"
              isLabelHidden
              size="md"
              startIcon={Search}
              placeholder="Search titles, topics, descriptions"
              value={query}
              onChange={setQuery}
              hasClear
              width="100%"
            />
          </StackItem>
          <Button label="Cancel" variant="ghost" onClick={close} />
        </HStack>
        {sections.length ? (
          sections.map(section => (
            <VStack key={section.title} gap={1}>
              <span className="pick-eyebrow">
                <Text type="supporting">{section.title}</Text>
              </span>
              <ul className="search-sheet-list">
                {section.items.map(item => (
                  <li key={item.id}>
                    <RouterLink href={searchItemHref(item.id) ?? undefined} className="search-sheet-row" onClick={close}>
                      <SearchResultRow item={item} />
                    </RouterLink>
                  </li>
                ))}
              </ul>
            </VStack>
          ))
        ) : (
          <Text type="body" color="secondary">
            {deferredQuery.trim() ? "No books match" : "Type to search the library"}
          </Text>
        )}
      </VStack>
    </BottomSheet>
  );
}
