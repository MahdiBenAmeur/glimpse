import { useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { X, Upload } from "lucide-react";
import { useApp } from "@/contexts/AppContext";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApply: (filters: string[]) => void;
}

export function AdvancedFiltersDrawer({ open, onOpenChange, onApply }: Props) {
  const { folders, people } = useApp();
  const [selectedFolders, setSelectedFolders] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState("any");
  const [facePresence, setFacePresence] = useState("any");
  const [selectedPeople, setSelectedPeople] = useState<{ id: string; name: string; mode: string }[]>([]);

  const handleApply = () => {
    const filters: string[] = [];
    selectedFolders.forEach(f => filters.push(`Folder: ${f.split("/").pop()}`));
    if (dateRange !== "any") filters.push(`Date: ${dateRange}`);
    if (facePresence !== "any") filters.push(facePresence === "faces" ? "Contains faces" : "No faces");
    selectedPeople.forEach(p => filters.push(`${p.mode}: ${p.name}`));
    onApply(filters);
  };

  const handleReset = () => {
    setSelectedFolders([]);
    setDateRange("any");
    setFacePresence("any");
    setSelectedPeople([]);
  };

  const toggleFolder = (path: string) => {
    setSelectedFolders(prev =>
      prev.includes(path) ? prev.filter(f => f !== path) : [...prev, path]
    );
  };

  const addPerson = (person: { id: string; name: string }) => {
    if (!selectedPeople.find(p => p.id === person.id)) {
      setSelectedPeople(prev => [...prev, { ...person, mode: "Must include" }]);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[380px] sm:max-w-[380px] flex flex-col">
        <SheetHeader>
          <SheetTitle className="text-base">Advanced Filters</SheetTitle>
        </SheetHeader>

        <div className="flex-1 overflow-auto space-y-6 py-4">
          {/* Folder filter */}
          <div>
            <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 block">Folder</Label>
            <div className="space-y-1.5">
              {folders.length > 0 ? folders.map(f => (
                <button
                  key={f.id}
                  onClick={() => toggleFolder(f.path)}
                  className={`w-full text-left px-3 py-2 rounded-md text-xs transition-colors ${selectedFolders.includes(f.path) ? "bg-accent text-accent-foreground" : "hover:bg-muted"}`}
                >
                  {f.path.split("/").slice(-2).join("/")}
                </button>
              )) : (
                <p className="text-xs text-muted-foreground">No folders indexed</p>
              )}
            </div>
          </div>

          <Separator />

          {/* Date filter */}
          <div>
            <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 block">Date</Label>
            <RadioGroup value={dateRange} onValueChange={setDateRange} className="space-y-1.5">
              {["any", "Today", "Last 7 days", "Last 30 days", "This year"].map(option => (
                <div key={option} className="flex items-center gap-2">
                  <RadioGroupItem value={option.toLowerCase().replace(/ /g, "-")} id={`date-${option}`} />
                  <Label htmlFor={`date-${option}`} className="text-xs font-normal">{option === "any" ? "Any time" : option}</Label>
                </div>
              ))}
            </RadioGroup>
          </div>

          <Separator />

          {/* Face presence */}
          <div>
            <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 block">Face Presence</Label>
            <RadioGroup value={facePresence} onValueChange={setFacePresence} className="space-y-1.5">
              {[{ value: "any", label: "Any" }, { value: "faces", label: "Contains faces" }, { value: "no-faces", label: "No faces" }].map(opt => (
                <div key={opt.value} className="flex items-center gap-2">
                  <RadioGroupItem value={opt.value} id={`face-${opt.value}`} />
                  <Label htmlFor={`face-${opt.value}`} className="text-xs font-normal">{opt.label}</Label>
                </div>
              ))}
            </RadioGroup>
          </div>

          <Separator />

          {/* People filter */}
          <div>
            <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 block">People</Label>
            {selectedPeople.length > 0 && (
              <div className="space-y-2 mb-3">
                {selectedPeople.map(p => (
                  <div key={p.id} className="flex items-center gap-2 bg-muted rounded-md px-2.5 py-1.5">
                    <span className="text-xs flex-1">{p.name}</span>
                    <select
                      value={p.mode}
                      onChange={e => setSelectedPeople(prev => prev.map(pp => pp.id === p.id ? { ...pp, mode: e.target.value } : pp))}
                      className="text-[10px] bg-card border border-border rounded px-1 py-0.5"
                    >
                      <option>Must include</option>
                      <option>Prefer</option>
                      <option>Exclude</option>
                    </select>
                    <button onClick={() => setSelectedPeople(prev => prev.filter(pp => pp.id !== p.id))}>
                      <X className="w-3 h-3 text-muted-foreground" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="space-y-1">
              {people.filter(p => p.name && !selectedPeople.find(sp => sp.id === p.id)).map(p => (
                <button
                  key={p.id}
                  onClick={() => addPerson({ id: p.id, name: p.name! })}
                  className="flex items-center gap-2 w-full px-2.5 py-1.5 rounded-md text-xs hover:bg-muted transition-colors"
                >
                  <img src={p.faceUrl} alt="" className="w-5 h-5 rounded-full object-cover" />
                  <span>{p.name}</span>
                  <span className="text-muted-foreground ml-auto">{p.imageCount}</span>
                </button>
              ))}
            </div>
          </div>

          <Separator />

          {/* Face photo search */}
          <div>
            <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 block">Face Photo Search</Label>
            <div className="border border-dashed border-border rounded-lg p-6 flex flex-col items-center gap-2">
              <Upload className="w-5 h-5 text-muted-foreground" />
              <p className="text-xs text-muted-foreground">Upload a photo to find matching faces</p>
              <Button variant="outline" size="sm" className="text-xs h-7">Choose photo</Button>
            </div>
          </div>
        </div>

        <SheetFooter className="flex-row gap-2 border-t border-border pt-4">
          <Button variant="ghost" size="sm" onClick={handleReset} className="text-xs">Reset</Button>
          <div className="flex-1" />
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} className="text-xs">Cancel</Button>
          <Button size="sm" onClick={handleApply} className="text-xs">Apply</Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
