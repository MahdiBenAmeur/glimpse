import { useEffect, useState } from "react";
import { Database, FolderOpen, Users, Image, Clock, HardDrive, RefreshCw, Plus, Trash2, AlertTriangle, ImagePlus, XCircle, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useApp } from "@/contexts/useApp";
import { getStorageSummary } from "@/lib/api";

export default function IndexPage() {
  const {
    folders,
    activeModel,
    lastIndexedTime,
    totalIndexedImages,
    people,
    indexingStatus,
    startIndexing,
    cancelIndexing,
    removeFolder,
    addFolder,
    addPhotos,
  } = useApp();
  const [indexSizeLabel, setIndexSizeLabel] = useState("0 B");

  const isIndexing = indexingStatus.phase !== "idle" && indexingStatus.phase !== "complete" && indexingStatus.phase !== "cancelled";
  const isCancelling = indexingStatus.phase === "cancelling";
  const isClustering = indexingStatus.phase === "clustering";
  const isVideoKeyframes = indexingStatus.phase === "video_keyframes";
  const handleReindexFolder = (folderId: string) => void startIndexing({ folderIds: [folderId], resetIndex: false });

  useEffect(() => {
    let cancelled = false;

    const loadStorage = async () => {
      try {
        const summary = await getStorageSummary();
        if (!cancelled) {
          setIndexSizeLabel(formatBytes(summary.indexSizeBytes));
        }
      } catch {
        if (!cancelled) {
          setIndexSizeLabel("Unavailable");
        }
      }
    };

    void loadStorage();
    return () => {
      cancelled = true;
    };
  }, [folders.length, totalIndexedImages, indexingStatus.phase]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-foreground">Index</h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="text-xs h-8 gap-1.5" onClick={() => void addFolder()}>
            <Plus className="w-3 h-3" /> Add folder path
          </Button>
          <Button variant="outline" size="sm" className="text-xs h-8 gap-1.5" onClick={() => void addPhotos()}>
            <ImagePlus className="w-3 h-3" /> Add photos
          </Button>
          <Button size="sm" className="text-xs h-8 gap-1.5" onClick={() => void startIndexing({ resetIndex: true })} disabled={isIndexing}>
            <RefreshCw className={`w-3 h-3 ${isIndexing ? "animate-spin" : ""}`} /> Reindex now
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
        <SummaryCard icon={Image} label="Images" value={totalIndexedImages.toLocaleString()} />
        <SummaryCard icon={Users} label="People" value={String(people.length)} />
        <SummaryCard icon={FolderOpen} label="Folders" value={String(folders.length)} />
        <SummaryCard icon={Database} label="Model" value={activeModel?.name || "None"} />
        <SummaryCard icon={Clock} label="Last indexed" value={lastIndexedTime ? new Date(lastIndexedTime).toLocaleDateString() : "Never"} />
        <SummaryCard icon={HardDrive} label="Index size" value={indexSizeLabel} />
      </div>

      {isIndexing && (
        <div className="bg-accent border border-border rounded-xl p-4 mb-6">
          <div className="flex items-center gap-2 mb-2">
            {isClustering || isVideoKeyframes ? (
              <Loader2 className="w-4 h-4 text-primary animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4 text-primary animate-spin" />
            )}
            <span className="text-sm font-medium text-foreground">
              {isCancelling ? "Cancelling indexing..." : isClustering ? "Clustering faces..." : isVideoKeyframes ? "Extracting keyframes..." : "Indexing in progress..."}
            </span>
            <Badge variant="secondary" className="text-[10px]">{indexingStatus.progress}%</Badge>
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto h-7 gap-1 text-xs text-muted-foreground"
              onClick={() => void cancelIndexing()}
              disabled={isCancelling}
            >
              <XCircle className="w-3 h-3" /> {isCancelling ? "Cancelling" : "Cancel"}
            </Button>
          </div>
          <div className="w-full h-1.5 bg-border rounded-full overflow-hidden">
            <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${indexingStatus.progress}%` }} />
          </div>
          <p className="text-[10px] text-muted-foreground mt-2">
            {isClustering
              ? `We are clustering ${indexingStatus.facesDetected.toLocaleString()} detected faces into people.`
              : isVideoKeyframes
                ? `${indexingStatus.processed.toLocaleString()} / ${indexingStatus.total.toLocaleString()} videos`
                : `${indexingStatus.processed.toLocaleString()} / ${indexingStatus.total.toLocaleString()} files - ${indexingStatus.facesDetected} faces detected`}
          </p>
          {isVideoKeyframes && indexingStatus.currentFile && (
            <p className="text-[10px] text-muted-foreground/60 mt-1 truncate">{indexingStatus.currentFile}</p>
          )}
        </div>
      )}

      <div>
        <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Indexed Folders</h2>
        {folders.length === 0 ? (
          <div className="bg-card border border-border rounded-xl p-8 text-center">
            <FolderOpen className="w-8 h-8 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">No folders indexed yet.</p>
          </div>
        ) : (
          <div className="bg-card border border-border rounded-xl overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Path</th>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Images</th>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Last scan</th>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Status</th>
                  <th className="text-right px-4 py-2.5 font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {folders.map((folder) => (
                  <tr key={folder.id} className="border-b border-border last:border-0 hover:bg-muted/30">
                    <td className="px-4 py-3 text-foreground truncate max-w-[300px]">{folder.path}</td>
                    <td className="px-4 py-3 text-muted-foreground">{folder.imageCount.toLocaleString()}</td>
                    <td className="px-4 py-3 text-muted-foreground">{folder.lastScanTime ? new Date(folder.lastScanTime).toLocaleDateString() : "Never"}</td>
                    <td className="px-4 py-3">
                      <Badge variant={folder.status === "ready" ? "secondary" : folder.status === "scanning" ? "default" : "destructive"} className="text-[10px]">
                        {folder.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => handleReindexFolder(folder.id)} disabled={isIndexing}>
                          <RefreshCw className="w-3 h-3" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive hover:text-destructive" onClick={() => void removeFolder(folder.id)}>
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {indexingStatus.error && !isIndexing && (
        <div className="bg-destructive/10 border border-destructive/30 rounded-xl p-4 mb-6 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground">Indexing failed</p>
            <p className="text-xs text-muted-foreground mt-1">{indexingStatus.error}</p>
          </div>
          <Button variant="outline" size="sm" className="text-xs h-8 shrink-0" onClick={() => void startIndexing({ resetIndex: true })}>
            Retry
          </Button>
        </div>
      )}

      {!activeModel && (
        <div className="mt-6 bg-warning/10 border border-warning/30 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-warning shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-foreground">No model selected</p>
            <p className="text-xs text-muted-foreground">Go to Settings -&gt; Models to download and activate a model.</p>
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string }) {
  return (
    <div className="bg-card border border-border rounded-xl p-3.5">
      <Icon className="w-4 h-4 text-muted-foreground mb-2" />
      <p className="text-lg font-semibold text-foreground leading-tight">{value}</p>
      <p className="text-[10px] text-muted-foreground">{label}</p>
    </div>
  );
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value >= 10 || unitIndex === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unitIndex]}`;
}
