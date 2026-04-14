import { X, Heart, ChevronLeft, ChevronRight, ExternalLink, Copy, Search } from "lucide-react";
import { useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/sonner";
import { useApp } from "@/contexts/AppContext";
import type { ImageResult } from "@/data/mockData";
import { openImageExternally } from "@/lib/api";

interface Props {
  image: ImageResult;
  images: ImageResult[];
  currentIndex: number;
  onClose: () => void;
  onNavigate: (index: number) => void;
}

export function ImageViewer({ image, images, currentIndex, onClose, onNavigate }: Props) {
  const navigate = useNavigate();
  const { toggleFavorite } = useApp();

  const goNext = useCallback(() => {
    if (currentIndex < images.length - 1) onNavigate(currentIndex + 1);
  }, [currentIndex, images.length, onNavigate]);

  const goPrev = useCallback(() => {
    if (currentIndex > 0) onNavigate(currentIndex - 1);
  }, [currentIndex, onNavigate]);

  const handleFindSimilar = useCallback(() => {
    const similarImageId = image.imageId ?? Number(image.id);
    if (!Number.isFinite(similarImageId)) {
      toast.error("This image cannot be used for similarity search yet.");
      return;
    }

    navigate("/search", {
      state: {
        similarImageId,
        similarSourceLabel: image.filename,
      },
    });
    onClose();
  }, [image.filename, image.id, image.imageId, navigate, onClose]);

  const handleOpenExternal = useCallback(async () => {
    const targetImageId = image.imageId ?? Number(image.id);
    if (!Number.isFinite(targetImageId)) {
      toast.error("This image cannot be opened externally.");
      return;
    }

    try {
      await openImageExternally(targetImageId);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not open image externally.");
    }
  }, [image.id, image.imageId]);

  const handleCopyPath = useCallback(async () => {
    if (!image.path) {
      toast.error("Image path is not available.");
      return;
    }

    try {
      await navigator.clipboard.writeText(image.path);
      toast.success("Image path copied.");
    } catch {
      toast.error("Could not copy image path.");
    }
  }, [image.path]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") goNext();
      if (e.key === "ArrowLeft") goPrev();
      if (e.key === "f" || e.key === "F") toggleFavorite(image.id);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, goNext, goPrev, toggleFavorite, image.id]);

  return (
    <div className="fixed inset-0 z-50 bg-foreground/90 flex">
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-4 left-4 z-10 text-background hover:text-background hover:bg-background/10"
        onClick={onClose}
      >
        <X className="w-5 h-5" />
      </Button>

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

      <div className="flex-1 flex items-center justify-center p-8">
        <img
          src={image.url}
          alt={image.filename}
          className="max-w-full max-h-full object-contain rounded-lg"
        />
      </div>

      <div className="w-[320px] bg-card border-l border-border p-5 overflow-auto flex flex-col">
        <h3 className="font-medium text-sm text-foreground mb-1">{image.filename}</h3>
        <p className="text-xs text-muted-foreground mb-4">{image.folder}</p>

        <Button
          variant="ghost"
          size="sm"
          className="justify-start gap-2 text-xs mb-2"
          onClick={() => toggleFavorite(image.id)}
        >
          <Heart className={`w-3.5 h-3.5 ${image.isFavorite ? "fill-destructive text-destructive" : ""}`} />
          {image.isFavorite ? "Unfavorite" : "Favorite"}
        </Button>

        <div className="space-y-3 text-xs mt-4">
          <div className="flex justify-between gap-3">
            <span className="text-muted-foreground">Date taken</span>
            <span className="text-foreground text-right">{image.dateTaken || "Unknown"}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-muted-foreground">Dimensions</span>
            <span className="text-foreground text-right">{image.width} x {image.height}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-muted-foreground">Faces</span>
            <span className="text-foreground text-right">{image.faceCount}</span>
          </div>
          {typeof image.score === "number" && (
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">Similarity</span>
              <span className="text-foreground text-right">{Math.round(image.score * 100)}%</span>
            </div>
          )}
          {image.path && (
            <div className="space-y-1">
              <span className="text-muted-foreground">Path</span>
              <p className="text-foreground break-all">{image.path}</p>
            </div>
          )}
        </div>

        {image.people.length > 0 && (
          <div className="mt-5">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">People</p>
            <div className="flex flex-wrap gap-1.5">
              {image.people.map((person) => (
                <Badge key={person} variant="secondary" className="text-[11px]">{person}</Badge>
              ))}
            </div>
          </div>
        )}

        {image.collections.length > 0 && (
          <div className="mt-5">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Collections</p>
            <div className="flex flex-wrap gap-1.5">
              {image.collections.map((collection) => (
                <Badge key={collection} variant="outline" className="text-[11px]">{collection}</Badge>
              ))}
            </div>
          </div>
        )}

        <div className="mt-auto pt-6 space-y-1">
          <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs" onClick={handleFindSimilar}>
            <Search className="w-3.5 h-3.5" /> Find similar
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs" onClick={() => void handleOpenExternal()}>
            <ExternalLink className="w-3.5 h-3.5" /> Open externally
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs" onClick={() => void handleCopyPath()}>
            <Copy className="w-3.5 h-3.5" /> Copy path
          </Button>
        </div>
      </div>
    </div>
  );
}
