import { useState, useMemo } from "react";
import { Search as SearchIcon, SlidersHorizontal, X, RefreshCw, Sparkles } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useApp } from "@/contexts/AppContext";
import { EXAMPLE_SEARCHES } from "@/data/mockData";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { AdvancedFiltersDrawer } from "@/components/search/AdvancedFiltersDrawer";

export default function SearchPage() {
  const { images, activeModel, lastIndexedTime, indexingStatus } = useApp();
  const [query, setQuery] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [activeFilters, setActiveFilters] = useState<string[]>([]);

  const indexFresh = lastIndexedTime
    ? (Date.now() - new Date(lastIndexedTime).getTime()) < 86400000
    : false;

  const results = useMemo(() => {
    if (!hasSearched) return [];
    if (!query.trim()) return images;
    return images.filter((_, i) => i % 2 === 0 || query.length < 5);
  }, [hasSearched, query, images]);

  const handleSearch = () => {
    if (!query.trim()) return;
    setIsSearching(true);
    setHasSearched(true);
    setTimeout(() => setIsSearching(false), 800);
  };

  const removeFilter = (f: string) => setActiveFilters(prev => prev.filter(x => x !== f));

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
          <Badge variant={indexFresh ? "secondary" : "destructive"} className="text-[11px] font-normal">
            {indexFresh ? "Index up to date" : "Index outdated"}
          </Badge>
          <Button variant="ghost" size="sm" className="h-8 text-xs gap-1.5">
            <RefreshCw className="w-3 h-3" /> Reindex
          </Button>
          <Button variant="outline" size="sm" className="h-8 text-xs gap-1.5" onClick={() => setFiltersOpen(true)}>
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
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSearch()}
            placeholder="sunset on the beach with Lina"
            className="pl-10 pr-20 h-11 bg-card border-border text-sm"
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
            {query && (
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => { setQuery(""); setHasSearched(false); }}>
                <X className="w-3.5 h-3.5" />
              </Button>
            )}
            <Button size="sm" className="h-7 text-xs px-3" onClick={handleSearch}>Search</Button>
          </div>
        </div>
      </div>

      {/* Active filters */}
      {activeFilters.length > 0 && (
        <div className="px-6 pb-3 flex items-center gap-2 flex-wrap shrink-0">
          {activeFilters.map(f => (
            <Badge key={f} variant="secondary" className="text-xs gap-1 pr-1">
              {f}
              <button onClick={() => removeFilter(f)} className="ml-0.5 hover:bg-muted rounded-full p-0.5">
                <X className="w-2.5 h-2.5" />
              </button>
            </Badge>
          ))}
          <button onClick={() => setActiveFilters([])} className="text-xs text-muted-foreground hover:text-foreground">
            Clear all
          </button>
        </div>
      )}

      {/* Results */}
      <div className="flex-1 overflow-auto px-6 pb-6">
        {!hasSearched ? (
          <EmptySearchState onExampleClick={(q) => { setQuery(q); }} />
        ) : isSearching ? (
          <SkeletonGrid />
        ) : results.length === 0 ? (
          <NoResultsState onClearFilters={() => setActiveFilters([])} />
        ) : (
          <ResultsGrid images={results} />
        )}
      </div>

      <AdvancedFiltersDrawer
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        onApply={(filters) => { setActiveFilters(filters); setFiltersOpen(false); }}
      />
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
