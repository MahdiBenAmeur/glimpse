import React, { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { MOCK_MODELS, type ModelInfo, type FolderInfo, type PersonInfo, type ImageResult, type CollectionInfo, type SavedSearch } from "@/data/mockData";

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
  indexingStatus: IndexingStatus;
  lastIndexedTime: string | null;
  totalIndexedImages: number;
}

interface AppContextType extends AppState {
  // Remote Data
  folders: FolderInfo[];
  people: PersonInfo[];
  images: ImageResult[];
  collections: CollectionInfo[];
  savedSearches: SavedSearch[];
  
  // UI & System State
  setOnboardingStep: (step: number) => void;
  completeOnboarding: () => void;
  downloadModel: (id: string) => void;
  setActiveModel: (id: string) => void;
  removeModel: (id: string) => void;
  startIndexing: () => void;
  runInBackground: () => void;

  // Remote Mutations
  addFolder: (path: string) => void;
  removeFolder: (id: string) => void;
  toggleFavorite: (imageId: string) => void;
  renamePerson: (personId: string, name: string) => void;
  createCollection: (name: string, description?: string) => void;
  deleteCollection: (id: string) => void;
  saveSearch: (name: string, query: string, filters: Record<string, unknown>) => void;
  deleteSavedSearch: (id: string) => void;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();

  // 1. Remote Data Fetching (Live from Backend)
  const { data: images = [] } = useQuery({ queryKey: ["images"], queryFn: () => api.images.getAll() as Promise<ImageResult[]> });
  const { data: folders = [] } = useQuery({ queryKey: ["folders"], queryFn: () => api.folders.getAll() as Promise<FolderInfo[]> });
  const { data: collections = [] } = useQuery({ queryKey: ["collections"], queryFn: () => api.collections.getAll() as Promise<CollectionInfo[]> });
  const { data: people = [] } = useQuery({ queryKey: ["people"], queryFn: () => api.people.getAll() as Promise<PersonInfo[]> });
  const { data: savedSearches = [] } = useQuery({ queryKey: ["savedSearches"], queryFn: () => api.savedSearches.getAll() as Promise<SavedSearch[]> });

  // 2. Mutations
  const addFolderMutation = useMutation({ mutationFn: api.folders.add, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["folders"] }) });
  const removeFolderMutation = useMutation({ mutationFn: api.folders.delete, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["folders"] }) });
  
  const createCollectionMutation = useMutation({ mutationFn: ({ name, desc }: { name: string, desc?: string }) => api.collections.create(name, desc), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["collections"] }) });
  const deleteCollectionMutation = useMutation({ mutationFn: api.collections.delete, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["collections"] }) });

  const renamePersonMutation = useMutation({ mutationFn: ({ id, name }: { id: string, name: string }) => api.people.rename(id, name), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["people"] }) });
  const toggleFavoriteMutation = useMutation({ mutationFn: ({ id, isFav }: { id: string, isFav: boolean }) => api.images.toggleFavorite(id, isFav), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["images"] }) });

  const saveSearchMutation = useMutation({ mutationFn: (data: { name: string, query: string, filters: Record<string, unknown> }) => api.savedSearches.create(data), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["savedSearches"] }) });
  const deleteSearchMutation = useMutation({ mutationFn: api.savedSearches.delete, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["savedSearches"] }) });


  // 3. Local UI State (Onboarding, Options, Indexing Status)
  const [state, setState] = useState<AppState>(() => {
    const saved = localStorage.getItem("glimpse-one-state");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        return { ...getDefaultState(), ...parsed };
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


  // 4. Implement Local Modifiers

  const setOnboardingStep = (step: number) => update({ onboardingStep: step });
  const completeOnboarding = () => update({ isFirstLaunch: false, onboardingStep: 3 });
  const runInBackground = () => update({ isFirstLaunch: false, onboardingStep: 3 });

  const startIndexing = () => {
      // Mocked indexing since backend system APIs don't exist yet
      update({ indexingStatus: { phase: "scanning", progress: 0, total: 100, processed: 0, facesDetected: 0, skipped: 0, currentFile: "Scanning folders..." } });
      let processed = 0;
      const interval = setInterval(() => {
        processed += 10;
        if (processed >= 100) {
          clearInterval(interval);
          update({ indexingStatus: { phase: "complete", progress: 100, total: 100, processed: 100, facesDetected: 24, skipped: 0 } });
          queryClient.invalidateQueries(); // Refresh all backend data at the end
        } else {
          setState(prev => ({ ...prev, indexingStatus: { phase: "scanning", progress: processed, total: 100, processed, facesDetected: 5, skipped: 0 } }));
        }
      }, 500);
  };

  const downloadModel = (id: string) => { /* Mocked */ };
  const setActiveModel = (id: string) => { /* Mocked */ };
  const removeModel = (id: string) => { /* Mocked */ };

  return (
    <AppContext.Provider value={{
      ...state,
      
      // Live Data
      folders,
      people,
      images,
      collections,
      savedSearches,
      
      // Interface Functions
      setOnboardingStep,
      completeOnboarding,
      downloadModel,
      setActiveModel,
      removeModel,
      startIndexing,
      runInBackground,
      
      // Backend Mutations
      addFolder: (path) => addFolderMutation.mutate(path),
      removeFolder: (id) => removeFolderMutation.mutate(id),
      toggleFavorite: (id) => toggleFavoriteMutation.mutate({ id, isFav: !images.find(i => i.id === id)?.isFavorite }),
      renamePerson: (id, name) => renamePersonMutation.mutate({ id, name }),
      createCollection: (name, desc) => createCollectionMutation.mutate({ name, desc }),
      deleteCollection: (id) => deleteCollectionMutation.mutate(id),
      saveSearch: (name, query, filters) => saveSearchMutation.mutate({ name, query, filters }),
      deleteSavedSearch: (id) => deleteSearchMutation.mutate(id),
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
