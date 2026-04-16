import { Database, FolderOpen, Users, Image, Clock, HardDrive, RefreshCw, Plus, Trash2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useApp } from "@/contexts/AppContext";
import { useFolders, useRemoveFolder } from "@/hooks/api/useFolders";
import { usePeople } from "@/hooks/api/usePeople";

export default function IndexPage() {
  const { activeModel, lastIndexedTime, totalIndexedImages, indexingStatus, startIndexing } = useApp();
  const { data: folders = [] } = useFolders();
  const { data: people = [] } = usePeople();
  const { mutate: removeFolder } = useRemoveFolder();

  const isIndexing = indexingStatus.phase !== "idle" && indexingStatus.phase !== "complete";

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-foreground">Index</h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="text-xs h-8 gap-1.5">
            <Plus className="w-3 h-3" /> Add folder
          </Button>
          <Button size="sm" className="text-xs h-8 gap-1.5" onClick={startIndexing} disabled={isIndexing}>
            <RefreshCw className={`w-3 h-3 ${isIndexing ? "animate-spin" : ""}`} /> Reindex now
          </Button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
        <SummaryCard icon={Image} label="Images" value={totalIndexedImages.toLocaleString()} />
        <SummaryCard icon={Users} label="People" value={String(people.length)} />
        <SummaryCard icon={FolderOpen} label="Folders" value={String(folders.length)} />
        <SummaryCard icon={Database} label="Model" value={activeModel?.name || "None"} />
        <SummaryCard icon={Clock} label="Last indexed" value={lastIndexedTime ? new Date(lastIndexedTime).toLocaleDateString() : "Never"} />
        <SummaryCard icon={HardDrive} label="Index size" value="142 MB" />
      </div>

      {/* Indexing progress */}
      {isIndexing && (
        <div className="bg-accent border border-border rounded-xl p-4 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <RefreshCw className="w-4 h-4 text-primary animate-spin" />
            <span className="text-sm font-medium text-foreground">Indexing in progress...</span>
            <Badge variant="secondary" className="text-[10px]">{indexingStatus.progress}%</Badge>
          </div>
          <div className="w-full h-1.5 bg-border rounded-full overflow-hidden">
            <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${indexingStatus.progress}%` }} />
          </div>
          <p className="text-[10px] text-muted-foreground mt-2">
            {indexingStatus.processed.toLocaleString()} / {indexingStatus.total.toLocaleString()} files • {indexingStatus.facesDetected} faces detected
          </p>
        </div>
      )}

      {/* Folders table */}
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
                {folders.map(f => (
                  <tr key={f.id} className="border-b border-border last:border-0 hover:bg-muted/30">
                    <td className="px-4 py-3 text-foreground truncate max-w-[300px]">{f.path}</td>
                    <td className="px-4 py-3 text-muted-foreground">{f.imageCount.toLocaleString()}</td>
                    <td className="px-4 py-3 text-muted-foreground">{new Date(f.lastScanTime).toLocaleDateString()}</td>
                    <td className="px-4 py-3">
                      <Badge variant={f.status === "ready" ? "secondary" : f.status === "scanning" ? "default" : "destructive"} className="text-[10px]">
                        {f.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="icon" className="h-6 w-6">
                          <RefreshCw className="w-3 h-3" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive hover:text-destructive" onClick={() => removeFolder(f.id)}>
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

      {/* Warnings */}
      {!activeModel && (
        <div className="mt-6 bg-warning/10 border border-warning/30 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-warning shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-foreground">No model selected</p>
            <p className="text-xs text-muted-foreground">Go to Settings → Models to download and activate a model.</p>
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
