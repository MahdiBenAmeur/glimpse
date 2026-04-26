import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { toast } from "@/components/ui/sonner";
import { type CollectionInfo, type FolderInfo, type ImageResult, type ModelInfo, type PersonInfo, type SavedSearch } from "@/types/app";
import * as api from "@/lib/api";

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

interface SearchFilters {
  folders?: string[];
  dateRange?: "any" | "today" | "last-7-days" | "last-30-days" | "this-year";
  facePresence?: "any" | "faces" | "no-faces";
  people?: Array<{ id: number; preference: "must_include" | "prefer" | "exclude" }>;
  facePhotoPath?: string | null;
}

interface StartIndexingOptions {
  folderPaths?: string[];
  folderIds?: string[];
  modelId?: string | null;
  recursive?: boolean;
  batchSize?: number;
  resetIndex?: boolean;
}

interface AppState {
  isFirstLaunch: boolean;
  onboardingStep: number;
  models: ModelInfo[];
  activeModel: ModelInfo | null;
  folders: FolderInfo[];
  people: PersonInfo[];
  images: ImageResult[];
  favorites: ImageResult[];
  collections: CollectionInfo[];
  savedSearches: SavedSearch[];
  indexingStatus: IndexingStatus;
  lastIndexedTime: string | null;
  totalIndexedImages: number;
  isHydrating: boolean;
  isWorking: boolean;
  busyMessage: string | null;
}

interface AppContextType extends AppState {
  setOnboardingStep: (step: number) => void;
  completeOnboarding: () => void;
  downloadModel: (id: string) => Promise<void>;
  setActiveModel: (id: string) => Promise<void>;
  switchModelAndRebuild: (id: string) => Promise<void>;
  removeModel: (id: string) => void;
  addFolder: (path?: string, includeSubfolders?: boolean) => Promise<void>;
  addPhotos: () => Promise<void>;
  removeFolder: (id: string) => Promise<void>;
  startIndexing: (options?: StartIndexingOptions) => Promise<void>;
  runInBackground: () => void;
  toggleFavorite: (imageId: string) => void;
  renamePerson: (personId: string, name: string) => Promise<void>;
  createCollection: (name: string, description?: string) => Promise<void>;
  deleteCollection: (id: string) => Promise<void>;
  saveSearch: (name: string, query: string, filters: Record<string, unknown>) => Promise<void>;
  deleteSavedSearch: (id: string) => Promise<void>;
  searchImages: (query: string, filters?: SearchFilters) => Promise<ImageResult[]>;
  searchSimilarImages: (imageId: string | number) => Promise<ImageResult[]>;
  searchImagesByFile: (file: File) => Promise<ImageResult[]>;
  refreshData: (options?: { showLoader?: boolean }) => Promise<void>;
}

const AppContext = createContext<AppContextType | null>(null);
const UI_STATE_KEY = "glimpse-one-ui-state";

function loadPersistedUiState() {
  const raw = localStorage.getItem(UI_STATE_KEY);
  if (!raw) return { hideOnboardingWhileIndexing: false };

  try {
    const parsed = JSON.parse(raw);
    return {
      hideOnboardingWhileIndexing: Boolean(parsed.hideOnboardingWhileIndexing),
    };
  } catch {
    return { hideOnboardingWhileIndexing: false };
  }
}

function persistUiState(nextState: { hideOnboardingWhileIndexing: boolean }) {
  localStorage.setItem(UI_STATE_KEY, JSON.stringify(nextState));
}

function isIndexingPhase(phase: IndexingPhase) {
  return phase !== "idle" && phase !== "complete";
}

function deriveOnboardingState(
  activeModel: ModelInfo | null,
  folders: FolderInfo[],
  indexingStatus: IndexingStatus,
  lastIndexedTime: string | null,
  totalIndexedImages: number,
  hideOnboardingWhileIndexing: boolean,
) {
  if (hideOnboardingWhileIndexing && isIndexingPhase(indexingStatus.phase)) {
    return { isFirstLaunch: false, onboardingStep: 3 };
  }

  if (!activeModel) return { isFirstLaunch: true, onboardingStep: 0 };
  if (folders.length === 0) return { isFirstLaunch: true, onboardingStep: 1 };
  if (isIndexingPhase(indexingStatus.phase)) return { isFirstLaunch: true, onboardingStep: 2 };
  if (!lastIndexedTime && totalIndexedImages === 0) return { isFirstLaunch: true, onboardingStep: 1 };

  return { isFirstLaunch: false, onboardingStep: 3 };
}

function markModelAsActive(models: ModelInfo[], modelId: string) {
  const nextModels = models.map((model) => {
    if (model.id === modelId) {
      return { ...model, status: "active" as ModelInfo["status"], downloadProgress: undefined };
    }
    if (model.status === "active") {
      return { ...model, status: "installed" as ModelInfo["status"], downloadProgress: undefined };
    }
    return model;
  });

  return {
    models: nextModels,
    activeModel: nextModels.find((model) => model.id === modelId) ?? null,
  };
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "Something went wrong";
}

export function AppProvider({ children }: { children: ReactNode }) {
  const persistedUiState = useMemo(loadPersistedUiState, []);
  const initializedRef = useRef(false);
  const [hideOnboardingWhileIndexing, setHideOnboardingWhileIndexing] = useState(persistedUiState.hideOnboardingWhileIndexing);
  const [state, setState] = useState<AppState>({
    isFirstLaunch: true,
    onboardingStep: 0,
    models: [],
    activeModel: null,
    folders: [],
    people: [],
    images: [],
    favorites: [],
    collections: [],
    savedSearches: [],
    indexingStatus: { phase: "idle", progress: 0, total: 0, processed: 0, facesDetected: 0, skipped: 0 },
    lastIndexedTime: null,
    totalIndexedImages: 0,
    isHydrating: true,
    isWorking: false,
    busyMessage: null,
  });

  const setBackgroundIndexingHidden = useCallback((hidden: boolean) => {
    setHideOnboardingWhileIndexing(hidden);
    persistUiState({ hideOnboardingWhileIndexing: hidden });
  }, []);

  const withBusy = useCallback(async <T,>(
    message: string,
    action: () => Promise<T>,
    options?: { successMessage?: string; errorMessage?: string },
  ) => {
    setState((prev) => ({ ...prev, isWorking: true, busyMessage: message }));
    try {
      const result = await action();
      if (options?.successMessage) {
        toast.success(options.successMessage);
      }
      return result;
    } catch (error) {
      toast.error(options?.errorMessage ?? getErrorMessage(error));
      throw error;
    } finally {
      setState((prev) => ({ ...prev, isWorking: false, busyMessage: null }));
    }
  }, []);

  const refreshData = useCallback(async (options?: { showLoader?: boolean }) => {
    const showLoader = options?.showLoader ?? false;
    if (showLoader) {
      setState((prev) => ({ ...prev, isHydrating: true }));
    }

    const [modelsResult, summaryResult, foldersResult, peopleResult, collectionsResult, savedSearchesResult, favoritesResult] =
      await Promise.allSettled([
        api.getModels(),
        api.getIndexSummary(),
        api.getFolders(),
        api.getPeople(),
        api.getCollections(),
        api.getSavedSearches(),
        api.getFavorites(),
      ]);

    setState((prev) => {
      const models = modelsResult.status === "fulfilled"
        ? modelsResult.value
        : summaryResult.status === "fulfilled"
          ? summaryResult.value.models
          : prev.models;

      const activeModel = summaryResult.status === "fulfilled" ? summaryResult.value.activeModel : prev.activeModel;
      const folders = foldersResult.status === "fulfilled" ? foldersResult.value : prev.folders;
      const people = peopleResult.status === "fulfilled" ? peopleResult.value : prev.people;
      const collections = collectionsResult.status === "fulfilled" ? collectionsResult.value : prev.collections;
      const savedSearches = savedSearchesResult.status === "fulfilled" ? savedSearchesResult.value : prev.savedSearches;
      const favorites = favoritesResult.status === "fulfilled" ? favoritesResult.value : prev.favorites;
      const indexingStatus = summaryResult.status === "fulfilled" ? summaryResult.value.indexingStatus : prev.indexingStatus;
      const lastIndexedTime = summaryResult.status === "fulfilled" ? summaryResult.value.lastIndexedTime : prev.lastIndexedTime;
      const totalIndexedImages = summaryResult.status === "fulfilled" ? summaryResult.value.totalIndexedImages : prev.totalIndexedImages;

      const onboarding = deriveOnboardingState(
        activeModel,
        folders,
        indexingStatus,
        lastIndexedTime,
        totalIndexedImages,
        hideOnboardingWhileIndexing,
      );

      return {
        ...prev,
        isHydrating: false,
        isFirstLaunch: onboarding.isFirstLaunch,
        onboardingStep: onboarding.onboardingStep,
        models,
        activeModel,
        folders,
        people,
        favorites,
        collections,
        savedSearches,
        indexingStatus,
        lastIndexedTime,
        totalIndexedImages,
      };
    });
  }, [hideOnboardingWhileIndexing]);

  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;
    void refreshData({ showLoader: true });
  }, [refreshData]);

  useEffect(() => {
    if (!isIndexingPhase(state.indexingStatus.phase)) {
      if (hideOnboardingWhileIndexing) {
        setBackgroundIndexingHidden(false);
      }
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const nextStatus = await api.getIndexStatus();
        setState((prev) => {
          const onboarding = deriveOnboardingState(
            prev.activeModel,
            prev.folders,
            nextStatus,
            prev.lastIndexedTime,
            prev.totalIndexedImages,
            hideOnboardingWhileIndexing,
          );

          return {
            ...prev,
            indexingStatus: nextStatus,
            isFirstLaunch: onboarding.isFirstLaunch,
            onboardingStep: onboarding.onboardingStep,
          };
        });

        if (!isIndexingPhase(nextStatus.phase)) {
          if (hideOnboardingWhileIndexing) {
            setBackgroundIndexingHidden(false);
          }
          await refreshData();
        }
      } catch {
        // Ignore transient polling failures.
      }
    }, 1200);

    return () => window.clearInterval(interval);
  }, [hideOnboardingWhileIndexing, refreshData, setBackgroundIndexingHidden, state.indexingStatus.phase]);

  const setOnboardingStep = useCallback((step: number) => {
    setState((prev) => ({ ...prev, onboardingStep: step, isFirstLaunch: step < 3 || prev.isFirstLaunch }));
  }, []);

  const completeOnboarding = useCallback(() => {
    setBackgroundIndexingHidden(false);
    setState((prev) => ({ ...prev, isFirstLaunch: false, onboardingStep: 3 }));
  }, [setBackgroundIndexingHidden]);

  const downloadModel = useCallback(async (id: string) => {
    const setDownloadProgress = (progress: number) => {
      setState((prev) => ({
        ...prev,
        models: prev.models.map((model) => (
          model.id === id
            ? { ...model, status: "downloading" as ModelInfo["status"], downloadProgress: progress }
            : model
        )),
      }));
    };

    setDownloadProgress(0);
    const interval = window.setInterval(() => {
      void api.getModelDownloadStatus(id)
        .then((status) => {
          setDownloadProgress(status.progress);
        })
        .catch(() => {
          // Ignore transient polling failures while the main download request is in flight.
        });
    }, 700);

    try {
      await withBusy(
        "Downloading model...",
        async () => {
          await api.downloadModel(id);
          setDownloadProgress(100);
          await refreshData();
        },
        { successMessage: "Model downloaded." },
      );
    } finally {
      window.clearInterval(interval);
      await refreshData();
    }
  }, [refreshData, withBusy]);

  const setActiveModel = useCallback(async (id: string) => {
    await withBusy(
      "Selecting model...",
      async () => {
        await api.activateModel(id);
        await refreshData();
      },
      { successMessage: "Model selected." },
    );
  }, [refreshData, withBusy]);

  const switchModelAndRebuild = useCallback(async (id: string) => {
    await withBusy(
      "Switching model and rebuilding index...",
      async () => {
        await api.activateModel(id);
        const currentFolders = state.folders.map((folder) => folder.path);
        if (currentFolders.length === 0) {
          await refreshData();
          return;
        }

        setBackgroundIndexingHidden(false);
        setState((prev) => {
          const { models, activeModel } = markModelAsActive(prev.models, id);
          const nextIndexingStatus: IndexingStatus = {
            phase: "scanning",
            progress: 0,
            total: prev.indexingStatus.total,
            processed: 0,
            facesDetected: 0,
            skipped: 0,
            currentFile: currentFolders[0] ?? prev.indexingStatus.currentFile,
          };
          const onboarding = deriveOnboardingState(
            activeModel,
            prev.folders,
            nextIndexingStatus,
            prev.lastIndexedTime,
            prev.totalIndexedImages,
            false,
          );

          return {
            ...prev,
            models,
            activeModel,
            indexingStatus: nextIndexingStatus,
            isFirstLaunch: onboarding.isFirstLaunch,
            onboardingStep: onboarding.onboardingStep,
          };
        });

        try {
          const summary = await api.startIndexing({
            folderPaths: currentFolders,
            modelId: id,
            recursive: true,
            batchSize: api.getDefaultIndexBatchSize(id),
            resetIndex: true,
          });

          setState((prev) => {
            const { models, activeModel } = markModelAsActive(prev.models, id);
            const onboarding = deriveOnboardingState(
              activeModel,
              prev.folders,
              summary.indexingStatus,
              summary.lastIndexedTime,
              summary.totalIndexedImages,
              false,
            );

            return {
              ...prev,
              models,
              activeModel,
              indexingStatus: summary.indexingStatus,
              lastIndexedTime: summary.lastIndexedTime,
              totalIndexedImages: summary.totalIndexedImages,
              isFirstLaunch: onboarding.isFirstLaunch,
              onboardingStep: onboarding.onboardingStep,
            };
          });
        } catch (error) {
          await refreshData();
          throw error;
        }
      },
      { successMessage: state.folders.length > 0 ? "Model switched. Rebuild started." : "Model switched." },
    );
  }, [refreshData, setBackgroundIndexingHidden, state.folders, withBusy]);

  const removeModel = useCallback((_id: string) => {
    toast.info("Model removal is not wired yet.");
  }, []);

  const addFolder = useCallback(async (path?: string, includeSubfolders = true) => {
    await withBusy(
      path ? "Adding folder..." : "Waiting for folder selection...",
      async () => {
        if (path) {
          await api.createFolder(path, includeSubfolders);
        } else {
          await api.pickFolder(includeSubfolders);
        }
        await refreshData();
      },
      { successMessage: "Folder added." },
    );
  }, [refreshData, withBusy]);

  const addPhotos = useCallback(async () => {
    await withBusy(
      "Waiting for image selection...",
      async () => {
        const imported = await api.importImages();
        await refreshData();
        toast.success(`${imported.importedCount} photo${imported.importedCount === 1 ? "" : "s"} added.`);
      },
      { errorMessage: "Could not add photos." },
    );
  }, [refreshData, withBusy]);

  const removeFolder = useCallback(async (id: string) => {
    await withBusy(
      "Removing folder...",
      async () => {
        await api.deleteFolder(id);
        await refreshData();
      },
      { successMessage: "Folder removed." },
    );
  }, [refreshData, withBusy]);

  const startIndexing = useCallback(async (options?: StartIndexingOptions) => {
    const nextFolderPaths = options?.folderPaths ?? state.folders.map((folder) => folder.path);
    const nextFolderIds = options?.folderIds;
    const nextModelId = options?.modelId ?? state.activeModel?.id ?? undefined;

    setBackgroundIndexingHidden(false);
    setState((prev) => ({
      ...prev,
      indexingStatus: {
        phase: "scanning",
        progress: 0,
        total: prev.indexingStatus.total,
        processed: 0,
        facesDetected: 0,
        skipped: 0,
        currentFile: nextFolderPaths[0] ?? prev.indexingStatus.currentFile,
      },
      onboardingStep: prev.isFirstLaunch ? 2 : prev.onboardingStep,
    }));

    try {
      const summary = await api.startIndexing({
        folderPaths: nextFolderPaths,
        folderIds: nextFolderIds,
        modelId: nextModelId,
        recursive: options?.recursive ?? true,
        batchSize: options?.batchSize ?? api.getDefaultIndexBatchSize(nextModelId),
        resetIndex: options?.resetIndex ?? true,
      });

      setState((prev) => ({
        ...prev,
        indexingStatus: summary.indexingStatus,
        lastIndexedTime: summary.lastIndexedTime,
        totalIndexedImages: summary.totalIndexedImages,
        onboardingStep: prev.isFirstLaunch ? 2 : prev.onboardingStep,
      }));
      toast.success("Indexing started.");
    } catch (error) {
      toast.error(getErrorMessage(error));
      await refreshData();
      throw error;
    }
  }, [refreshData, setBackgroundIndexingHidden, state.activeModel?.id, state.folders]);

  const runInBackground = useCallback(() => {
    setBackgroundIndexingHidden(true);
    setState((prev) => ({ ...prev, isFirstLaunch: false, onboardingStep: 3 }));
  }, [setBackgroundIndexingHidden]);

  const toggleFavorite = useCallback((imageId: string) => {
    let nextFavorite = false;

    setState((prev) => {
      const images = prev.images.map((image) => {
        if (image.id !== imageId) return image;
        nextFavorite = !image.isFavorite;
        return { ...image, isFavorite: nextFavorite };
      });

      const imageFromResults = images.find((image) => image.id === imageId);
      let favorites = prev.favorites.map((image) => (
        image.id === imageId ? { ...image, isFavorite: nextFavorite } : image
      ));

      if (imageFromResults && nextFavorite && !favorites.some((image) => image.id === imageId)) {
        favorites = [imageFromResults, ...favorites];
      }
      if (!nextFavorite) {
        favorites = favorites.filter((image) => image.id !== imageId);
      }

      return { ...prev, images, favorites };
    });

    void api.toggleFavorite(imageId, nextFavorite)
      .then(() => api.getFavorites())
      .then((favorites) => setState((prev) => ({ ...prev, favorites })))
      .catch(() => {
        toast.error("Could not update favorite.");
        void refreshData();
      });
  }, [refreshData]);

  const renamePerson = useCallback(async (personId: string, name: string) => {
    await withBusy(
      "Saving person name...",
      async () => {
        await api.renamePerson(personId, name);
        await refreshData();
      },
      { successMessage: "Person updated." },
    );
  }, [refreshData, withBusy]);

  const createCollection = useCallback(async (name: string, description?: string) => {
    await withBusy(
      "Creating collection...",
      async () => {
        await api.createCollection(name, description);
        await refreshData();
      },
      { successMessage: "Collection created." },
    );
  }, [refreshData, withBusy]);

  const deleteCollection = useCallback(async (id: string) => {
    await withBusy(
      "Deleting collection...",
      async () => {
        await api.deleteCollection(id);
        await refreshData();
      },
      { successMessage: "Collection deleted." },
    );
  }, [refreshData, withBusy]);

  const saveSearch = useCallback(async (name: string, query: string, filters: Record<string, unknown>) => {
    await withBusy(
      "Saving search...",
      async () => {
        await api.createSavedSearch(name, query, filters);
        await refreshData();
      },
      { successMessage: "Search saved." },
    );
  }, [refreshData, withBusy]);

  const deleteSavedSearch = useCallback(async (id: string) => {
    await withBusy(
      "Deleting saved search...",
      async () => {
        await api.deleteSavedSearch(id);
        await refreshData();
      },
      { successMessage: "Saved search deleted." },
    );
  }, [refreshData, withBusy]);

  const searchImages = useCallback(async (query: string, filters?: SearchFilters) => {
    try {
      const results = await api.searchImages({
        query,
        folders: filters?.folders ?? [],
        dateRange: filters?.dateRange ?? "any",
        facePresence: filters?.facePresence ?? "any",
        people: filters?.people ?? [],
        facePhotoPath: filters?.facePhotoPath ?? null,
        modelId: state.activeModel?.id ?? undefined,
        page: 1,
        pageSize: 100,
      });
      setState((prev) => ({ ...prev, images: results }));
      return results;
    } catch (error) {
      toast.error(getErrorMessage(error));
      throw error;
    }
  }, [state.activeModel?.id]);

  const searchSimilarImages = useCallback(async (imageId: string | number) => {
    try {
      const results = await api.getSimilarImages(imageId);
      setState((prev) => ({ ...prev, images: results }));
      return results;
    } catch (error) {
      toast.error(getErrorMessage(error));
      throw error;
    }
  }, []);

  const searchImagesByFile = useCallback(async (file: File) => {
    try {
      const results = await api.searchByImageFile(file);
      setState((prev) => ({ ...prev, images: results }));
      return results;
    } catch (error) {
      toast.error(getErrorMessage(error));
      throw error;
    }
  }, []);

  return (
    <AppContext.Provider value={{
      ...state,
      setOnboardingStep,
      completeOnboarding,
      downloadModel,
      setActiveModel,
      switchModelAndRebuild,
      removeModel,
      addFolder,
      addPhotos,
      removeFolder,
      startIndexing,
      runInBackground,
      toggleFavorite,
      renamePerson,
      createCollection,
      deleteCollection,
      saveSearch,
      deleteSavedSearch,
      searchImages,
      searchSimilarImages,
      searchImagesByFile,
      refreshData,
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
