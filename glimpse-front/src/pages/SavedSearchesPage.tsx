import { useState } from "react";
import { Bookmark, Play, Edit2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApp } from "@/contexts/useApp";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

export default function SavedSearchesPage() {
  const { savedSearches, deleteSavedSearch, settings, refreshData } = useApp();
  const navigate = useNavigate();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const beginRename = (id: string, currentName: string) => {
    setEditingId(id);
    setEditName(currentName);
  };

  const commitRename = async (id: string) => {
    const next = editName.trim();
    if (!next) {
      setEditingId(null);
      return;
    }
    try {
      const response = await fetch(`/api/saved-searches/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: next }),
      });
      if (!response.ok) {
        throw new Error(`Rename failed (${response.status})`);
      }
      await refreshData();
      toast.success(`Renamed to "${next}".`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not rename the saved search.";
      toast.error(message);
    } finally {
      setEditingId(null);
    }
  };

  const confirmDelete = confirmDeleteId
    ? savedSearches.find((search) => search.id === confirmDeleteId)
    : null;

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
                {editingId === ss.id ? (
                  <div className="flex items-center gap-2">
                    <Input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void commitRename(ss.id);
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      className="h-7 text-xs w-56"
                      autoFocus
                    />
                    <Button size="sm" className="h-7 text-xs" onClick={() => void commitRename(ss.id)}>Save</Button>
                    <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setEditingId(null)}>Cancel</Button>
                  </div>
                ) : (
                  <h3 className="text-sm font-medium text-foreground">{ss.name}</h3>
                )}
                <p className="text-xs text-muted-foreground truncate mt-0.5">"{ss.query}"</p>
                <p className="text-[10px] text-muted-foreground mt-1">Last used: {ss.lastUsed}</p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs gap-1"
                  onClick={() => navigate("/search", { state: { savedSearch: ss } })}
                >
                  <Play className="w-3 h-3" /> Run
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => beginRename(ss.id, ss.name)}
                  disabled={editingId === ss.id}
                >
                  <Edit2 className="w-3 h-3" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive hover:text-destructive"
                  onClick={() => {
                    if (settings.confirmDestructiveActions) {
                      setConfirmDeleteId(ss.id);
                    } else {
                      void deleteSavedSearch(ss.id);
                    }
                  }}
                >
                  <Trash2 className="w-3 h-3" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {settings.confirmDestructiveActions && (
        <div
          aria-hidden={!confirmDelete}
          className={`fixed inset-0 z-50 flex items-center justify-center bg-black/50 transition-opacity ${
            confirmDelete ? "opacity-100" : "pointer-events-none opacity-0"
          }`}
          onClick={() => setConfirmDeleteId(null)}
        >
          <div
            className="w-full max-w-sm rounded-lg border border-border bg-card p-5 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-sm font-semibold text-foreground">Delete saved search</h2>
            <p className="mt-2 text-xs text-muted-foreground">
              Delete "{confirmDelete?.name}"? This cannot be undone.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setConfirmDeleteId(null)}>Cancel</Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => {
                  if (confirmDeleteId) {
                    void deleteSavedSearch(confirmDeleteId);
                    setConfirmDeleteId(null);
                  }
                }}
              >
                Delete saved search
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
