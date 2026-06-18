import type {
  AppSettings,
  CollectionInfo,
  FolderInfo,
  ImageResult,
  ModelInfo,
  PersonInfo,
  SavedSearch,
  VideoResult,
} from "@/types/app";

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
const DEFAULT_INDEX_BATCH_SIZE = 32;
const SIGLIP2_LARGE_MODEL_ID = "siglip2-large-patch16-384";
const SIGLIP2_LARGE_BATCH_SIZE = 8;

export function getDefaultIndexBatchSize(modelId?: string | null): number {
  if (modelId === SIGLIP2_LARGE_MODEL_ID) {
    return SIGLIP2_LARGE_BATCH_SIZE;
  }
  return DEFAULT_INDEX_BATCH_SIZE;
}

type IndexingPhase =
  | "idle"
  | "scanning"
  | "embeddings"
  | "faces"
  | "clustering"
  | "thumbnails"
  | "writing"
  | "cancelling"
  | "cancelled"
  | "complete";

export interface IndexingStatus {
  phase: IndexingPhase;
  progress: number;
  total: number;
  processed: number;
  facesDetected: number;
  skipped: number;
  currentFile?: string;
  error?: string | null;
}

export interface IndexSummary {
  activeModel: ModelInfo | null;
  models: ModelInfo[];
  indexingStatus: IndexingStatus;
  lastIndexedTime: string | null;
  totalIndexedImages: number;
  totalIndexedVideos: number;
  totalPeople: number;
  totalFolders: number;
  indexedPaths: string[];
}

export const DEFAULT_APP_SETTINGS: AppSettings = {
  rememberLastPage: true,
  confirmDestructiveActions: true,
  doubleClickBehavior: "viewer",
  includeSubfoldersByDefault: true,
  skipHiddenFolders: true,
  faceDetectionEnabled: true,
  compactSidebar: false,
  thumbnailDensity: "comfortable",
};

export interface ImportedImagesResult {
  folder: FolderInfo;
  importedCount: number;
  files: string[];
}

export interface PickCollectionImagesResult {
  collectionId: string;
  addedCount: number;
  autoIndexedCount: number;
  skippedPaths: string[];
  imageCount: number;
}

export interface StorageSummary {
  indexPath: string;
  indexSizeBytes: number;
  thumbnailCachePath: string;
  thumbnailCacheBytes: number;
}

export interface ModelDownloadStatus {
  modelId: string;
  status: "idle" | "downloading" | "complete" | "error";
  progress: number;
  downloadedBytes: number;
  totalBytes: number;
  error?: string | null;
}

export interface PersonMergeResult {
  targetPersonId: string;
  sourcePersonId: string;
  imageCount: number;
  name: string | null;
}

export interface SearchRequestPayload {
  query: string;
  folders?: string[];
  dateRange?: "any" | "today" | "last-7-days" | "last-30-days" | "this-year";
  facePresence?: "any" | "faces" | "no-faces";
  people?: Array<{
    id: number;
    preference: "must_include" | "prefer" | "exclude";
  }>;
  facePhotoPath?: string | null;
  page?: number;
  pageSize?: number;
  modelId?: string | null;
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...init,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail =
        typeof body?.detail === "string"
          ? body.detail
          : JSON.stringify(body?.detail ?? body);
    } catch {
      // Ignore JSON parsing errors on failure bodies.
    }
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

/* eslint-disable @typescript-eslint/no-explicit-any */

function mapModel(raw: any): ModelInfo {
  return {
    id: String(raw.id),
    name: String(raw.name),
    description: String(raw.description ?? ""),
    quality: raw.quality,
    speed: raw.speed,
    diskSize: String(raw.diskSize ?? raw.disk_size ?? ""),
    suitability: String(raw.suitability ?? ""),
    mediaType: raw.mediaType === "unified" ? "unified" : (raw.mediaType === "video" ? "video" : "image"),
    status: raw.status,
    downloadProgress: raw.downloadProgress,
  };
}

function mapFolder(raw: any): FolderInfo {
  return {
    id: String(raw.id),
    path: String(raw.path),
    imageCount: Number(raw.imageCount ?? raw.image_count ?? 0),
    lastScanTime: String(raw.lastScanTime ?? raw.last_scan_time ?? ""),
    status: (raw.status ?? "ready") as FolderInfo["status"],
    includeSubfolders: Boolean(
      raw.includeSubfolders ?? raw.include_subfolders ?? true,
    ),
  };
}

function mapPerson(raw: any): PersonInfo {
  return {
    id: String(raw.id),
    name: raw.name ?? null,
    faceUrl: String(raw.faceUrl ?? raw.face_url ?? ""),
    imageCount: Number(raw.imageCount ?? raw.image_count ?? 0),
    lastSeen: raw.lastSeen ?? raw.last_seen ?? undefined,
  };
}

function mapImage(raw: any): ImageResult {
  const imageId = raw.imageId ?? raw.image_id ?? raw.id;
  return {
    id: String(raw.id ?? imageId),
    imageId: Number(imageId),
    url: String(raw.url),
    thumbnailUrl: raw.thumbnailUrl ?? raw.thumbnail_url ?? undefined,
    path: raw.path ?? undefined,
    filename: String(raw.filename ?? ""),
    folder: String(raw.folder ?? raw.path ?? ""),
    dateTaken: String(raw.dateTaken ?? raw.date_taken ?? ""),
    width: Number(raw.width ?? 0),
    height: Number(raw.height ?? 0),
    isFavorite: Boolean(raw.isFavorite ?? raw.is_favorite ?? false),
    faceCount: Number(raw.faceCount ?? raw.face_count ?? 0),
    people: Array.isArray(raw.people) ? raw.people.map(String) : [],
    collections: Array.isArray(raw.collections)
      ? raw.collections.map(String)
      : [],
    score:
      raw.score !== undefined && raw.score !== null
        ? Number(raw.score)
        : undefined,
  };
}

function mapCollection(raw: any): CollectionInfo {
  return {
    id: String(raw.id),
    name: String(raw.name),
    description: raw.description ?? undefined,
    imageCount: Number(raw.imageCount ?? raw.image_count ?? 0),
    previewUrls: Array.isArray(raw.previewUrls)
      ? raw.previewUrls.map(String)
      : [],
    modifiedDate: String(
      raw.modifiedDate ??
        raw.modified_date ??
        new Date().toISOString().slice(0, 10),
    ),
  };
}

function mapSavedSearch(raw: any): SavedSearch {
  return {
    id: String(raw.id),
    name: String(raw.name),
    query: String(raw.query ?? ""),
    filters: typeof raw.filters === "object" && raw.filters ? raw.filters : {},
    lastUsed: String(raw.lastUsed ?? raw.last_used ?? ""),
  };
}

function mapIndexingStatus(raw: any): IndexingStatus {
  return {
    phase: raw.phase,
    progress: Number(raw.progress ?? 0),
    total: Number(raw.total ?? 0),
    processed: Number(raw.processed ?? 0),
    facesDetected: Number(raw.facesDetected ?? raw.faces_detected ?? 0),
    skipped: Number(raw.skipped ?? 0),
    currentFile: raw.currentFile ?? raw.current_file ?? undefined,
    error: raw.error ?? null,
  };
}

function mapVideoResult(raw: any): VideoResult {
  return {
    id: String(raw.id ?? raw.videoId),
    videoId: Number(raw.videoId),
    url: String(raw.url),
    thumbnailUrl: raw.thumbnailUrl ? String(raw.thumbnailUrl) : undefined,
    path: raw.path ? String(raw.path) : undefined,
    filename: String(raw.filename ?? ""),
    folder: String(raw.folder ?? ""),
    dateTaken: raw.dateTaken ?? null,
    width: raw.width != null ? Number(raw.width) : null,
    height: raw.height != null ? Number(raw.height) : null,
    duration: raw.duration != null ? Number(raw.duration) : null,
    score: raw.score != null ? Number(raw.score) : undefined,
    mediaType: "video",
  };
}

export interface VideoSearchResponse {
  query: string;
  page: number;
  pageSize: number;
  totalResults: number;
  totalPages: number;
  results: VideoResult[];
}

function mapIndexSummary(raw: any): IndexSummary {
  return {
    activeModel: raw.activeModel ? mapModel(raw.activeModel) : null,
    models: Array.isArray(raw.models) ? raw.models.map(mapModel) : [],
    indexingStatus: mapIndexingStatus(raw.indexingStatus ?? {}),
    lastIndexedTime: raw.lastIndexedTime ?? null,
    totalIndexedImages: Number(raw.totalIndexedImages ?? 0),
    totalIndexedVideos: Number(raw.totalIndexedVideos ?? 0),
    totalPeople: Number(raw.totalPeople ?? 0),
    totalFolders: Number(raw.totalFolders ?? 0),
    indexedPaths: Array.isArray(raw.indexedPaths)
      ? raw.indexedPaths.map(String)
      : [],
  };
}

export async function getIndexSummary(): Promise<IndexSummary> {
  return mapIndexSummary(await apiRequest<any>("/api/index/summary"));
}

export async function getModels(): Promise<ModelInfo[]> {
  return (await apiRequest<any[]>("/api/index/models")).map(mapModel);
}

export async function getIndexStatus(): Promise<IndexingStatus> {
  return mapIndexingStatus(await apiRequest<any>("/api/index/status"));
}

export async function downloadModel(modelId: string): Promise<ModelInfo> {
  return mapModel(
    await apiRequest<any>("/api/index/models/download", {
      method: "POST",
      body: JSON.stringify({ modelId }),
    }),
  );
}

export async function getModelDownloadStatus(
  modelId: string,
): Promise<ModelDownloadStatus> {
  const raw = await apiRequest<any>(
    `/api/index/models/download-status/${modelId}`,
  );
  return {
    modelId: String(raw.modelId ?? modelId),
    status: raw.status,
    progress: Number(raw.progress ?? 0),
    downloadedBytes: Number(raw.downloadedBytes ?? 0),
    totalBytes: Number(raw.totalBytes ?? 0),
    error: raw.error ?? null,
  };
}

export async function activateModel(
  modelId: string,
  _mediaType?: "image" | "video" | "unified",
): Promise<ModelInfo> {
  return mapModel(
    await apiRequest<any>("/api/index/models/activate", {
      method: "POST",
      body: JSON.stringify({ modelId }),
    }),
  );
}

export async function deleteModel(modelId: string): Promise<void> {
  await apiRequest(`/api/index/models/${modelId}`, {
    method: "DELETE",
  });
}

function mapAppSettings(raw: any): AppSettings {
  return {
    rememberLastPage: Boolean(
      raw.rememberLastPage ?? DEFAULT_APP_SETTINGS.rememberLastPage,
    ),
    confirmDestructiveActions: Boolean(
      raw.confirmDestructiveActions ??
      DEFAULT_APP_SETTINGS.confirmDestructiveActions,
    ),
    doubleClickBehavior:
      raw.doubleClickBehavior === "external" ? "external" : "viewer",
    includeSubfoldersByDefault: Boolean(
      raw.includeSubfoldersByDefault ??
      DEFAULT_APP_SETTINGS.includeSubfoldersByDefault,
    ),
    skipHiddenFolders: Boolean(
      raw.skipHiddenFolders ?? DEFAULT_APP_SETTINGS.skipHiddenFolders,
    ),
    faceDetectionEnabled: Boolean(
      raw.faceDetectionEnabled ?? DEFAULT_APP_SETTINGS.faceDetectionEnabled,
    ),
    compactSidebar: Boolean(
      raw.compactSidebar ?? DEFAULT_APP_SETTINGS.compactSidebar,
    ),
    thumbnailDensity:
      raw.thumbnailDensity === "compact" ? "compact" : "comfortable",
  };
}

export async function getAppSettings(): Promise<AppSettings> {
  return mapAppSettings(await apiRequest<any>("/api/settings/"));
}

export async function updateAppSettings(
  changes: Partial<AppSettings>,
): Promise<AppSettings> {
  return mapAppSettings(
    await apiRequest<any>("/api/settings/", {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),
  );
}

export async function getFolders(): Promise<FolderInfo[]> {
  return (await apiRequest<any[]>("/api/folders/")).map(mapFolder);
}

export async function createFolder(
  path: string,
  includeSubfolders: boolean,
): Promise<FolderInfo> {
  return mapFolder(
    await apiRequest<any>("/api/folders/", {
      method: "POST",
      body: JSON.stringify({
        path,
        include_subfolders: includeSubfolders,
        image_count: 0,
        status: "ready",
      }),
    }),
  );
}

export async function pickFolder(
  includeSubfolders: boolean,
): Promise<FolderInfo> {
  return mapFolder(
    await apiRequest<any>("/api/folders/pick", {
      method: "POST",
      body: JSON.stringify({ includeSubfolders }),
    }),
  );
}

export async function importImages(): Promise<ImportedImagesResult> {
  const raw = await apiRequest<any>("/api/folders/import-images", {
    method: "POST",
    body: JSON.stringify({}),
  });

  return {
    folder: mapFolder(raw.folder),
    importedCount: Number(raw.importedCount ?? 0),
    files: Array.isArray(raw.files) ? raw.files.map(String) : [],
  };
}

export async function deleteFolder(folderId: string): Promise<void> {
  await apiRequest(`/api/folders/${folderId}`, { method: "DELETE" });
}

export async function startIndexing(payload: {
  folderPaths: string[];
  folderIds?: string[];
  modelId?: string | null;
  recursive?: boolean;
  batchSize?: number;
  resetIndex?: boolean;
}): Promise<IndexSummary> {
  const raw = await apiRequest<any>("/api/index/start", {
    method: "POST",
    body: JSON.stringify({
      folderPaths: payload.folderPaths,
      folderIds: (payload.folderIds ?? []).map((id) => Number(id)),
      modelId: payload.modelId ?? undefined,
      recursive: payload.recursive ?? true,
      batchSize: payload.batchSize ?? getDefaultIndexBatchSize(payload.modelId),
      resetIndex: payload.resetIndex ?? true,
    }),
  });
  return mapIndexSummary(raw);
}

export async function cancelIndexing(): Promise<IndexingStatus> {
  return mapIndexingStatus(
    await apiRequest<any>("/api/index/cancel", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  );
}

export async function searchImages(
  payload: SearchRequestPayload,
): Promise<ImageResult[]> {
  const raw = await apiRequest<any>("/api/search/", {
    method: "POST",
    body: JSON.stringify({
      query: payload.query,
      folders: payload.folders ?? [],
      dateRange: payload.dateRange ?? "any",
      facePresence: payload.facePresence ?? "any",
      people: payload.people ?? [],
      facePhotoPath: payload.facePhotoPath ?? null,
      page: payload.page ?? 1,
      pageSize: payload.pageSize ?? 100,
      modelId: payload.modelId ?? undefined,
    }),
  });
  return Array.isArray(raw.results) ? raw.results.map(mapImage) : [];
}

export async function searchVideos(payload: {
  query: string;
  page?: number;
  pageSize?: number;
}): Promise<VideoSearchResponse> {
  const raw = await apiRequest<any>("/api/search/videos", {
    method: "POST",
    body: JSON.stringify({
      query: payload.query,
      page: payload.page ?? 1,
      pageSize: payload.pageSize ?? 50,
    }),
  });
  return {
    query: String(raw.query ?? ""),
    page: Number(raw.page ?? 1),
    pageSize: Number(raw.pageSize ?? 50),
    totalResults: Number(raw.totalResults ?? 0),
    totalPages: Number(raw.totalPages ?? 0),
    results: Array.isArray(raw.results) ? raw.results.map(mapVideoResult) : [],
  };
}

export interface UnifiedSearchResult {
  id: string;
  score: number;
  mediaType: "image" | "video";
  filePath: string | null;
  fileId: number | null;
  dateTaken: string | null;
  duration: number | null;
}

export interface UnifiedSearchResponse {
  query: string;
  page: number;
  pageSize: number;
  totalResults: number;
  totalPages: number;
  results: UnifiedSearchResult[];
}

export async function searchUnified(
  query: string,
  modelId: string,
  mediaType: "all" | "image" | "video" = "all",
  page = 1,
  pageSize = 50,
): Promise<UnifiedSearchResponse> {
  const raw = await apiRequest<any>("/api/search/unified", {
    method: "POST",
    body: JSON.stringify({ query, modelId, mediaType, page, pageSize }),
  });
  return {
    query: String(raw.query ?? ""),
    page: Number(raw.page ?? 1),
    pageSize: Number(raw.pageSize ?? 50),
    totalResults: Number(raw.totalResults ?? 0),
    totalPages: Number(raw.totalPages ?? 0),
    results: Array.isArray(raw.results)
      ? raw.results.map((r: any) => ({
          id: String(r.id),
          score: Number(r.score ?? 0),
          mediaType: r.mediaType === "video" ? "video" : "image",
          filePath: r.filePath ?? null,
          fileId: r.fileId != null ? Number(r.fileId) : null,
          dateTaken: r.dateTaken ?? null,
          duration: r.duration != null ? Number(r.duration) : null,
        }))
      : [],
  };
}

export async function getSimilarImages(
  imageId: string | number,
  limit = 24,
): Promise<ImageResult[]> {
  return (
    await apiRequest<any[]>(`/api/search/similar/${imageId}?limit=${limit}`)
  ).map(mapImage);
}

export async function searchByImageFile(
  file: File,
  limit = 24,
): Promise<ImageResult[]> {
  const body = new FormData();
  body.append("file", file);
  return (
    await apiRequest<any[]>(`/api/search/by-image?limit=${limit}`, {
      method: "POST",
      body,
    })
  ).map(mapImage);
}

export async function uploadFaceSearchPhoto(
  file: File,
): Promise<{ path: string; filename: string }> {
  const body = new FormData();
  body.append("file", file);
  const raw = await apiRequest<any>("/api/search/face-photo", {
    method: "POST",
    body,
  });
  return {
    path: String(raw.path ?? ""),
    filename: String(raw.filename ?? file.name),
  };
}

export async function getFavorites(): Promise<ImageResult[]> {
  return (await apiRequest<any[]>("/api/images/indexed?favorite=true")).map(
    mapImage,
  );
}

export async function toggleFavorite(
  imageId: string,
  isFavorite: boolean,
): Promise<void> {
  await apiRequest(`/api/images/indexed/${imageId}/favorite`, {
    method: "PATCH",
    body: JSON.stringify({ isFavorite }),
  });
}

export async function openImageExternally(
  imageId: string | number,
): Promise<void> {
  await apiRequest(`/api/images/indexed/${imageId}/open-external`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function getPeople(limit = 1000): Promise<PersonInfo[]> {
  return (await apiRequest<any[]>(`/api/people/?limit=${limit}`)).map(
    mapPerson,
  );
}

export async function renamePerson(
  personId: string,
  name: string,
): Promise<void> {
  await apiRequest(`/api/people/${personId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export async function mergePeople(
  targetPersonId: string,
  sourcePersonId: string,
): Promise<PersonMergeResult> {
  const raw = await apiRequest<any>(`/api/people/${targetPersonId}/merge`, {
    method: "POST",
    body: JSON.stringify({ sourcePersonId: Number(sourcePersonId) }),
  });

  return {
    targetPersonId: String(raw.targetPersonId ?? targetPersonId),
    sourcePersonId: String(raw.sourcePersonId ?? sourcePersonId),
    imageCount: Number(raw.imageCount ?? 0),
    name: raw.name ?? null,
  };
}

export async function getPersonImages(
  personId: string,
  options?: { skip?: number; limit?: number },
): Promise<ImageResult[]> {
  const params = new URLSearchParams();
  if (options?.skip !== undefined) params.set("skip", String(options.skip));
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  const query = params.toString();
  return (
    await apiRequest<any[]>(
      `/api/people/${personId}/images${query ? `?${query}` : ""}`,
    )
  ).map(mapImage);
}

export async function getCollections(): Promise<CollectionInfo[]> {
  const collections = (await apiRequest<any[]>("/api/collections/")).map(
    mapCollection,
  );
  return Promise.all(
    collections.map(async (collection) => {
      if (collection.previewUrls.length > 0 || collection.imageCount === 0) {
        return collection;
      }
      try {
        const images = await getCollectionImages(collection.id);
        return {
          ...collection,
          imageCount: images.length,
          previewUrls: images
            .slice(0, 4)
            .map((image) => image.thumbnailUrl ?? image.url),
        };
      } catch {
        return collection;
      }
    }),
  );
}

export async function createCollection(
  name: string,
  description?: string,
): Promise<CollectionInfo> {
  return mapCollection(
    await apiRequest<any>("/api/collections/", {
      method: "POST",
      body: JSON.stringify({
        name,
        description,
        image_count: 0,
        modified_date: new Date().toISOString(),
      }),
    }),
  );
}

export async function deleteCollection(collectionId: string): Promise<void> {
  await apiRequest(`/api/collections/${collectionId}`, { method: "DELETE" });
}

export async function getCollectionImages(
  collectionId: string,
): Promise<ImageResult[]> {
  return (
    await apiRequest<any[]>(`/api/collections/${collectionId}/images`)
  ).map(mapImage);
}

export async function pickCollectionImages(
  collectionId: string,
): Promise<PickCollectionImagesResult> {
  const raw = await apiRequest<any>(
    `/api/collections/${collectionId}/pick-images`,
    {
      method: "POST",
      body: JSON.stringify({}),
    },
  );

  return {
    collectionId: String(raw.collectionId ?? collectionId),
    addedCount: Number(raw.addedCount ?? 0),
    autoIndexedCount: Number(raw.autoIndexedCount ?? 0),
    skippedPaths: Array.isArray(raw.skippedPaths)
      ? raw.skippedPaths.map(String)
      : [],
    imageCount: Number(raw.imageCount ?? 0),
  };
}

export async function getStorageSummary(): Promise<StorageSummary> {
  const raw = await apiRequest<any>("/api/index/storage-summary");
  return {
    indexPath: String(raw.indexPath ?? ""),
    indexSizeBytes: Number(raw.indexSizeBytes ?? 0),
    thumbnailCachePath: String(raw.thumbnailCachePath ?? ""),
    thumbnailCacheBytes: Number(raw.thumbnailCacheBytes ?? 0),
  };
}

export async function clearCache(): Promise<StorageSummary> {
  const raw = await apiRequest<any>("/api/index/clear-cache", {
    method: "POST",
    body: JSON.stringify({}),
  });
  return {
    indexPath: String(raw.indexPath ?? ""),
    indexSizeBytes: Number(raw.indexSizeBytes ?? 0),
    thumbnailCachePath: String(raw.thumbnailCachePath ?? ""),
    thumbnailCacheBytes: Number(raw.thumbnailCacheBytes ?? 0),
  };
}

export async function getSavedSearches(): Promise<SavedSearch[]> {
  return (await apiRequest<any[]>("/api/saved-searches/")).map(mapSavedSearch);
}

export async function createSavedSearch(
  name: string,
  query: string,
  filters: Record<string, unknown>,
): Promise<SavedSearch> {
  return mapSavedSearch(
    await apiRequest<any>("/api/saved-searches/", {
      method: "POST",
      body: JSON.stringify({
        name,
        query,
        filters,
        last_used: new Date().toISOString().slice(0, 10),
      }),
    }),
  );
}

export async function deleteSavedSearch(searchId: string): Promise<void> {
  await apiRequest(`/api/saved-searches/${searchId}`, { method: "DELETE" });
}
