import { Bookmark, Play, Edit2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApp } from "@/contexts/AppContext";
import { useNavigate } from "react-router-dom";

export default function SavedSearchesPage() {
  const { savedSearches, deleteSavedSearch } = useApp();
  const navigate = useNavigate();

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-foreground">Saved Searches</h1>
      </div>

      {savedSearches.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
          <Bookmark className="w-12 h-12 text-muted-foreground/30 mb-4" />
          <h2 className="text-lg font-medium text-foreground mb-1">No saved searches</h2>
          <p className="text-sm text-muted-foreground mb-4">Save a search from the Search page to reuse it later.</p>
          <Button variant="outline" size="sm" onClick={() => navigate("/search")}>Go to Search</Button>
        </div>
      ) : (
        <div className="space-y-2">
          {savedSearches.map(ss => (
            <div key={ss.id} className="bg-card border border-border rounded-xl p-4 flex items-center gap-4 hover:border-primary/30 transition-colors">
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-medium text-foreground">{ss.name}</h3>
                <p className="text-xs text-muted-foreground truncate mt-0.5">"{ss.query}"</p>
                <p className="text-[10px] text-muted-foreground mt-1">Last used: {ss.lastUsed}</p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Button variant="outline" size="sm" className="h-7 text-xs gap-1" onClick={() => navigate("/search")}>
                  <Play className="w-3 h-3" /> Run
                </Button>
                <Button variant="ghost" size="icon" className="h-7 w-7">
                  <Edit2 className="w-3 h-3" />
                </Button>
                <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => deleteSavedSearch(ss.id)}>
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
