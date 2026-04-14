import { Heart, Users } from "lucide-react";
import { useApp } from "@/contexts/AppContext";
import type { ImageResult } from "@/data/mockData";
import { useState } from "react";
import { ImageViewer } from "@/components/ImageViewer";

interface Props {
  images: ImageResult[];
}

export function ResultsGrid({ images }: Props) {
  const { toggleFavorite } = useApp();
  const [viewerImage, setViewerImage] = useState<ImageResult | null>(null);
  const [viewerIdx, setViewerIdx] = useState(0);

  const openViewer = (img: ImageResult, idx: number) => {
    setViewerImage(img);
    setViewerIdx(idx);
  };

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
        {images.map((img, i) => (
          <div
            key={img.id}
            className="group relative rounded-lg overflow-hidden bg-card border border-border cursor-pointer hover:border-primary/30 transition-colors"
            onDoubleClick={() => openViewer(img, i)}
          >
            <div className="aspect-[4/3] overflow-hidden">
              <img
                src={img.thumbnailUrl ?? img.url}
                alt={img.filename}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                loading="lazy"
                onError={(event) => {
                  if (img.thumbnailUrl && event.currentTarget.src !== new URL(img.url, window.location.origin).toString()) {
                    event.currentTarget.src = img.url;
                  }
                }}
              />
            </div>
            {/* Hover overlay */}
            <div className="absolute inset-0 bg-foreground/0 group-hover:bg-foreground/10 transition-colors" />
            <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={(e) => { e.stopPropagation(); toggleFavorite(img.id); }}
                className="w-7 h-7 rounded-full bg-card/80 backdrop-blur flex items-center justify-center hover:bg-card"
              >
                <Heart className={`w-3.5 h-3.5 ${img.isFavorite ? "fill-destructive text-destructive" : "text-foreground"}`} />
              </button>
            </div>
            {img.faceCount > 0 && (
              <div className="absolute bottom-2 left-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-card/80 backdrop-blur text-[10px] text-foreground">
                  <Users className="w-3 h-3" /> {img.faceCount}
                </div>
              </div>
            )}
            <div className="px-2 py-1.5">
              <p className="text-[11px] text-muted-foreground truncate">{img.filename}</p>
            </div>
          </div>
        ))}
      </div>

      {viewerImage && (
        <ImageViewer
          image={viewerImage}
          images={images}
          currentIndex={viewerIdx}
          onClose={() => setViewerImage(null)}
          onNavigate={(idx) => { setViewerIdx(idx); setViewerImage(images[idx]); }}
        />
      )}
    </>
  );
}
