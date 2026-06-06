import { Download, Check, Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { useApp } from "@/contexts/useApp";

export default function ModelSetupPage() {
  const { models, activeModel, downloadModel, setActiveModel, removeModel, setOnboardingStep, isWorking } = useApp();
  const hasActive = models.some(m => m.status === "active");

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-8">
      <div className="max-w-2xl w-full">
        <div className="text-center mb-8">
          <img src="/logo.png" alt="Glimpse logo" className="w-24 h-24 rounded-2xl object-contain mx-auto mb-4" />
          <h1 className="text-2xl font-semibold text-foreground mb-2">Welcome to Glimpse One</h1>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            Glimpse One runs entirely on your computer. Choose a model to enable natural language image search.
          </p>
        </div>

        <div className="space-y-3 mb-8">
          {models.length === 0 && (
            <div className="border border-dashed border-border rounded-xl p-6 text-center bg-card">
              <p className="text-sm text-foreground mb-1">No models loaded yet</p>
              <p className="text-xs text-muted-foreground">Check that the backend is running and the model list endpoint is available.</p>
            </div>
          )}
          {models.map(model => (
            <div
              key={model.id}
              className={`border rounded-xl p-4 transition-colors ${model.status === "active"
                ? "border-primary bg-accent"
                : "border-border bg-card hover:border-primary/30"
                }`}
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
                    <Button size="sm" variant="outline" className="text-xs h-8" onClick={() => void downloadModel(model.id)} disabled={isWorking}>
                      <Download className="w-3 h-3 mr-1.5" /> Download
                    </Button>
                  )}
                  {model.status === "downloading" && (
                    <Button size="sm" variant="outline" className="text-xs h-8" disabled>
                      <Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> {model.downloadProgress}%
                    </Button>
                  )}
                  {model.status === "installed" && (
                    <Button size="sm" className="text-xs h-8" onClick={() => void setActiveModel(model.id)} disabled={isWorking}>
                      <Check className="w-3 h-3 mr-1.5" /> Use this model
                    </Button>
                  )}
                  {(model.status === "installed" || model.status === "active") && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs h-8 text-destructive hover:text-destructive"
                      onClick={() => void removeModel(model.id)}
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

        <div className="flex items-center justify-between">
          <p className="text-[10px] text-muted-foreground">
            {activeModel ? `Selected: ${activeModel.name}` : "All data stays on your device."}
          </p>
          <Button
            disabled={!hasActive}
            onClick={() => setOnboardingStep(1)}
          >
            Continue
          </Button>
        </div>
      </div>
    </div>
  );
}
