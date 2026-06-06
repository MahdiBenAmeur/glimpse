import { useEffect, useRef, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import { Loader2, X, Upload } from "lucide-react";
import { useApp } from "@/contexts/useApp";
import { uploadFaceSearchPhoto } from "@/lib/api";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentFilters: {
    folders: string[];
    dateRange: "any" | "today" | "last-7-days" | "last-30-days" | "this-year";
    facePresence: "any" | "faces" | "no-faces";
    people: Array<{ id: number; preference: "must_include" | "prefer" | "exclude" }>;
    facePhotoPath: string | null;
  };
  onApply: (filters: {
    labels: string[];
    folders: string[];
    dateRange: "any" | "today" | "last-7-days" | "last-30-days" | "this-year";
    facePresence: "any" | "faces" | "no-faces";
    people: Array<{ id: number; name: string; preference: "must_include" | "prefer" | "exclude" }>;
    facePhotoPath: string | null;
  }) => void;
}

export function AdvancedFiltersDrawer({ open, onOpenChange, currentFilters, onApply }: Props) {
  const { folders, people } = useApp();
  const facePhotoInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFolders, setSelectedFolders] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState("any");
  const [facePresence, setFacePresence] = useState("any");
  const [selectedPeople, setSelectedPeople] = useState<{ id: string; name: string; mode: string }[]>([]);
  const [facePhotoPath, setFacePhotoPath] = useState<string | null>(null);
  const [facePhotoName, setFacePhotoName] = useState<string | null>(null);
  const [isUploadingFacePhoto, setIsUploadingFacePhoto] = useState(false);

  useEffect(() => {
    if (!open) return;

    setSelectedFolders(currentFilters.folders);
    setDateRange(currentFilters.dateRange);
    setFacePresence(currentFilters.facePresence);
    setSelectedPeople(
      currentFilters.people.map((person) => ({
        id: String(person.id),
        name: people.find((candidate) => Number(candidate.id) === person.id)?.name ?? `Person ${person.id}`,
        mode: person.preference === "exclude" ? "Exclude" : person.preference === "prefer" ? "Prefer" : "Must include",
      })),
    );
    setFacePhotoPath(currentFilters.facePhotoPath);
    if (!currentFilters.facePhotoPath) {
      setFacePhotoName(null);
    }
  }, [currentFilters, open, people]);

  const handleApply = () => {
    const labels: string[] = [];
    selectedFolders.forEach(f => labels.push(`Folder: ${f.split("/").pop()}`));
    if (dateRange !== "any") labels.push(`Date: ${dateRange}`);
    if (facePresence !== "any") labels.push(facePresence === "faces" ? "Contains faces" : "No faces");
    selectedPeople.forEach(p => labels.push(`${p.mode}: ${p.name}`));
    if (facePhotoName) labels.push(`Face photo: ${facePhotoName}`);
    onApply({
      labels,
      folders: selectedFolders,
      dateRange: dateRange as "any" | "today" | "last-7-days" | "last-30-days" | "this-year",
      facePresence: facePresence as "any" | "faces" | "no-faces",
      people: selectedPeople.map((person) => ({
        id: Number(person.id),
        name: person.name,
        preference: person.mode === "Must include" ? "must_include" : person.mode === "Exclude" ? "exclude" : "prefer",
      })),
      facePhotoPath,
    });
  };

  const handleReset = () => {
    setSelectedFolders([]);
    setDateRange("any");
    setFacePresence("any");
    setSelectedPeople([]);
    setFacePhotoPath(null);
    setFacePhotoName(null);
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

  const handleFacePhotoFile = async (file: File | undefined) => {
    if (!file) return;
    setIsUploadingFacePhoto(true);
    try {
      const uploaded = await uploadFaceSearchPhoto(file);
      setFacePhotoPath(uploaded.path);
      setFacePhotoName(uploaded.filename || file.name);
    } finally {
      setIsUploadingFacePhoto(false);
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
            <div
              className="border border-dashed border-border rounded-lg p-6 flex flex-col items-center gap-2"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                void handleFacePhotoFile(event.dataTransfer.files?.[0]);
              }}
            >
              {isUploadingFacePhoto ? (
                <Loader2 className="w-5 h-5 text-muted-foreground animate-spin" />
              ) : (
                <Upload className="w-5 h-5 text-muted-foreground" />
              )}
              <p className="text-xs text-muted-foreground">
                {facePhotoName ? facePhotoName : "Upload a photo to find matching faces"}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs h-7"
                  disabled={isUploadingFacePhoto}
                  onClick={() => facePhotoInputRef.current?.click()}
                >
                  Choose photo
                </Button>
                {facePhotoPath && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs h-7"
                    onClick={() => {
                      setFacePhotoPath(null);
                      setFacePhotoName(null);
                    }}
                  >
                    Remove
                  </Button>
                )}
              </div>
              <input
                ref={facePhotoInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => {
                  void handleFacePhotoFile(event.target.files?.[0]);
                  event.currentTarget.value = "";
                }}
              />
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
