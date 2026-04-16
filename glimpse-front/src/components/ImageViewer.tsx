import { X, Heart, ChevronLeft, ChevronRight, ExternalLink, FolderOpen, Copy, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToggleFavorite } from "@/hooks/api/useImages";
import type { ImageResult } from "@/data/mockData";
import { useEffect, useCallback } from "react";

interface Props {
  image: ImageResult;
  images: ImageResult[];
  currentIndex: number;
  onClose: () => void;
  onNavigate: (index: number) => void;
}

export function ImageViewer({ image, images, currentIndex, onClose, onNavigate }: Props) {
  const { mutate: toggleFavorite } = useToggleFavorite();

  const goNext = useCallback(() => {
    if (currentIndex < images.length - 1) onNavigate(currentIndex + 1);
  }, [currentIndex, images.length, onNavigate]);

  const goPrev = useCallback(() => {
    if (currentIndex > 0) onNavigate(currentIndex - 1);
  }, [currentIndex, onNavigate]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") goNext();
      if (e.key === "ArrowLeft") goPrev();
      if (e.key === "f" || e.key === "F") toggleFavorite({ id: image.id, isFav: !image.isFavorite });
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, goNext, goPrev, toggleFavorite, image.id]);

  return (
    <div className="fixed inset-0 z-50 bg-foreground/90 flex">
      {/* Close button */}
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-4 right-4 z-10 text-background hover:text-background hover:bg-background/10"
        onClick={onClose}
      >
        <X className="w-5 h-5" />
      </Button>

      {/* Navigation */}
      {currentIndex > 0 && (
        <Button
          variant="ghost"
          size="icon"
          className="absolute left-4 top-1/2 -translate-y-1/2 z-10 text-background hover:text-background hover:bg-background/10"
          onClick={goPrev}
        >
          <ChevronLeft className="w-6 h-6" />
        </Button>
      )}
      {currentIndex < images.length - 1 && (
        <Button
          variant="ghost"
          size="icon"
          className="absolute right-[340px] top-1/2 -translate-y-1/2 z-10 text-background hover:text-background hover:bg-background/10"
          onClick={goNext}
        >
          <ChevronRight className="w-6 h-6" />
        </Button>
      )}

      {/* Image */}
      <div className="flex-1 flex items-center justify-center p-8">
        <img
          src={image.url}
          alt={image.filename}
          className="max-w-full max-h-full object-contain rounded-lg"
        />
      </div>

      {/* Side panel */}
      <div className="w-[320px] bg-card border-l border-border p-5 overflow-auto flex flex-col">
        <h3 className="font-medium text-sm text-foreground mb-1">{image.filename}</h3>
        <p className="text-xs text-muted-foreground mb-4">{image.folder}</p>

        <Button
          variant="ghost"
          size="sm"
          className="justify-start gap-2 text-xs mb-2"
          onClick={() => toggleFavorite({ id: image.id, isFav: !image.isFavorite })}
        >
          <Heart className={`w-3.5 h-3.5 ${image.isFavorite ? "fill-destructive text-destructive" : ""}`} />
          {image.isFavorite ? "Unfavorite" : "Favorite"}
        </Button>

        <div className="space-y-3 text-xs mt-4">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Date taken</span>
            <span className="text-foreground">{image.dateTaken}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Dimensions</span>
            <span className="text-foreground">{image.width} × {image.height}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Faces</span>
            <span className="text-foreground">{image.faceCount}</span>
          </div>
        </div>

        {image.people.length > 0 && (
          <div className="mt-5">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">People</p>
            <div className="flex flex-wrap gap-1.5">
              {image.people.map(p => (
                <Badge key={p} variant="secondary" className="text-[11px]">{p}</Badge>
              ))}
            </div>
          </div>
        )}

        {image.collections.length > 0 && (
          <div className="mt-5">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Collections</p>
            <div className="flex flex-wrap gap-1.5">
              {image.collections.map(c => (
                <Badge key={c} variant="outline" className="text-[11px]">{c}</Badge>
              ))}
            </div>
          </div>
        )}

        <div className="mt-auto pt-6 space-y-1">
          <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs">
            <Search className="w-3.5 h-3.5" /> Find similar
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs">
            <FolderOpen className="w-3.5 h-3.5" /> Reveal in folder
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs">
            <ExternalLink className="w-3.5 h-3.5" /> Open externally
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs">
            <Copy className="w-3.5 h-3.5" /> Copy path
          </Button>
        </div>
      </div>
    </div>
  );
}
