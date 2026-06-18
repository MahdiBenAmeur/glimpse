import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Edit2, Trash2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApp } from "@/contexts/useApp";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { getCollectionImages, pickCollectionImages } from "@/lib/api";
import type { ImageResult } from "@/types/app";
import { toast } from "sonner";

export default function CollectionDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { collections, deleteCollection, refreshData, settings } = useApp();
  const collection = collections.find(c => c.id === id);
  const [collectionImages, setCollectionImages] = useState<ImageResult[]>([]);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const loadCollectionImages = async (collectionId: string) => {
    const images = await getCollectionImages(collectionId);
    setCollectionImages(images);
  };

  useEffect(() => {
    if (!id) return;
    void loadCollectionImages(id).catch(() => setCollectionImages([]));
  }, [id]);

  const handleAddPhotos = async () => {
    if (!id) return;
    try {
      const result = await pickCollectionImages(id);
      await refreshData();
      await loadCollectionImages(id);
      toast.success(`${result.addedCount} photo${result.addedCount === 1 ? "" : "s"} added to the collection.`);
      if (result.autoIndexedCount > 0) {
        toast.info(`${result.autoIndexedCount} selected photo${result.autoIndexedCount === 1 ? "" : "s"} were indexed automatically before being added.`);
      }
      if (result.skippedPaths.length > 0) {
        toast.info(`${result.skippedPaths.length} selected photo${result.skippedPaths.length === 1 ? "" : "s"} could not be added.`);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not add photos to the collection.";
      toast.error(message);
    }
  };

  const beginRename = () => {
    if (!collection) return;
    setRenameValue(collection.name);
    setIsRenaming(true);
  };

  const commitRename = async () => {
    const next = renameValue.trim();
    if (!collection || !next || next === collection.name) {
      setIsRenaming(false);
      return;
    }
    try {
      const response = await fetch(`/api/collections/${collection.id}`, {
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
      const message = error instanceof Error ? error.message : "Could not rename the collection.";
      toast.error(message);
    } finally {
      setIsRenaming(false);
    }
  };

  if (!collection) {
    return (
      <div className="p-6 text-center">
        <p className="text-muted-foreground">Collection not found.</p>
        <Button variant="ghost" onClick={() => navigate("/collections")} className="mt-4">Back</Button>
      </div>
    );
  }

  const handleDelete = async () => {
    setConfirmDeleteOpen(false);
    const deleted = await deleteCollection(collection.id);
    if (deleted) {
      navigate("/collections");
    }
  };

  const requiresConfirmation = settings.confirmDestructiveActions;

  return (
    <div className="p-6">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 text-xs" onClick={() => navigate("/collections")}>
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Collections
      </Button>

      <div className="flex items-center justify-between mb-6">
        <div>
          {isRenaming ? (
            <div className="flex items-center gap-2">
              <Input
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void commitRename();
                  if (e.key === "Escape") setIsRenaming(false);
                }}
                className="h-8 text-sm w-64"
                autoFocus
              />
              <Button size="sm" className="h-8 text-xs" onClick={() => void commitRename()}>Save</Button>
              <Button variant="ghost" size="sm" className="h-8 text-xs" onClick={() => setIsRenaming(false)}>Cancel</Button>
            </div>
          ) : (
            <h1 className="text-xl font-semibold text-foreground">{collection.name}</h1>
          )}
          {collection.description && <p className="text-xs text-muted-foreground mt-0.5">{collection.description}</p>}
          <p className="text-[10px] text-muted-foreground mt-1">{collection.imageCount} items</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="text-xs h-8 gap-1" onClick={() => void handleAddPhotos()}>
            <Plus className="w-3 h-3" /> Add photos
          </Button>
          <Button variant="outline" size="sm" className="text-xs h-8 gap-1" onClick={beginRename} disabled={isRenaming}>
            <Edit2 className="w-3 h-3" /> Rename
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-xs h-8 gap-1 text-destructive hover:text-destructive"
            onClick={() => {
              if (requiresConfirmation) {
                setConfirmDeleteOpen(true);
              } else {
                void handleDelete();
              }
            }}
          >
            <Trash2 className="w-3 h-3" /> Delete
          </Button>
        </div>
      </div>

      <ResultsGrid images={collectionImages} />

      {requiresConfirmation && (
        <div
          aria-hidden={!confirmDeleteOpen}
          className={`fixed inset-0 z-50 flex items-center justify-center bg-black/50 transition-opacity ${
            confirmDeleteOpen ? "opacity-100" : "pointer-events-none opacity-0"
          }`}
          onClick={() => setConfirmDeleteOpen(false)}
        >
          <div
            className="w-full max-w-sm rounded-lg border border-border bg-card p-5 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-sm font-semibold text-foreground">Delete collection</h2>
            <p className="mt-2 text-xs text-muted-foreground">
              Delete "{collection.name}"? Photos inside stay in your library.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setConfirmDeleteOpen(false)}>Cancel</Button>
              <Button variant="destructive" size="sm" onClick={() => void handleDelete()}>
                Delete collection
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
