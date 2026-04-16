import { useState } from "react";
import { Search, Users as UsersIcon, Edit2, Merge, Trash2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { usePeople } from "@/hooks/api/usePeople";
import { useNavigate } from "react-router-dom";

export default function PeoplePage() {
  const { data: people = [] } = usePeople();
  const [searchQuery, setSearchQuery] = useState("");
  const navigate = useNavigate();

  const named = people.filter(p => p.name);
  const unnamed = people.filter(p => !p.name);

  const filtered = (list: typeof people) =>
    searchQuery
      ? list.filter(p => p.name?.toLowerCase().includes(searchQuery.toLowerCase()))
      : list;

  if (people.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-6">
        <UsersIcon className="w-12 h-12 text-muted-foreground/30 mb-4" />
        <h2 className="text-lg font-medium text-foreground mb-1">No people detected yet</h2>
        <p className="text-sm text-muted-foreground mb-4">Index your photos with face detection enabled to find people.</p>
        <Button variant="outline" size="sm" onClick={() => navigate("/index-manager")}>Go to Index</Button>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-foreground">People</h1>
        <div className="flex items-center gap-2">
          <div className="relative w-56">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search people..."
              className="pl-9 h-8 text-xs"
            />
          </div>
          <Button variant="outline" size="sm" className="text-xs h-8 gap-1.5">
            <Merge className="w-3 h-3" /> Merge
          </Button>
        </div>
      </div>

      {/* Named people */}
      <div className="mb-8">
        <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
          Named ({named.length})
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
          {filtered(named).map(person => (
            <PersonCard key={person.id} person={person} onClick={() => navigate(`/people/${person.id}`)} />
          ))}
        </div>
      </div>

      {/* Unnamed people */}
      {unnamed.length > 0 && (
        <div>
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
            Unnamed ({unnamed.length})
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
            {unnamed.map(person => (
              <PersonCard key={person.id} person={person} onClick={() => navigate(`/people/${person.id}`)} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PersonCard({ person, onClick }: { person: { id: string; name: string | null; faceUrl: string; imageCount: number; lastSeen?: string }; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="bg-card border border-border rounded-xl p-4 text-center hover:border-primary/30 transition-colors group"
    >
      <img
        src={person.faceUrl}
        alt={person.name || "Unnamed"}
        className="w-16 h-16 rounded-full object-cover mx-auto mb-3 ring-2 ring-border group-hover:ring-primary/30 transition-colors"
      />
      <p className="text-sm font-medium text-foreground truncate">{person.name || "Unnamed"}</p>
      <p className="text-[10px] text-muted-foreground">{person.imageCount} photos</p>
    </button>
  );
}
