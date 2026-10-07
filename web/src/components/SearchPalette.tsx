import { CommandPalette, CommandPaletteInput } from "@astryxdesign/core/CommandPalette";
import type { SearchSource } from "@astryxdesign/core/Typeahead";
import { useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { searchItemHref, useLibrarySearch, type SearchItem } from "../lib/librarySearch";
import { SearchResultRow } from "./SearchResultRow";

interface SearchPaletteProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}

export function SearchPalette({ isOpen, onOpenChange }: SearchPaletteProps) {
  const { bootstrap, search } = useLibrarySearch("Browse");
  const navigate = useNavigate();
  const source = useMemo<SearchSource<SearchItem>>(() => ({ bootstrap, search }), [bootstrap, search]);

  const onValueChange = useCallback(
    (value: string) => {
      const href = searchItemHref(value);
      if (href) navigate(href);
    },
    [navigate]
  );

  return (
    <CommandPalette<SearchItem>
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      searchSource={source}
      label="Search the library"
      value=""
      onValueChange={onValueChange}
      input={<CommandPaletteInput placeholder="Search titles, topics, descriptions" label="Search the library" />}
      emptyBootstrapText="Type to search the library"
      emptySearchText="No books match"
      renderItem={item => <SearchResultRow item={item} />}
    />
  );
}
