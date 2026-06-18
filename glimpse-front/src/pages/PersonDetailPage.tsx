import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Edit2, GitMerge, Trash2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApp } from "@/contexts/useApp";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { getPersonImages } from "@/lib/api";
import type { ImageResult } from "@/types/app";

const PERSON_IMAGES_PAGE_SIZE = 20;

export default function PersonDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { people, renamePerson, mergePerson, isWorking } = useApp();
  const person = people.find(p => p.id === id);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(person?.name || "");
  const [personImages, setPersonImages] = useState<ImageResult[]>([]);
  const [isLoadingImages, setIsLoadingImages] = useState(true);
  const [isLoadingMoreImages, setIsLoadingMoreImages] = useState(false);
  const [hasMoreImages, setHasMoreImages] = useState(true);
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false);
  const [selectedMergePersonId, setSelectedMergePersonId] = useState("");
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const loadingMoreRef = useRef(false);

  const loadFirstPageImages = useCallback(async (isCancelled: () => boolean = () => false) => {
    if (!id) return;
    setPersonImages([]);
    setHasMoreImages(true);
    setIsLoadingImages(true);
    loadingMoreRef.current = false;

    try {
      const images = await getPersonImages(id, { skip: 0, limit: PERSON_IMAGES_PAGE_SIZE });
      if (isCancelled()) return;
      setPersonImages(images);
      setHasMoreImages(images.length === PERSON_IMAGES_PAGE_SIZE);
    } catch {
      if (isCancelled()) return;
      setPersonImages([]);
      setHasMoreImages(false);
    } finally {
      if (!isCancelled()) {
        setIsLoadingImages(false);
      }
    }
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    void loadFirstPageImages(() => cancelled);

    return () => {
      cancelled = true;
    };
  }, [loadFirstPageImages]);

  const loadMoreImages = useCallback(async () => {
    if (!id || isLoadingImages || loadingMoreRef.current || !hasMoreImages) return;

    loadingMoreRef.current = true;
    setIsLoadingMoreImages(true);
    try {
      const nextImages = await getPersonImages(id, {
        skip: personImages.length,
        limit: PERSON_IMAGES_PAGE_SIZE,
      });
      setPersonImages((current) => {
        const seen = new Set(current.map((image) => image.id));
        const uniqueNextImages = nextImages.filter((image) => {
          if (seen.has(image.id)) return false;
          seen.add(image.id);
          return true;
        });
        return [...current, ...uniqueNextImages];
      });
      setHasMoreImages(nextImages.length === PERSON_IMAGES_PAGE_SIZE);
    } catch {
      setHasMoreImages(false);
    } finally {
      loadingMoreRef.current = false;
      setIsLoadingMoreImages(false);
    }
  }, [hasMoreImages, id, isLoadingImages, personImages.length]);

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target || isLoadingImages || isLoadingMoreImages || !hasMoreImages) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          void loadMoreImages();
        }
      },
      { rootMargin: "360px" },
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [hasMoreImages, isLoadingImages, isLoadingMoreImages, loadMoreImages]);

  const namedMergePeople = people.filter((candidate) => (
    candidate.id !== id && Boolean(candidate.name?.trim())
  ));

  const handleMergePerson = async () => {
    if (!id || !selectedMergePersonId) return;
    await mergePerson(id, selectedMergePersonId);
    setMergeDialogOpen(false);
    setSelectedMergePersonId("");
    await loadFirstPageImages();
  };

  if (!person) {
    return (
      <div className="p-6 text-center">
        <p className="text-muted-foreground">Person not found.</p>
        <Button variant="ghost" onClick={() => navigate("/people")} className="mt-4">Back to People</Button>
      </div>
    );
  }

  const handleSaveName = () => {
    if (editName.trim()) {
      renamePerson(person.id, editName.trim());
      setIsEditing(false);
    }
  };

  return (
    <div className="p-6">
      <Button variant="ghost" size="sm" className="mb-4 gap-1.5 text-xs" onClick={() => navigate("/people")}>
        <ArrowLeft className="w-3.5 h-3.5" /> Back to People
      </Button>

      <div className="flex items-start gap-5 mb-8">
        <img
          src={person.faceUrl}
          alt={person.name || "Unnamed"}
          className="w-20 h-20 rounded-full object-cover ring-2 ring-border"
        />
        <div className="flex-1">
          {isEditing ? (
            <div className="flex items-center gap-2 mb-2">
              <Input
                value={editName}
                onChange={e => setEditName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleSaveName()}
                className="h-8 text-sm w-48"
                autoFocus
              />
              <Button size="sm" className="h-8 text-xs" onClick={handleSaveName}>Save</Button>
              <Button variant="ghost" size="sm" className="h-8 text-xs" onClick={() => setIsEditing(false)}>Cancel</Button>
            </div>
          ) : (
            <h1 className="text-xl font-semibold text-foreground mb-1">{person.name || "Unnamed"}</h1>
          )}
          <p className="text-xs text-muted-foreground">{person.imageCount} photos - Last seen {person.lastSeen}</p>
          <div className="flex items-center gap-2 mt-3">
            <Button variant="outline" size="sm" className="text-xs h-7 gap-1" onClick={() => setIsEditing(true)}>
              <Edit2 className="w-3 h-3" /> Rename
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-xs h-7 gap-1"
              onClick={() => navigate("/search", { state: { personFilter: { id: Number(person.id), preference: "must_include" } } })}
            >
              <Search className="w-3 h-3" /> Search
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-xs h-7 gap-1"
              onClick={() => {
                setSelectedMergePersonId("");
                setMergeDialogOpen(true);
              }}
            >
              <GitMerge className="w-3 h-3" /> Merge
            </Button>
            <Button variant="ghost" size="sm" className="text-xs h-7 gap-1 text-destructive hover:text-destructive">
              <Trash2 className="w-3 h-3" /> Delete
            </Button>
          </div>
        </div>
      </div>

      {isLoadingImages ? (
        <SkeletonGrid />
      ) : personImages.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[320px] text-center">
          <Search className="w-10 h-10 text-muted-foreground/40 mb-4" />
          <h2 className="text-lg font-medium text-foreground mb-1">No photos found</h2>
          <p className="text-sm text-muted-foreground">This person does not have indexed photos yet.</p>
        </div>
      ) : (
        <>
          <ResultsGrid images={personImages} />
          <div ref={loadMoreRef} className="h-8" />
          {isLoadingMoreImages && <SkeletonGrid count={5} />}
        </>
      )}

      <Dialog open={mergeDialogOpen} onOpenChange={setMergeDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base">Merge with another person</DialogTitle>
            <DialogDescription className="text-xs">
              Pick a named person to merge into {person.name || "this person"}. The current person will be kept.
            </DialogDescription>
          </DialogHeader>

          {namedMergePeople.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-5 text-center text-xs text-muted-foreground">
              No other named people are available to merge yet.
            </div>
          ) : (
            <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
              {namedMergePeople.map((candidate) => {
                const selected = selectedMergePersonId === candidate.id;
                return (
                  <button
                    key={candidate.id}
                    type="button"
                    onClick={() => setSelectedMergePersonId(candidate.id)}
                    className={`flex w-full items-center gap-3 rounded-lg border p-2 text-left transition ${
                      selected ? "border-primary bg-primary/10" : "border-border hover:bg-muted/60"
                    }`}
                  >
                    <img
                      src={candidate.faceUrl}
                      alt={candidate.name || "Named person"}
                      className="h-10 w-10 rounded-full object-cover ring-1 ring-border"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">{candidate.name}</p>
                      <p className="text-xs text-muted-foreground">{candidate.imageCount} photos</p>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button variant="ghost" size="sm" onClick={() => setMergeDialogOpen(false)} disabled={isWorking}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleMergePerson}
              disabled={!selectedMergePersonId || isWorking}
            >
              Merge
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SkeletonGrid({ count = 12 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="animate-shimmer rounded-lg" style={{ height: 180 + (i % 3) * 40 }} />
      ))}
    </div>
  );
}
