import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Edit2, Trash2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApp } from "@/contexts/useApp";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { getCollectionImages, pickCollectionImages } from "@/lib/api";
import type { ImageResult } from "@/types/app";
import { toast } from "sonner";

export default function CollectionDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { collections, deleteCollection, refreshData } = useApp();
  const collection = collections.find(c => c.id === id);
  const [collectionImages, setCollectionImages] = useState<ImageResult[]>([]);

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

  if (!collection) {
    return (
      <div className="p-6 text-center">
        <p className="text-muted-foreground">Collection not found.</p>
        <Button variant="ghost" onClick={() => navigate("/collections")} className="mt-4">Back</Button>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 text-xs" onClick={() => navigate("/collections")}>
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Collections
      </Button>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-foreground">{collection.name}</h1>
          {collection.description && <p className="text-xs text-muted-foreground mt-0.5">{collection.description}</p>}
          <p className="text-[10px] text-muted-foreground mt-1">{collection.imageCount} items</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="text-xs h-8 gap-1" onClick={() => void handleAddPhotos()}>
            <Plus className="w-3 h-3" /> Add photos
          </Button>
          <Button variant="outline" size="sm" className="text-xs h-8 gap-1">
            <Edit2 className="w-3 h-3" /> Rename
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-xs h-8 gap-1 text-destructive hover:text-destructive"
            onClick={() => {
              void deleteCollection(collection.id).then((deleted) => {
                if (deleted) {
                  navigate("/collections");
                }
              });
            }}
          >
            <Trash2 className="w-3 h-3" /> Delete
          </Button>
        </div>
      </div>

      <ResultsGrid images={collectionImages} />
    </div>
  );
}
