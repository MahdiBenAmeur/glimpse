import React, { createContext, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { type AppSettings, type CollectionInfo, type FolderInfo, type ImageResult, type ModelInfo, type PersonInfo, type SavedSearch, type VideoResult } from "@/types/app";
import type { PersonMergeResult } from "@/lib/api";
import * as api from "@/lib/api";

type IndexingPhase = "idle" | "scanning" | "embeddings" | "faces" | "clustering" | "thumbnails" | "writing" | "cancelling" | "cancelled" | "complete";

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
  videoResults: VideoResult[];
  favorites: ImageResult[];
  collections: CollectionInfo[];
  savedSearches: SavedSearch[];
  indexingStatus: IndexingStatus;
  lastIndexedTime: string | null;
  totalIndexedImages: number;
  totalIndexedVideos: number;
  isHydrating: boolean;
  isWorking: boolean;
  busyMessage: string | null;
  showWorkingOverlay: boolean;
  settings: AppSettings;
}

interface AppContextType extends AppState {
  setOnboardingStep: (step: number) => void;
  completeOnboarding: () => void;
  downloadModel: (id: string) => Promise<void>;
  setActiveModel: (id: string) => Promise<void>;
  switchModelAndRebuild: (id: string) => Promise<void>;
  removeModel: (id: string) => Promise<void>;
  addFolder: (path?: string, includeSubfolders?: boolean) => Promise<void>;
  addPhotos: () => Promise<void>;
  removeFolder: (id: string) => Promise<void>;
  startIndexing: (options?: StartIndexingOptions) => Promise<void>;
  cancelIndexing: () => Promise<void>;
  runInBackground: () => void;
  toggleFavorite: (imageId: string) => void;
  renamePerson: (personId: string, name: string) => Promise<void>;
  mergePerson: (targetPersonId: string, sourcePersonId: string) => Promise<PersonMergeResult>;
  createCollection: (name: string, description?: string) => Promise<void>;
  deleteCollection: (id: string) => Promise<boolean>;
  saveSearch: (name: string, query: string, filters: Record<string, unknown>) => Promise<void>;
  deleteSavedSearch: (id: string) => Promise<void>;
  searchImages: (query: string, filters?: SearchFilters) => Promise<ImageResult[]>;
  searchVideos: (query: string) => Promise<VideoResult[]>;
  searchSimilarImages: (imageId: string | number) => Promise<ImageResult[]>;
  searchImagesByFile: (file: File) => Promise<ImageResult[]>;
  refreshData: (options?: { showLoader?: boolean }) => Promise<void>;
  updateSettings: (changes: Partial<AppSettings>) => Promise<AppSettings>;
}

export const AppContext = createContext<AppContextType | null>(null);
const UI_STATE_KEY = "glimpse-one-ui-state";

/**
 * Loads UI-specific state from local storage.
 */
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

/**
 * Persists UI-specific state to local storage.
 */
function persistUiState(nextState: { hideOnboardingWhileIndexing: boolean }) {
  localStorage.setItem(UI_STATE_KEY, JSON.stringify(nextState));
}

/**
 * Checks if the given phase represents an active indexing process.
 */
function isIndexingPhase(phase: IndexingPhase) {
  return phase !== "idle" && phase !== "complete" && phase !== "cancelled";
}

/**
 * Derives the current onboarding step based on the application state.
 */
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

/**
 * Updates the model list to set a specific model as active.
 */
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

/**
 * Extracts a user-friendly message from an error object.
 */
function getErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "Something went wrong";
}

/**
 * Core application provider that manages state, indexing, and data fetching.
 */
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
    videoResults: [],
    favorites: [],
    collections: [],
    savedSearches: [],
    indexingStatus: { phase: "idle", progress: 0, total: 0, processed: 0, facesDetected: 0, skipped: 0 },
    lastIndexedTime: null,
    totalIndexedImages: 0,
    totalIndexedVideos: 0,
    isHydrating: true,
    isWorking: false,
    busyMessage: null,
    showWorkingOverlay: true,
    settings: api.DEFAULT_APP_SETTINGS,
  });

  /**
   * Toggles the visibility of onboarding while indexing runs in the background.
   */
  const setBackgroundIndexingHidden = useCallback((hidden: boolean) => {
    setHideOnboardingWhileIndexing(hidden);
    persistUiState({ hideOnboardingWhileIndexing: hidden });
  }, []);

  /**
   * Wrapper for async actions that displays a busy overlay and handles notifications.
   */
  const withBusy = useCallback(async <T,>(
    message: string,
    action: () => Promise<T>,
    options?: { successMessage?: string; errorMessage?: string; showOverlay?: boolean },
  ) => {
    setState((prev) => ({
      ...prev,
      isWorking: true,
      busyMessage: message,
      showWorkingOverlay: options?.showOverlay ?? true,
    }));
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
      setState((prev) => ({ ...prev, isWorking: false, busyMessage: null, showWorkingOverlay: true }));
    }
  }, []);

  /**
   * Refreshes all application data from the backend.
   */
  const refreshData = useCallback(async (options?: { showLoader?: boolean }) => {
    const showLoader = options?.showLoader ?? false;
    if (showLoader) {
      setState((prev) => ({ ...prev, isHydrating: true }));
    }

    const [modelsResult, summaryResult, foldersResult, peopleResult, collectionsResult, savedSearchesResult, favoritesResult, settingsResult] =
      await Promise.allSettled([
        api.getModels(),
        api.getIndexSummary(),
        api.getFolders(),
        api.getPeople(),
        api.getCollections(),
        api.getSavedSearches(),
        api.getFavorites(),
        api.getAppSettings(),
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
      const settings = settingsResult.status === "fulfilled" ? settingsResult.value : prev.settings;
      const indexingStatus = summaryResult.status === "fulfilled" ? summaryResult.value.indexingStatus : prev.indexingStatus;
      const lastIndexedTime = summaryResult.status === "fulfilled" ? summaryResult.value.lastIndexedTime : prev.lastIndexedTime;
      const totalIndexedImages = summaryResult.status === "fulfilled" ? summaryResult.value.totalIndexedImages : prev.totalIndexedImages;
      const totalIndexedVideos = summaryResult.status === "fulfilled" ? summaryResult.value.totalIndexedVideos : prev.totalIndexedVideos;

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
        settings,
        indexingStatus,
        lastIndexedTime,
        totalIndexedImages,
        totalIndexedVideos,
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

  /**
   * Sets the current step in the onboarding flow.
   */
  const setOnboardingStep = useCallback((step: number) => {
    setState((prev) => ({ ...prev, onboardingStep: step, isFirstLaunch: step < 3 || prev.isFirstLaunch }));
  }, []);

  /**
   * Marks the onboarding flow as complete.
   */
  const completeOnboarding = useCallback(() => {
    setBackgroundIndexingHidden(false);
    setState((prev) => ({ ...prev, isFirstLaunch: false, onboardingStep: 3 }));
  }, [setBackgroundIndexingHidden]);

  /**
   * Initiates the download of a model and polls for progress.
   */
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
        { successMessage: "Model downloaded.", showOverlay: false },
      );
    } finally {
      window.clearInterval(interval);
      await refreshData();
    }
  }, [refreshData, withBusy]);

  /**
   * Sets a specific model as the active embedding model.
   */
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

  /**
   * Switches to a new model and triggers a full index rebuild.
   */
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

  /**
   * Removes a downloaded model from the system.
   */
  const removeModel = useCallback(async (id: string) => {
    if (state.settings.confirmDestructiveActions && !window.confirm("Delete this downloaded model?")) {
      return;
    }
    await withBusy(
      "Deleting model...",
      async () => {
        await api.deleteModel(id);
        await refreshData();
      },
      { successMessage: "Model deleted." },
    );
  }, [refreshData, state.settings.confirmDestructiveActions, withBusy]);

  /**
   * Adds a folder to the library for indexing.
   */
  const addFolder = useCallback(async (path?: string, includeSubfolders?: boolean) => {
    const resolvedIncludeSubfolders = includeSubfolders ?? state.settings.includeSubfoldersByDefault;
    await withBusy(
      path ? "Adding folder..." : "Waiting for folder selection...",
      async () => {
        if (path) {
          await api.createFolder(path, resolvedIncludeSubfolders);
        } else {
          await api.pickFolder(resolvedIncludeSubfolders);
        }
        await refreshData();
      },
      { successMessage: "Folder added." },
    );
  }, [refreshData, state.settings.includeSubfoldersByDefault, withBusy]);

  /**
   * Imports specific photo files into the library.
   */
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

  /**
   * Removes a folder and its indexed data from the library.
   */
  const removeFolder = useCallback(async (id: string) => {
    if (state.settings.confirmDestructiveActions && !window.confirm("Remove this folder and its indexed data?")) {
      return;
    }
    await withBusy(
      "Removing folder...",
      async () => {
        await api.deleteFolder(id);
        await refreshData();
      },
      { successMessage: "Folder removed." },
    );
  }, [refreshData, state.settings.confirmDestructiveActions, withBusy]);

  /**
   * Starts the indexing process for specific folders or the entire library.
   */
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
      if (summary.indexingStatus.phase === "cancelled") {
        toast.info("Indexing cancelled.");
      } else {
        toast.success("Indexing started.");
      }
    } catch (error) {
      toast.error(getErrorMessage(error));
      await refreshData();
      throw error;
    }
  }, [refreshData, setBackgroundIndexingHidden, state.activeModel?.id, state.folders]);

  /**
   * Requests the cancellation of the current indexing process.
   */
  const cancelIndexing = useCallback(async () => {
    try {
      const nextStatus = await api.cancelIndexing();
      setBackgroundIndexingHidden(false);
      setState((prev) => {
        const onboarding = deriveOnboardingState(
          prev.activeModel,
          prev.folders,
          nextStatus,
          prev.lastIndexedTime,
          prev.totalIndexedImages,
          false,
        );

        return {
          ...prev,
          indexingStatus: nextStatus,
          isFirstLaunch: onboarding.isFirstLaunch,
          onboardingStep: onboarding.onboardingStep,
        };
      });

      if (nextStatus.phase === "cancelled") {
        toast.info("Indexing cancelled.");
        await refreshData();
      } else {
        toast.info("Cancelling indexing after the current batch...");
      }
    } catch (error) {
      toast.error(getErrorMessage(error));
      await refreshData();
      throw error;
    }
  }, [refreshData, setBackgroundIndexingHidden]);

  /**
   * Hides the indexing progress and returns the user to the main app.
   */
  const runInBackground = useCallback(() => {
    setBackgroundIndexingHidden(true);
    setState((prev) => ({ ...prev, isFirstLaunch: false, onboardingStep: 3 }));
  }, [setBackgroundIndexingHidden]);

  /**
   * Toggles the favorite status of an image.
   */
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

  /**
   * Updates the name of a detected person.
   */
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

  /**
   * Merges two person profiles into a single identity.
   */
  const mergePerson = useCallback(async (targetPersonId: string, sourcePersonId: string) => {
    return withBusy(
      "Merging people...",
      async () => {
        const result = await api.mergePeople(targetPersonId, sourcePersonId);
        await refreshData();
        return result;
      },
      { successMessage: "People merged." },
    );
  }, [refreshData, withBusy]);

  /**
   * Creates a new user-defined image collection.
   */
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

  /**
   * Deletes an image collection.
   */
  const deleteCollection = useCallback(async (id: string) => {
    if (state.settings.confirmDestructiveActions && !window.confirm("Delete this collection?")) {
      return false;
    }
    await withBusy(
      "Deleting collection...",
      async () => {
        await api.deleteCollection(id);
        await refreshData();
      },
      { successMessage: "Collection deleted." },
    );
    return true;
  }, [refreshData, state.settings.confirmDestructiveActions, withBusy]);

  /**
   * Saves the current search query and filters.
   */
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

  /**
   * Deletes a previously saved search.
   */
  const deleteSavedSearch = useCallback(async (id: string) => {
    if (state.settings.confirmDestructiveActions && !window.confirm("Delete this saved search?")) {
      return;
    }
    await withBusy(
      "Deleting saved search...",
      async () => {
        await api.deleteSavedSearch(id);
        await refreshData();
      },
      { successMessage: "Saved search deleted." },
    );
  }, [refreshData, state.settings.confirmDestructiveActions, withBusy]);

  /**
   * Executes an image search with specific filters.
   */
  const searchImages = useCallback(async (query: string, filters?: SearchFilters) => {
    const modelId = state.activeModel?.id === "xclip-video-b32" ? "clip-vit-b32" : state.activeModel?.id;
    try {
      const results = await api.searchImages({
        query,
        folders: filters?.folders ?? [],
        dateRange: filters?.dateRange ?? "any",
        facePresence: filters?.facePresence ?? "any",
        people: filters?.people ?? [],
        facePhotoPath: filters?.facePhotoPath ?? null,
        modelId,
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

  /**
   * Searches videos by text query.
   */
  const searchVideosFn = useCallback(async (query: string) => {
    try {
      const response = await api.searchVideos({ query });
      setState((prev) => ({ ...prev, videoResults: response.results }));
      return response.results;
    } catch {
      setState((prev) => ({ ...prev, videoResults: [] }));
      return [];
    }
  }, []);

  /**
   * Searches for images similar to a specific indexed image.
   */
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

  /**
   * Performs a visual search using an uploaded image file.
   */
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

  /**
   * Updates application settings.
   */
  const updateSettings = useCallback(async (changes: Partial<AppSettings>) => {
    const nextSettings = await api.updateAppSettings(changes);
    setState((prev) => ({ ...prev, settings: nextSettings }));
    return nextSettings;
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
      cancelIndexing,
      runInBackground,
      toggleFavorite,
      renamePerson,
      mergePerson,
      createCollection,
      deleteCollection,
      saveSearch,
      deleteSavedSearch,
      searchImages,
      searchVideos: searchVideosFn,
      searchSimilarImages,
      searchImagesByFile,
      refreshData,
      updateSettings,
    }}>
      {children}
    </AppContext.Provider>
  );
}


