import { Heart } from "lucide-react";
import { useApp } from "@/contexts/AppContext";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";

export default function FavoritesPage() {
  const { favorites } = useApp();
  const navigate = useNavigate();

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Favorites</h1>
          <p className="text-xs text-muted-foreground mt-0.5">{favorites.length} images</p>
        </div>
      </div>

      {favorites.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
          <Heart className="w-12 h-12 text-muted-foreground/30 mb-4" />
          <h2 className="text-lg font-medium text-foreground mb-1">No favorites yet</h2>
          <p className="text-sm text-muted-foreground mb-4">Favorite images from Search to see them here.</p>
          <Button variant="outline" size="sm" onClick={() => navigate("/search")}>Go to Search</Button>
        </div>
      ) : (
        <ResultsGrid images={favorites} />
      )}
    </div>
  );
}
