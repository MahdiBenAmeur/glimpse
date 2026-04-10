import { Loader2, Database, Users, Image, AlertTriangle, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useApp } from "@/contexts/AppContext";

const phaseLabels: Record<string, string> = {
  scanning: "Scanning folders",
  embeddings: "Generating embeddings",
  faces: "Detecting faces",
  thumbnails: "Creating thumbnails",
  writing: "Writing index",
  complete: "Indexing complete",
  idle: "Preparing...",
};

export default function InitialIndexingPage() {
  const { indexingStatus, runInBackground, completeOnboarding } = useApp();
  const isDone = indexingStatus.phase === "complete";

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-8">
      <div className="max-w-lg w-full text-center">
        <div className="mb-6">
          {isDone ? (
            <div className="w-14 h-14 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
              <Check className="w-7 h-7 text-success" />
            </div>
          ) : (
            <div className="w-14 h-14 rounded-full bg-accent flex items-center justify-center mx-auto mb-4">
              <Loader2 className="w-7 h-7 text-primary animate-spin" />
            </div>
          )}
          <h1 className="text-2xl font-semibold text-foreground mb-2">
            {isDone ? "Your library is ready!" : "Building your index"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {isDone
              ? "You can now search your photos using natural language."
              : "This may take a few minutes depending on your library size."}
          </p>
        </div>

        <Progress value={indexingStatus.progress} className="h-2 mb-4" />

        <div className="bg-card border border-border rounded-xl p-4 mb-6">
          <div className="flex items-center justify-center gap-2 mb-4">
            <span className="text-xs font-medium text-foreground">{phaseLabels[indexingStatus.phase]}</span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
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

          {indexingStatus.currentFile && (
            <p className="text-[10px] text-muted-foreground/60 mt-3 truncate">
              {indexingStatus.currentFile}
            </p>
          )}
        </div>

        <div className="flex items-center justify-center gap-3">
          {isDone ? (
            <Button onClick={completeOnboarding}>Start searching</Button>
          ) : (
            <>
              <Button variant="outline" onClick={runInBackground}>Run in background</Button>
              <Button variant="ghost" className="text-muted-foreground">Cancel</Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
