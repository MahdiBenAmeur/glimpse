import { useEffect, useState } from "react";
import { Download, Check, Loader2, Trash2, FolderPlus, ImagePlus, X, Database, Users, Image, AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useApp } from "@/contexts/useApp";
import { cn } from "@/lib/utils";
import type { ModelInfo } from "@/types/app";

const phaseLabels: Record<string, string> = {
  scanning: "Scanning folders",
  embeddings: "Generating embeddings",
  video_keyframes: "Extracting keyframes",
  faces: "Detecting faces",
  clustering: "Clustering faces",
  thumbnails: "Creating thumbnails",
  writing: "Writing index",
  cancelling: "Cancelling after current batch",
  cancelled: "Indexing cancelled",
  complete: "Indexing complete",
  idle: "Preparing...",
};

function SectionHeader({
  number,
  title,
  description,
  done,
  enabled,
  expanded,
  onToggle,
}: {
  number: number;
  title: string;
  description: string;
  done: boolean;
  enabled: boolean;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={!enabled}
      className={cn(
        "w-full flex items-center gap-3 px-4 py-3 rounded-xl border text-left transition-colors",
        done
          ? "border-success/40 bg-success/5"
          : enabled
            ? "border-border bg-card hover:border-primary/30"
            : "border-border bg-card/50 opacity-60 cursor-not-allowed",
      )}
    >
      <div
        className={cn(
          "w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium shrink-0",
          done
            ? "bg-success text-success-foreground"
            : enabled
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground",
        )}
      >
        {done ? <Check className="w-4 h-4" /> : number}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-foreground">{title}</div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>
      {enabled && (expanded ? <ChevronDown className="w-4 h-4 text-muted-foreground" /> : <ChevronRight className="w-4 h-4 text-muted-foreground" />)}
    </button>
  );
}

export default function OnboardingPage() {
  const {
    models,
    activeModel,
    downloadModel,
    setActiveModel,
    removeModel,
    isWorking,
    folders,
    addFolder,
    addPhotos,
    removeFolder,
    startIndexing,
    settings,
    indexingStatus,
    runInBackground,
    completeOnboarding,
    cancelIndexing,
  } = useApp();

  const hasActiveModel = !!activeModel;
  const hasFolders = folders.length > 0;
  const indexingDone = indexingStatus.phase === "complete";
  const isCancelling = indexingStatus.phase === "cancelling";

  const [modelStepDone, setModelStepDone] = useState(hasActiveModel);
  const [foldersStepDone, setFoldersStepDone] = useState(false);
  const [expanded, setExpanded] = useState<"models" | "folders" | "indexing" | null>("models");
  const [includeSubfolders, setIncludeSubfolders] = useState(settings.includeSubfoldersByDefault);

  useEffect(() => {
    setIncludeSubfolders(settings.includeSubfoldersByDefault);
  }, [settings.includeSubfoldersByDefault]);

  useEffect(() => {
    if (hasActiveModel) setModelStepDone(true);
  }, [hasActiveModel]);

  useEffect(() => {
    if (modelStepDone && !hasFolders) setExpanded("folders");
    if (hasFolders && !foldersStepDone) setExpanded("folders");
  }, [modelStepDone, hasFolders, foldersStepDone]);

  useEffect(() => {
    if (foldersStepDone) setExpanded("indexing");
  }, [foldersStepDone]);

  const handleSelectModel = async (id: string) => {
    await setActiveModel(id);
    setModelStepDone(true);
    setExpanded("folders");
  };

  const handleStartIndexing = () => {
    setFoldersStepDone(true);
    setExpanded("indexing");
    void startIndexing({ resetIndex: true });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-8">
      <div className="max-w-2xl w-full space-y-6">
        <div className="text-center">
          <img src="/logo.png" alt="Glimpse logo" className="w-20 h-20 rounded-2xl object-contain mx-auto mb-3" />
          <h1 className="text-2xl font-semibold text-foreground mb-1">Welcome to Glimpse One</h1>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            Three quick steps to get you searching. All data stays on your computer.
          </p>
        </div>

        {/* Step 1: Models */}
        <div className="space-y-2">
          <SectionHeader
            number={1}
            title="Choose a model"
            description="Pick an embedding model to power natural-language search."
            done={modelStepDone}
            enabled={true}
            expanded={expanded === "models"}
            onToggle={() => setExpanded(expanded === "models" ? null : "models")}
          />
          {expanded === "models" && (
            <div className="space-y-4 pl-2">
              {models.length === 0 && (
                <div className="border border-dashed border-border rounded-xl p-6 text-center bg-card">
                  <p className="text-sm text-foreground mb-1">No models loaded yet</p>
                  <p className="text-xs text-muted-foreground">Check that the backend is running and the model list endpoint is available.</p>
                </div>
              )}
              <OnboardingModelGroup
                title="Primary model"
                description="Powers both image and video search."
                models={models}
                onSelect={(id) => void handleSelectModel(id)}
                onDownload={(id) => void downloadModel(id)}
                onRemove={(id) => void removeModel(id)}
                isWorking={isWorking}
              />
              <div className="flex justify-end pt-1">
                <Button size="sm" disabled={!modelStepDone} onClick={() => setExpanded("folders")}>
                  Continue to folders
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Step 2: Folders */}
        <div className="space-y-2">
          <SectionHeader
            number={2}
            title="Choose folders to index"
            description="Add at least one folder of photos to search."
            done={foldersStepDone}
            enabled={modelStepDone}
            expanded={expanded === "folders"}
            onToggle={() => modelStepDone && setExpanded(expanded === "folders" ? null : "folders")}
          />
          {expanded === "folders" && modelStepDone && (
            <div className="space-y-3 pl-2">
              <div className="bg-card border border-border rounded-xl p-4 min-h-[160px]">
                {folders.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-[140px] text-center">
                    <FolderPlus className="w-7 h-7 text-muted-foreground/40 mb-2" />
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

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" className="text-xs gap-1.5" onClick={() => void addFolder(undefined, includeSubfolders)}>
                    <FolderPlus className="w-3.5 h-3.5" /> Add folder path
                  </Button>
                  <Button variant="outline" size="sm" className="text-xs gap-1.5" onClick={() => void addPhotos()}>
                    <ImagePlus className="w-3.5 h-3.5" /> Add photos
                  </Button>
                </div>
                <div className="flex items-center gap-2">
                  <Switch id="subfolders" checked={includeSubfolders} onCheckedChange={setIncludeSubfolders} />
                  <Label htmlFor="subfolders" className="text-xs">Include subfolders</Label>
                </div>
              </div>

              <div className="flex items-center justify-end pt-1">
                <Button size="sm" disabled={!hasFolders} onClick={handleStartIndexing}>
                  Start indexing
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Step 3: Indexing */}
        <div className="space-y-2">
          <SectionHeader
            number={3}
            title="Build the index"
            description="Generate embeddings and detect faces. This may take a few minutes."
            done={indexingDone}
            enabled={foldersStepDone}
            expanded={expanded === "indexing"}
            onToggle={() => foldersStepDone && setExpanded(expanded === "indexing" ? null : "indexing")}
          />
          {expanded === "indexing" && foldersStepDone && (
            <div className="pl-2">
              <div className="bg-card border border-border rounded-xl p-4">
                {indexingStatus.error && !indexingDone ? (
                  <div className="text-center">
                    <div className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center mx-auto mb-2">
                      <AlertTriangle className="w-6 h-6 text-destructive" />
                    </div>
                    <h2 className="text-sm font-medium text-foreground mb-1">Indexing failed</h2>
                    <p className="text-xs text-muted-foreground mb-4 max-w-sm mx-auto">{indexingStatus.error}</p>
                    <Button size="sm" onClick={handleStartIndexing}>Retry indexing</Button>
                  </div>
                ) : (
                  <>
                    <div className="text-center mb-4">
                      {indexingDone ? (
                        <div className="w-12 h-12 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-2">
                          <Check className="w-6 h-6 text-success" />
                        </div>
                      ) : (
                        <Loader2 className="w-7 h-7 text-primary animate-spin mx-auto mb-2" />
                      )}
                      <h2 className="text-sm font-medium text-foreground">
                        {indexingDone ? "Your library is ready!" : "Building your index"}
                      </h2>
                    </div>
                    <Progress value={indexingStatus.progress} className="h-2 mb-4" />
                    {indexingStatus.phase === "clustering" && (
                      <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/40 px-3 py-2 mb-3">
                        <Loader2 className="w-4 h-4 animate-spin text-primary" />
                        <div className="text-left">
                          <p className="text-xs font-medium text-foreground">Clustering faces</p>
                          <p className="text-[10px] text-muted-foreground">We are clustering faces into people.</p>
                        </div>
                      </div>
                    )}
                    <div className="space-y-1 mb-3">
                      <div className="flex items-center justify-center gap-2">
                        <span className="text-xs font-medium text-foreground">{phaseLabels[indexingStatus.phase]}</span>
                        {indexingStatus.phase === "video_keyframes" && indexingStatus.keyframeCount != null && indexingStatus.keyframeCount > 0 && (
                          <span className="text-[10px] text-muted-foreground">({indexingStatus.keyframeCount} keyframes)</span>
                        )}
                      </div>
                      {indexingStatus.currentFile && indexingStatus.phase !== "clustering" && (
                        <p className="text-[11px] text-muted-foreground/70 text-center truncate max-w-full px-2">
                          {indexingStatus.currentFile}
                        </p>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Image className="w-3.5 h-3.5" />
                        <span>Total: {indexingStatus.total.toLocaleString()}</span>
                      </div>
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Database className="w-3.5 h-3.5" />
                        <span>Processed: {indexingStatus.processed.toLocaleString()}</span>
                      </div>
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Users className="w-3.5 h-3.5" />
                        <span>Faces: {indexingStatus.facesDetected}</span>
                      </div>
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>Skipped: {indexingStatus.skipped}</span>
                      </div>
                    </div>
                  </>
                )}
              </div>
              <div className="flex items-center justify-center gap-3 pt-3">
                {indexingDone || indexingStatus.error ? (
                  indexingDone ? (
                    <Button onClick={completeOnboarding}>Start searching</Button>
                  ) : (
                    <Button size="sm" onClick={handleStartIndexing}>Retry indexing</Button>
                  )
                ) : (
                  <>
                    <Button variant="outline" onClick={runInBackground}>Run in background</Button>
                    <Button
                      variant="ghost"
                      className="text-muted-foreground"
                      onClick={() => void cancelIndexing()}
                      disabled={isCancelling}
                    >
                      {isCancelling ? "Cancelling..." : "Cancel"}
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function OnboardingModelGroup({
  title,
  description,
  models,
  onSelect,
  onDownload,
  onRemove,
  isWorking,
}: {
  title: string;
  description: string;
  models: ModelInfo[];
  onSelect: (id: string) => void;
  onDownload: (id: string) => void;
  onRemove: (id: string) => void;
  isWorking: boolean;
}) {
  if (models.length === 0) return null;
  return (
    <div className="space-y-2">
      <div>
        <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{title}</p>
        <p className="text-xs text-muted-foreground/80">{description}</p>
      </div>
      {models.map((model) => (
        <div
          key={model.id}
          className={cn(
            "border rounded-xl p-4 transition-colors",
            model.status === "active"
              ? "border-primary bg-accent"
              : "border-border bg-card hover:border-primary/30",
          )}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-medium text-sm text-foreground">{model.name}</h3>
                <Badge variant="outline" className="text-[10px]">{model.quality}</Badge>
                <Badge variant="secondary" className="text-[10px]">{model.speed}</Badge>
              </div>
              <p className="text-xs text-muted-foreground mb-2">{model.description}</p>
              <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                <span>{model.diskSize}</span>
                <span>•</span>
                <span>{model.suitability}</span>
              </div>
            </div>
            <div className="flex flex-col items-end gap-1.5 shrink-0">
              {model.status === "not_installed" && (
                <Button size="sm" variant="outline" className="text-xs h-8" onClick={() => onDownload(model.id)} disabled={isWorking}>
                  <Download className="w-3 h-3 mr-1.5" /> Download
                </Button>
              )}
              {model.status === "downloading" && (
                <Button size="sm" variant="outline" className="text-xs h-8" disabled>
                  <Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> {model.downloadProgress}%
                </Button>
              )}
              {model.status === "installed" && (
                <Button size="sm" className="text-xs h-8" onClick={() => onSelect(model.id)} disabled={isWorking}>
                  <Check className="w-3 h-3 mr-1.5" /> Use this model
                </Button>
              )}
              {(model.status === "installed" || model.status === "active") && (
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs h-8 text-destructive hover:text-destructive"
                  onClick={() => onRemove(model.id)}
                  disabled={isWorking}
                >
                  <Trash2 className="w-3 h-3 mr-1.5" /> Delete
                </Button>
              )}
              {model.status === "active" && (
                <Badge className="bg-primary text-primary-foreground text-[10px]">Active</Badge>
              )}
            </div>
          </div>
          {model.status === "downloading" && (
            <Progress value={model.downloadProgress} className="mt-3 h-1.5" />
          )}
        </div>
      ))}
    </div>
  );
}
