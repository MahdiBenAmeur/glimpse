import React, { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import { type ModelInfo, MOCK_MODELS } from "@/data/mockData";

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
  // UI & System State
  setOnboardingStep: (step: number) => void;
  completeOnboarding: () => void;
  downloadModel: (id: string) => void;
  setActiveModel: (id: string) => void;
  removeModel: (id: string) => void;
  startIndexing: () => void;
  runInBackground: () => void;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  // Local UI State (Onboarding, Options, Indexing Status)
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
        // NOTE: the components will auto refetch assuming they are configured with React Query refetch loops or we can add a global event.
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
      setOnboardingStep,
      completeOnboarding,
      downloadModel,
      setActiveModel,
      removeModel,
      startIndexing,
      runInBackground,
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

