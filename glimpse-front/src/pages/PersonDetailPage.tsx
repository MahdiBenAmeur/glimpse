import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Edit2, Trash2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useApp } from "@/contexts/AppContext";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { getPersonImages } from "@/lib/api";

export default function PersonDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { people, renamePerson } = useApp();
  const person = people.find(p => p.id === id);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(person?.name || "");
  const [personImages, setPersonImages] = useState<any[]>([]);

  useEffect(() => {
    if (!id) return;
    void getPersonImages(id).then(setPersonImages).catch(() => setPersonImages([]));
  }, [id]);

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

      <ResultsGrid images={personImages} />
    </div>
  );
}
