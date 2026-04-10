import React, { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import { MOCK_MODELS, MOCK_FOLDERS, MOCK_PEOPLE, MOCK_IMAGES, MOCK_COLLECTIONS, MOCK_SAVED_SEARCHES, type ModelInfo, type FolderInfo, type PersonInfo, type ImageResult, type CollectionInfo, type SavedSearch } from "@/data/mockData";

type IndexingPhase = "idle" | "scanning" | "embeddings" | "faces" | "thumbnails" | "writing" | "complete";

interface IndexingStatus {
  phase: IndexingPhase;
  progress: number;
  total: number;
  processed: number;
  facesDetected: number;
  skipped: number;
  currentFile?: string;
}

interface AppState {
  isFirstLaunch: boolean;
  onboardingStep: number;
  models: ModelInfo[];
  activeModel: ModelInfo | null;
  folders: FolderInfo[];
  people: PersonInfo[];
  images: ImageResult[];
  collections: CollectionInfo[];
  savedSearches: SavedSearch[];
  indexingStatus: IndexingStatus;
  lastIndexedTime: string | null;
  totalIndexedImages: number;
}

interface AppContextType extends AppState {
  setOnboardingStep: (step: number) => void;
  completeOnboarding: () => void;
  downloadModel: (id: string) => void;
  setActiveModel: (id: string) => void;
  removeModel: (id: string) => void;
  addFolder: (path: string) => void;
  removeFolder: (id: string) => void;
  startIndexing: () => void;
  runInBackground: () => void;
  toggleFavorite: (imageId: string) => void;
  renamePerson: (personId: string, name: string) => void;
  createCollection: (name: string, description?: string) => void;
  deleteCollection: (id: string) => void;
  saveSearch: (name: string, query: string, filters: Record<string, unknown>) => void;
  deleteSavedSearch: (id: string) => void;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState>(() => {
    const saved = localStorage.getItem("glimpse-one-state");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        return { ...getDefaultState(), ...parsed, models: MOCK_MODELS.map(m => {
          const savedModel = parsed.models?.find((sm: ModelInfo) => sm.id === m.id);
          return savedModel || m;
        })};
      } catch { /* ignore */ }
    }
    return getDefaultState();
  });

  function getDefaultState(): AppState {
    return {
      isFirstLaunch: true,
      onboardingStep: 0,
      models: MOCK_MODELS,
      activeModel: null,
      folders: [],
      people: [],
      images: [],
      collections: [],
      savedSearches: [],
      indexingStatus: { phase: "idle", progress: 0, total: 0, processed: 0, facesDetected: 0, skipped: 0 },
      lastIndexedTime: null,
      totalIndexedImages: 0,
    };
  }

  const persist = useCallback((newState: AppState) => {
    localStorage.setItem("glimpse-one-state", JSON.stringify({
      isFirstLaunch: newState.isFirstLaunch,
      onboardingStep: newState.onboardingStep,
      models: newState.models,
      activeModel: newState.activeModel,
      lastIndexedTime: newState.lastIndexedTime,
      totalIndexedImages: newState.totalIndexedImages,
    }));
  }, []);

  const update = useCallback((partial: Partial<AppState>) => {
    setState(prev => {
      const next = { ...prev, ...partial };
      persist(next);
      return next;
    });
  }, [persist]);

  const downloadModel = useCallback((id: string) => {
    setState(prev => {
      const models = prev.models.map(m => m.id === id ? { ...m, status: "downloading" as const, downloadProgress: 0 } : m);
      const next = { ...prev, models };
      persist(next);
      return next;
    });
    // Simulate download
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 15 + 5;
      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);
        setState(prev => {
          const models = prev.models.map(m => m.id === id ? { ...m, status: "installed" as const, downloadProgress: 100 } : m);
          const next = { ...prev, models };
          persist(next);
          return next;
        });
      } else {
        setState(prev => {
          const models = prev.models.map(m => m.id === id ? { ...m, downloadProgress: Math.round(progress) } : m);
          return { ...prev, models };
        });
      }
    }, 500);
  }, [persist]);

  const setActiveModel = useCallback((id: string) => {
    setState(prev => {
      const models = prev.models.map(m => ({ ...m, status: (m.id === id ? "active" : m.status === "active" ? "installed" : m.status) as ModelInfo["status"] }));
      const activeModel = models.find(m => m.id === id) || null;
      const next = { ...prev, models, activeModel };
      persist(next);
      return next;
    });
  }, [persist]);

  const removeModel = useCallback((id: string) => {
    setState(prev => {
      const models = prev.models.map(m => m.id === id ? { ...m, status: "not_installed" as const, downloadProgress: undefined } : m);
      const activeModel = prev.activeModel?.id === id ? null : prev.activeModel;
      const next = { ...prev, models, activeModel };
      persist(next);
      return next;
    });
  }, [persist]);

  const addFolder = useCallback((path: string) => {
    const newFolder: FolderInfo = {
      id: `f-${Date.now()}`,
      path,
      imageCount: 0,
      lastScanTime: "",
      status: "ready",
      includeSubfolders: true,
    };
    setState(prev => ({ ...prev, folders: [...prev.folders, newFolder] }));
  }, []);

  const removeFolder = useCallback((id: string) => {
    setState(prev => ({ ...prev, folders: prev.folders.filter(f => f.id !== id) }));
  }, []);

  const startIndexing = useCallback(() => {
    update({
      indexingStatus: { phase: "scanning", progress: 0, total: 4506, processed: 0, facesDetected: 0, skipped: 0, currentFile: "Scanning folders..." },
    });
    const phases: IndexingPhase[] = ["scanning", "embeddings", "faces", "thumbnails", "writing", "complete"];
    let phaseIdx = 0;
    let processed = 0;
    const total = 4506;
    const interval = setInterval(() => {
      processed += Math.floor(Math.random() * 200 + 100);
      if (processed >= total * ((phaseIdx + 1) / (phases.length - 1))) {
        phaseIdx++;
        if (phaseIdx >= phases.length - 1) {
          clearInterval(interval);
          update({
            indexingStatus: { phase: "complete", progress: 100, total, processed: total, facesDetected: 847, skipped: 23, currentFile: undefined },
            images: MOCK_IMAGES,
            people: MOCK_PEOPLE,
            folders: MOCK_FOLDERS,
            collections: MOCK_COLLECTIONS,
            savedSearches: MOCK_SAVED_SEARCHES,
            lastIndexedTime: new Date().toISOString(),
            totalIndexedImages: total,
          });
          return;
        }
      }
      const progress = Math.min(100, Math.round((processed / total) * 100));
      setState(prev => ({
        ...prev,
        indexingStatus: {
          phase: phases[phaseIdx],
          progress,
          total,
          processed: Math.min(processed, total),
          facesDetected: Math.floor(processed * 0.19),
          skipped: Math.floor(processed * 0.005),
          currentFile: `IMG_${2000 + (processed % 500)}.jpg`,
        },
      }));
    }, 300);
  }, [update]);

  const runInBackground = useCallback(() => {
    update({ isFirstLaunch: false, onboardingStep: 3 });
  }, [update]);

  const completeOnboarding = useCallback(() => {
    update({ isFirstLaunch: false, onboardingStep: 3 });
  }, [update]);

  const toggleFavorite = useCallback((imageId: string) => {
    setState(prev => ({
      ...prev,
      images: prev.images.map(img => img.id === imageId ? { ...img, isFavorite: !img.isFavorite } : img),
    }));
  }, []);

  const renamePerson = useCallback((personId: string, name: string) => {
    setState(prev => ({
      ...prev,
      people: prev.people.map(p => p.id === personId ? { ...p, name } : p),
    }));
  }, []);

  const createCollection = useCallback((name: string, description?: string) => {
    const newCol: CollectionInfo = {
      id: `c-${Date.now()}`,
      name,
      description,
      imageCount: 0,
      previewUrls: [],
      modifiedDate: new Date().toISOString().split("T")[0],
    };
    setState(prev => ({ ...prev, collections: [...prev.collections, newCol] }));
  }, []);

  const deleteCollection = useCallback((id: string) => {
    setState(prev => ({ ...prev, collections: prev.collections.filter(c => c.id !== id) }));
  }, []);

  const saveSearch = useCallback((name: string, query: string, filters: Record<string, unknown>) => {
    const newSS: SavedSearch = {
      id: `ss-${Date.now()}`,
      name,
      query,
      filters,
      lastUsed: new Date().toISOString().split("T")[0],
    };
    setState(prev => ({ ...prev, savedSearches: [...prev.savedSearches, newSS] }));
  }, []);

  const deleteSavedSearch = useCallback((id: string) => {
    setState(prev => ({ ...prev, savedSearches: prev.savedSearches.filter(s => s.id !== id) }));
  }, []);

  return (
    <AppContext.Provider value={{
      ...state,
      setOnboardingStep: (step) => update({ onboardingStep: step }),
      completeOnboarding,
      downloadModel,
      setActiveModel,
      removeModel,
      addFolder,
      removeFolder,
      startIndexing,
      runInBackground,
      toggleFavorite,
      renamePerson,
      createCollection,
      deleteCollection,
      saveSearch,
      deleteSavedSearch,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
