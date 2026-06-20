import { useState } from "react";
import { Plus, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useApp } from "@/contexts/useApp";
import { useNavigate } from "react-router-dom";

export default function CollectionsPage() {
  const { collections, createCollection } = useApp();
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const handleCreate = () => {
    if (newName.trim()) {
      createCollection(newName.trim(), newDesc.trim() || undefined);
      setNewName("");
      setNewDesc("");
      setCreateOpen(false);
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-foreground">Collections</h1>
        <Button size="sm" className="text-xs gap-1.5" onClick={() => setCreateOpen(true)}>
          <Plus className="w-3.5 h-3.5" /> New Collection
        </Button>
      </div>

      {collections.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[400px] text-center">
          <FolderOpen className="w-12 h-12 text-muted-foreground/30 mb-4" />
          <h2 className="text-lg font-medium text-foreground mb-1">No collections yet</h2>
          <p className="text-sm text-muted-foreground mb-4">Create a collection to organize your photos.</p>
          <Button variant="outline" size="sm" onClick={() => setCreateOpen(true)}>Create collection</Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {collections.map(col => (
            <button
              key={col.id}
              onClick={() => navigate(`/collections/${col.id}`)}
              className="bg-card border border-border rounded-xl overflow-hidden text-left hover:border-primary/30 transition-colors group"
            >
              <div className="grid grid-cols-2 gap-0.5 h-36 bg-muted">
                {col.previewUrls.slice(0, 4).map((url, i) => (
                  <img key={i} src={url} alt="" className="w-full h-full object-cover" />
                ))}
              </div>
              <div className="p-3 bg-card relative">
                <h3 className="text-sm font-medium text-foreground">{col.name}</h3>
                {col.description && <p className="text-[11px] text-muted-foreground truncate">{col.description}</p>}
                <p className="text-[10px] text-muted-foreground mt-1">{col.imageCount} items • {col.modifiedDate}</p>
              </div>
            </button>
          ))}
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-base">New Collection</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Name</Label>
              <Input value={newName} onChange={e => setNewName(e.target.value)} className="mt-1 h-9 text-sm" placeholder="Collection name" />
            </div>
            <div>
              <Label className="text-xs">Description (optional)</Label>
              <Textarea value={newDesc} onChange={e => setNewDesc(e.target.value)} className="mt-1 text-sm" placeholder="Brief description" rows={2} />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="ghost" size="sm" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleCreate} disabled={!newName.trim()}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
