import { useEffect, useMemo, useRef, useState } from "react";
import { Search as SearchIcon, SlidersHorizontal, X, RefreshCw, Sparkles, ImageUp, BookmarkPlus } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useApp } from "@/contexts/AppContext";
import { EXAMPLE_SEARCHES } from "@/data/exampleSearches";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { AdvancedFiltersDrawer } from "@/components/search/AdvancedFiltersDrawer";

type SearchFilterState = {
  folders: string[];
  dateRange: "any" | "today" | "last-7-days" | "last-30-days" | "this-year";
  facePresence: "any" | "faces" | "no-faces";
  people: Array<{ id: number; preference: "must_include" | "prefer" | "exclude" }>;
  facePhotoPath: string | null;
};

type SearchRouteState = {
  savedSearch?: {
    id?: string;
    name: string;
    query: string;
    filters?: Record<string, unknown>;
  };
  similarImageId?: string | number;
  similarSourceLabel?: string;
} | null;

type ActiveFilterChip = {
  key: string;
  label: string;
};

function getPathLabel(path: string) {
  const normalized = path.replace(/\\/g, "/");
  const parts = normalized.split("/").filter(Boolean);
  return parts.slice(-2).join("/") || normalized;
}

function normalizeSearchFilters(filters?: Record<string, unknown>): SearchFilterState {
  const rawPeople = Array.isArray(filters?.people) ? filters.people : [];
  const people = rawPeople
    .map((person) => {
      if (!person || typeof person !== "object") return null;
      const candidate = person as { id?: unknown; preference?: unknown };
      const id = Number(candidate.id);
      if (!Number.isFinite(id)) return null;
      const preference = candidate.preference === "exclude" || candidate.preference === "prefer" ? candidate.preference : "must_include";
      return { id, preference };
    })
    .filter((value): value is { id: number; preference: "must_include" | "prefer" | "exclude" } => value !== null);

  return {
    folders: Array.isArray(filters?.folders) ? filters.folders.map(String) : [],
    dateRange:
      filters?.dateRange === "today" ||
      filters?.dateRange === "last-7-days" ||
      filters?.dateRange === "last-30-days" ||
      filters?.dateRange === "this-year"
        ? filters.dateRange
        : "any",
    facePresence: filters?.facePresence === "faces" || filters?.facePresence === "no-faces" ? filters.facePresence : "any",
    people,
    facePhotoPath: typeof filters?.facePhotoPath === "string" ? filters.facePhotoPath : null,
  };
}

function buildFilterChips(
  filters: SearchFilterState,
  peopleLookup: Map<number, string>,
): ActiveFilterChip[] {
  const chips: ActiveFilterChip[] = [];

  filters.folders.forEach((folder) => {
    chips.push({
      key: `folder:${folder}`,
      label: `Folder: ${getPathLabel(folder)}`,
    });
  });

  if (filters.dateRange !== "any") {
    chips.push({ key: "dateRange", label: `Date: ${filters.dateRange}` });
  }

  if (filters.facePresence !== "any") {
    chips.push({
      key: "facePresence",
      label: filters.facePresence === "faces" ? "Contains faces" : "No faces",
    });
  }

  filters.people.forEach((person) => {
    const name = peopleLookup.get(person.id) ?? `Person ${person.id}`;
    const prefix = person.preference === "exclude" ? "Exclude" : person.preference === "prefer" ? "Prefer" : "Must include";
    chips.push({
      key: `person:${person.id}:${person.preference}`,
      label: `${prefix}: ${name}`,
    });
  });

  if (filters.facePhotoPath) {
    chips.push({
      key: "facePhotoPath",
      label: "Face photo search",
    });
  }

  return chips;
}

export default function SearchPage() {
  const { images, activeModel, lastIndexedTime, people, searchImages, searchSimilarImages, searchImagesByFile, startIndexing, saveSearch } = useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [query, setQuery] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [searchFilterRequest, setSearchFilterRequest] = useState<SearchFilterState>({
    folders: [],
    dateRange: "any",
    facePresence: "any",
    people: [],
    facePhotoPath: null,
  });
  const [isDraggingImage, setIsDraggingImage] = useState(false);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveName, setSaveName] = useState("");

  const peopleLookup = useMemo(
    () => new Map(people.filter((person) => person.name).map((person) => [Number(person.id), person.name as string])),
    [people],
  );
  const activeFilterChips = useMemo(
    () => buildFilterChips(searchFilterRequest, peopleLookup),
    [peopleLookup, searchFilterRequest],
  );

  const indexFresh = lastIndexedTime
    ? (Date.now() - new Date(lastIndexedTime).getTime()) < 86400000
    : false;

  const handleSearch = async () => {
    if (!query.trim() && !searchFilterRequest.facePhotoPath) return;
    setHasSearched(true);
    setIsSearching(true);
    try {
      await searchImages(query, searchFilterRequest);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSearchByFile = async (file: File) => {
    setHasSearched(true);
    setIsSearching(true);
    setQuery(`Similar to ${file.name}`);
    setSearchFilterRequest({
      folders: [],
      dateRange: "any",
      facePresence: "any",
      people: [],
      facePhotoPath: null,
    });
    try {
      await searchImagesByFile(file);
    } finally {
      setIsSearching(false);
    }
  };

  const removeFilter = (filterKey: string) => {
    setSearchFilterRequest((prev) => {
      if (filterKey.startsWith("folder:")) {
        const path = filterKey.slice("folder:".length);
        return {
          ...prev,
          folders: prev.folders.filter((folder) => folder !== path),
        };
      }

      if (filterKey === "dateRange") {
        return { ...prev, dateRange: "any" };
      }

      if (filterKey === "facePresence") {
        return { ...prev, facePresence: "any" };
      }

      if (filterKey === "facePhotoPath") {
        return { ...prev, facePhotoPath: null };
      }

      if (filterKey.startsWith("person:")) {
        const [, personId, preference] = filterKey.split(":");
        const id = Number(personId);
        return {
          ...prev,
          people: prev.people.filter((person) => !(person.id === id && person.preference === preference)),
        };
      }

      return prev;
    });
  };

  const clearFilters = () => {
    setSearchFilterRequest({
      folders: [],
      dateRange: "any",
      facePresence: "any",
      people: [],
      facePhotoPath: null,
    });
  };

  const handleSaveCurrentSearch = async () => {
    if (!saveName.trim() || (!query.trim() && !searchFilterRequest.facePhotoPath)) return;
    await saveSearch(saveName.trim(), query.trim(), searchFilterRequest as Record<string, unknown>);
    setSaveDialogOpen(false);
    setSaveName("");
  };

  useEffect(() => {
    const state = location.state as SearchRouteState;
    if (!state) return;

    let cancelled = false;
    const run = async () => {
      if (state.savedSearch) {
        const nextFilters = normalizeSearchFilters(state.savedSearch.filters);
        setQuery(state.savedSearch.query || "");
        setSearchFilterRequest(nextFilters);
        setHasSearched(true);
        setIsSearching(true);
        try {
          await searchImages(state.savedSearch.query || "", nextFilters);
        } finally {
          if (!cancelled) {
            setIsSearching(false);
            navigate(location.pathname, { replace: true, state: null });
          }
        }
        return;
      }

      if (state.similarImageId !== undefined) {
        setQuery(`Similar to ${state.similarSourceLabel ?? "image"}`);
        setHasSearched(true);
        setIsSearching(true);
        try {
          await searchSimilarImages(state.similarImageId);
        } finally {
          if (!cancelled) {
            setIsSearching(false);
            navigate(location.pathname, { replace: true, state: null });
          }
        }
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [location.pathname, location.state, navigate, peopleLookup, searchImages, searchSimilarImages]);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 pt-5 pb-4 flex items-center justify-between shrink-0">
        <h1 className="text-xl font-semibold text-foreground">Search</h1>
        <div className="flex items-center gap-2">
          {activeModel && (
            <Badge variant="outline" className="text-[11px] font-normal">
              {activeModel.name}
            </Badge>
          )}
          <Badge
            variant={indexFresh ? "secondary" : "destructive"}
            className="text-[11px] font-normal"
          >
            {indexFresh ? "Index up to date" : "Index outdated"}
          </Badge>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 text-xs gap-1.5"
            onClick={() => void startIndexing({ resetIndex: true })}
          >
            <RefreshCw className="w-3 h-3" /> Reindex
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs gap-1.5"
            onClick={() => setSaveDialogOpen(true)}
            disabled={!query.trim() && !searchFilterRequest.facePhotoPath}
          >
            <BookmarkPlus className="w-3 h-3" /> Save search
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs gap-1.5"
            onClick={() => setFiltersOpen(true)}
          >
            <SlidersHorizontal className="w-3 h-3" /> Filters
          </Button>
        </div>
      </div>

      {/* Search bar */}
      <div className="px-6 pb-3 shrink-0">
        <div className="relative max-w-2xl mx-auto">
          <SearchIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Describe the image you’re looking..."
            className="pl-10 pr-20 h-11 bg-card border-border text-sm"
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
            {query && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => {
                  setQuery("");
                  setHasSearched(false);
                }}
              >
                <X className="w-3.5 h-3.5" />
              </Button>
            )}
            <Button
              size="sm"
              className="h-7 text-xs px-3"
              onClick={handleSearch}
            >
              Search
            </Button>
          </div>
        </div>
        <div
          className={`max-w-2xl mx-auto mt-3 rounded-xl border border-dashed px-4 py-3 text-center transition-colors ${
            isDraggingImage
              ? "border-primary bg-accent"
              : "border-border bg-card"
          }`}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDraggingImage(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setIsDraggingImage(false);
          }}
          onDrop={(event) => {
            event.preventDefault();
            setIsDraggingImage(false);
            const file = event.dataTransfer.files?.[0];
            if (file) {
              void handleSearchByFile(file);
            }
          }}
        >
          <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <ImageUp className="w-3.5 h-3.5" />
            <span>Drop an image here to find similar photos</span>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={() => fileInputRef.current?.click()}
            >
              Choose image
            </Button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                void handleSearchByFile(file);
              }
              event.currentTarget.value = "";
            }}
          />
        </div>
      </div>

      {/* Active filters */}
      {activeFilterChips.length > 0 && (
        <div className="px-6 pb-3 flex items-center gap-2 flex-wrap shrink-0">
          {activeFilterChips.map((filterChip) => (
            <Badge key={filterChip.key} variant="secondary" className="text-xs gap-1 pr-1">
              {filterChip.label}
              <button
                onClick={() => removeFilter(filterChip.key)}
                className="ml-0.5 hover:bg-muted rounded-full p-0.5"
              >
                <X className="w-2.5 h-2.5" />
              </button>
            </Badge>
          ))}
          <button
            onClick={clearFilters}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Clear all
          </button>
        </div>
      )}

      {/* Results */}
      <div className="flex-1 overflow-auto px-6 pb-6">
        {isSearching ? (
          <SkeletonGrid />
        ) : !hasSearched ? (
          <EmptySearchState
            onExampleClick={(q) => {
              setQuery(q);
            }}
          />
        ) : images.length === 0 ? (
          <NoResultsState onClearFilters={clearFilters} />
        ) : (
          <ResultsGrid images={images} />
        )}
      </div>

      <AdvancedFiltersDrawer
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        currentFilters={searchFilterRequest}
        onApply={(filters) => {
          setSearchFilterRequest({
            folders: filters.folders,
            dateRange: filters.dateRange,
            facePresence: filters.facePresence,
            people: filters.people.map((person) => ({
              id: person.id,
              preference: person.preference,
            })),
            facePhotoPath: filters.facePhotoPath,
          });
          setFiltersOpen(false);
        }}
      />

      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-base">Save Search</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Name</Label>
              <Input
                value={saveName}
                onChange={(event) => setSaveName(event.target.value)}
                className="mt-1 h-9 text-sm"
                placeholder="My search"
              />
            </div>
            <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              Query: {query || "No query"}
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSaveDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={() => void handleSaveCurrentSearch()}
              disabled={!saveName.trim() || (!query.trim() && !searchFilterRequest.facePhotoPath)}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function EmptySearchState({ onExampleClick }: { onExampleClick: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-center">
      <div className="w-14 h-14 rounded-2xl bg-accent flex items-center justify-center mb-4">
        <Sparkles className="w-6 h-6 text-accent-foreground" />
      </div>
      <h2 className="text-lg font-medium text-foreground mb-1">Describe what you're looking for</h2>
      <p className="text-sm text-muted-foreground mb-6 max-w-sm">
        Search your photo library using natural language. Try one of these:
      </p>
      <div className="flex flex-wrap gap-2 justify-center max-w-md">
        {EXAMPLE_SEARCHES.slice(0, 4).map(ex => (
          <button
            key={ex}
            onClick={() => onExampleClick(ex)}
            className="px-3 py-1.5 rounded-full bg-card border border-border text-xs text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
      {Array.from({ length: 12 }).map((_, i) => (
        <div key={i} className="animate-shimmer rounded-lg" style={{ height: 180 + (i % 3) * 40 }} />
      ))}
    </div>
  );
}

function NoResultsState({ onClearFilters }: { onClearFilters: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-center">
      <SearchIcon className="w-10 h-10 text-muted-foreground/40 mb-4" />
      <h2 className="text-lg font-medium text-foreground mb-1">No matches found</h2>
      <p className="text-sm text-muted-foreground mb-4">Try adjusting your search or removing some filters.</p>
      <Button variant="outline" size="sm" onClick={onClearFilters}>Clear filters</Button>
    </div>
  );
}
