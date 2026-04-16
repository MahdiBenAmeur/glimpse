import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Edit2, Trash2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCollections, useDeleteCollection } from "@/hooks/api/useCollections";
import { useImages } from "@/hooks/api/useImages";
import { ResultsGrid } from "@/components/search/ResultsGrid";

export default function CollectionDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: collections = [] } = useCollections();
  const { data: images = [] } = useImages();
  const { mutate: deleteCollection } = useDeleteCollection();
  const collection = collections.find(c => c.id === id);

  if (!collection) {
    return (
      <div className="p-6 text-center">
        <p className="text-muted-foreground">Collection not found.</p>
        <Button variant="ghost" onClick={() => navigate("/collections")} className="mt-4">Back</Button>
      </div>
    );
  }

  const collectionImages = images.filter(img => img.collections.includes(collection.name));

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
          <Button variant="outline" size="sm" className="text-xs h-8 gap-1">
            <Plus className="w-3 h-3" /> Add photos
          </Button>
          <Button variant="outline" size="sm" className="text-xs h-8 gap-1">
            <Edit2 className="w-3 h-3" /> Rename
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-xs h-8 gap-1 text-destructive hover:text-destructive"
            onClick={() => { deleteCollection(collection.id); navigate("/collections"); }}
          >
            <Trash2 className="w-3 h-3" /> Delete
          </Button>
        </div>
      </div>

      <ResultsGrid images={collectionImages} />
    </div>
  );
}
