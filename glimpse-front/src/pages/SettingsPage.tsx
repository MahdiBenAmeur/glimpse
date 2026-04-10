import { useState } from "react";
import { useTheme } from "@/contexts/ThemeContext";
import { Download, Check, Loader2, Trash2, AlertTriangle, HardDrive, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { useApp } from "@/contexts/AppContext";

const tabs = ["General", "Models", "Storage", "Indexing", "Interface"];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("General");

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold text-foreground mb-6">Settings</h1>

      <div className="flex gap-6">
        <nav className="w-40 shrink-0 space-y-0.5">
          {tabs.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                activeTab === tab
                  ? "bg-accent text-accent-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>

        <div className="flex-1 max-w-2xl">
          {activeTab === "General" && <GeneralSettings />}
          {activeTab === "Models" && <ModelsSettings />}
          {activeTab === "Storage" && <StorageSettings />}
          {activeTab === "Indexing" && <IndexingSettings />}
          {activeTab === "Interface" && <InterfaceSettings />}
        </div>
      </div>
    </div>
  );
}

function GeneralSettings() {
  return (
    <div className="space-y-6">
      <h2 className="text-base font-medium text-foreground">General</h2>
      <SettingRow label="Launch on startup" description="Open Glimpse One when you log in">
        <Switch />
      </SettingRow>
      <SettingRow label="Remember last page" description="Return to the last visited page on launch">
        <Switch defaultChecked />
      </SettingRow>
      <SettingRow label="Confirm destructive actions" description="Ask for confirmation before deleting">
        <Switch defaultChecked />
      </SettingRow>
      <SettingRow label="Double-click behavior" description="What happens when you double-click a result">
        <Select defaultValue="viewer">
          <SelectTrigger className="w-44 h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="viewer">Open in viewer</SelectItem>
            <SelectItem value="external">Open externally</SelectItem>
          </SelectContent>
        </Select>
      </SettingRow>
    </div>
  );
}

function ModelsSettings() {
  const { models, activeModel, downloadModel, setActiveModel, removeModel } = useApp();
  const [switchDialog, setSwitchDialog] = useState<string | null>(null);

  const handleSwitch = (id: string) => {
    if (activeModel) {
      setSwitchDialog(id);
    } else {
      setActiveModel(id);
    }
  };

  const confirmSwitch = () => {
    if (switchDialog) {
      setActiveModel(switchDialog);
      setSwitchDialog(null);
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-base font-medium text-foreground">Models</h2>

      {activeModel && (
        <div className="bg-accent border border-border rounded-xl p-4">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Active Model</p>
          <p className="text-sm font-medium text-foreground">{activeModel.name}</p>
          <p className="text-xs text-muted-foreground">{activeModel.description}</p>
        </div>
      )}

      <div className="space-y-3">
        {models.map(model => (
          <div key={model.id} className={`border rounded-xl p-4 transition-colors ${model.status === "active" ? "border-primary bg-accent" : "border-border bg-card"}`}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-medium text-sm text-foreground">{model.name}</h3>
                  {model.status === "active" && <Badge className="bg-primary text-primary-foreground text-[10px]">Active</Badge>}
                </div>
                <p className="text-xs text-muted-foreground">{model.description}</p>
                <div className="flex items-center gap-3 text-[10px] text-muted-foreground mt-1">
                  <span>{model.diskSize}</span>
                  <span>•</span>
                  <span>{model.quality} quality</span>
                  <span>•</span>
                  <span>{model.speed} speed</span>
                </div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {model.status === "not_installed" && (
                  <Button size="sm" variant="outline" className="text-xs h-8" onClick={() => downloadModel(model.id)}>
                    <Download className="w-3 h-3 mr-1.5" /> Download
                  </Button>
                )}
                {model.status === "downloading" && (
                  <Button size="sm" variant="outline" className="text-xs h-8" disabled>
                    <Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> {model.downloadProgress}%
                  </Button>
                )}
                {model.status === "installed" && (
                  <>
                    <Button size="sm" className="text-xs h-8" onClick={() => handleSwitch(model.id)}>
                      <Check className="w-3 h-3 mr-1.5" /> Use
                    </Button>
                    <Button size="sm" variant="ghost" className="h-8 text-destructive hover:text-destructive" onClick={() => removeModel(model.id)}>
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </>
                )}
              </div>
            </div>
            {model.status === "downloading" && <Progress value={model.downloadProgress} className="mt-3 h-1.5" />}
          </div>
        ))}
      </div>

      <Dialog open={!!switchDialog} onOpenChange={() => setSwitchDialog(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-base">Switch model?</DialogTitle>
            <DialogDescription className="text-xs">
              Switching models changes the embedding space. Your current index will need to be rebuilt for best results.
            </DialogDescription>
          </DialogHeader>
          <div className="bg-warning/10 border border-warning/30 rounded-lg p-3 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-warning shrink-0 mt-0.5" />
            <p className="text-xs text-foreground">Search quality may be degraded until you rebuild the index.</p>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSwitchDialog(null)}>Cancel</Button>
            <Button variant="outline" size="sm" onClick={confirmSwitch}>Switch, rebuild later</Button>
            <Button size="sm" onClick={() => { confirmSwitch(); }}>Switch & rebuild now</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function StorageSettings() {
  return (
    <div className="space-y-6">
      <h2 className="text-base font-medium text-foreground">Storage</h2>
      <div className="space-y-4">
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <HardDrive className="w-4 h-4 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium text-foreground">Index storage</p>
              <p className="text-xs text-muted-foreground">~/.glimpse-one/index/</p>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">142 MB used</p>
        </div>
        <div className="bg-card border border-border rounded-xl p-4">
          <div className="flex items-center gap-3 mb-2">
            <FolderOpen className="w-4 h-4 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium text-foreground">Thumbnail cache</p>
              <p className="text-xs text-muted-foreground">~/.glimpse-one/thumbnails/</p>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">89 MB used</p>
            <Button variant="outline" size="sm" className="text-xs h-7">Clear cache</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function IndexingSettings() {
  return (
    <div className="space-y-6">
      <h2 className="text-base font-medium text-foreground">Indexing</h2>
      <SettingRow label="Include subfolders by default" description="Scan subdirectories when adding new folders">
        <Switch defaultChecked />
      </SettingRow>
      <SettingRow label="Skip hidden folders" description="Ignore folders starting with a dot">
        <Switch defaultChecked />
      </SettingRow>
      <SettingRow label="Face detection" description="Detect and index faces in your photos">
        <Switch defaultChecked />
      </SettingRow>
      <Separator />
      <div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Supported file types</p>
        <div className="flex flex-wrap gap-1.5">
          {["JPG", "JPEG", "PNG", "WEBP", "HEIC", "TIFF", "BMP", "GIF"].map(type => (
            <Badge key={type} variant="secondary" className="text-[10px]">{type}</Badge>
          ))}
        </div>
      </div>
    </div>
  );
}

function InterfaceSettings() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="space-y-6">
      <h2 className="text-base font-medium text-foreground">Interface</h2>
      <SettingRow label="Theme" description="Choose your preferred appearance">
        <Select value={theme} onValueChange={(v) => setTheme(v as "system" | "light" | "dark")}>
          <SelectTrigger className="w-32 h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="system">System</SelectItem>
            <SelectItem value="light">Light</SelectItem>
            <SelectItem value="dark">Dark</SelectItem>
          </SelectContent>
        </Select>
      </SettingRow>
      <SettingRow label="Compact sidebar" description="Use a narrower sidebar by default">
        <Switch />
      </SettingRow>
      <SettingRow label="Thumbnail density" description="Adjust how many images appear per row">
        <Select defaultValue="comfortable">
          <SelectTrigger className="w-32 h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="comfortable">Comfortable</SelectItem>
            <SelectItem value="compact">Compact</SelectItem>
          </SelectContent>
        </Select>
      </SettingRow>
    </div>
  );
}

function SettingRow({ label, description, children }: { label: string; description: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1">
      <div>
        <p className="text-sm text-foreground">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      {children}
    </div>
  );
}
