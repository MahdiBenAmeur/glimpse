import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Edit2, Trash2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useApp } from "@/contexts/AppContext";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { getPersonImages } from "@/lib/api";
import type { ImageResult } from "@/types/app";

const PERSON_IMAGES_PAGE_SIZE = 20;

export default function PersonDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { people, renamePerson } = useApp();
  const person = people.find(p => p.id === id);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(person?.name || "");
  const [personImages, setPersonImages] = useState<ImageResult[]>([]);
  const [isLoadingImages, setIsLoadingImages] = useState(true);
  const [isLoadingMoreImages, setIsLoadingMoreImages] = useState(false);
  const [hasMoreImages, setHasMoreImages] = useState(true);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setPersonImages([]);
    setHasMoreImages(true);
    setIsLoadingImages(true);

    void getPersonImages(id, { skip: 0, limit: PERSON_IMAGES_PAGE_SIZE })
      .then((images) => {
        if (cancelled) return;
        setPersonImages(images);
        setHasMoreImages(images.length === PERSON_IMAGES_PAGE_SIZE);
      })
      .catch(() => {
        if (cancelled) return;
        setPersonImages([]);
        setHasMoreImages(false);
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingImages(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  const loadMoreImages = useCallback(async () => {
    if (!id || isLoadingImages || isLoadingMoreImages || !hasMoreImages) return;

    setIsLoadingMoreImages(true);
    try {
      const nextImages = await getPersonImages(id, {
        skip: personImages.length,
        limit: PERSON_IMAGES_PAGE_SIZE,
      });
      setPersonImages((current) => [...current, ...nextImages]);
      setHasMoreImages(nextImages.length === PERSON_IMAGES_PAGE_SIZE);
    } catch {
      setHasMoreImages(false);
    } finally {
      setIsLoadingMoreImages(false);
    }
  }, [hasMoreImages, id, isLoadingImages, isLoadingMoreImages, personImages.length]);

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
          <p className="text-xs text-muted-foreground">{person.imageCount} photos • Last seen {person.lastSeen}</p>
          <div className="flex items-center gap-2 mt-3">
            <Button variant="outline" size="sm" className="text-xs h-7 gap-1" onClick={() => setIsEditing(true)}>
              <Edit2 className="w-3 h-3" /> Rename
            </Button>
            <Button variant="outline" size="sm" className="text-xs h-7 gap-1">
              <Search className="w-3 h-3" /> Search
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
