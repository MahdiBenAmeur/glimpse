import { FolderPlus, ImagePlus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useApp } from "@/contexts/AppContext";
import { useState } from "react";

export default function FolderSelectionPage() {
  const { folders, addFolder, addPhotos, removeFolder, setOnboardingStep, startIndexing } = useApp();
  const [includeSubfolders, setIncludeSubfolders] = useState(true);

  const handleAddFolder = () => void addFolder(undefined, includeSubfolders);
  const handleAddPhotos = () => void addPhotos();

  const handleContinue = () => {
    setOnboardingStep(2);
    void startIndexing({ resetIndex: true });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-8">
      <div className="max-w-lg w-full">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-foreground mb-2">Choose folders to index</h1>
          <p className="text-sm text-muted-foreground max-w-sm mx-auto">
            Glimpse One scans selected folders on your computer to build a searchable index. Your files are never uploaded.
          </p>
        </div>

        <div className="bg-card border border-border rounded-xl p-4 mb-4 min-h-[200px]">
          {folders.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-[180px] text-center">
              <FolderPlus className="w-8 h-8 text-muted-foreground/40 mb-3" />
              <p className="text-sm text-muted-foreground">No folders selected yet</p>
              <p className="text-xs text-muted-foreground/70">Add at least one folder to continue</p>
            </div>
          ) : (
            <div className="space-y-2">
              {folders.map(f => (
                <div key={f.id} className="flex items-center gap-3 px-3 py-2 bg-muted rounded-lg">
                  <FolderPlus className="w-4 h-4 text-muted-foreground shrink-0" />
                  <span className="text-xs text-foreground flex-1 truncate">{f.path}</span>
                  <button onClick={() => removeFolder(f.id)} className="text-muted-foreground hover:text-foreground">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="text-xs gap-1.5" onClick={handleAddFolder}>
              <FolderPlus className="w-3.5 h-3.5" /> Add folder path
            </Button>
            <Button variant="outline" size="sm" className="text-xs gap-1.5" onClick={handleAddPhotos}>
              <ImagePlus className="w-3.5 h-3.5" /> Add photos
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Switch id="subfolders" checked={includeSubfolders} onCheckedChange={setIncludeSubfolders} />
            <Label htmlFor="subfolders" className="text-xs">Include subfolders</Label>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <Button variant="ghost" onClick={() => setOnboardingStep(0)}>Back</Button>
          <Button disabled={folders.length === 0} onClick={handleContinue}>
            Start indexing
          </Button>
        </div>
      </div>
    </div>
  );
}
