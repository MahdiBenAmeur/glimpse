export interface ModelInfo {
  id: string;
  name: string;
  description: string;
  quality: "standard" | "high" | "best";
  speed: "fast" | "moderate" | "slow";
  diskSize: string;
  suitability: string;
  status: "not_installed" | "downloading" | "installed" | "active";
  downloadProgress?: number;
}

export interface FolderInfo {
  id: string;
  path: string;
  imageCount: number;
  lastScanTime: string;
  status: "ready" | "scanning" | "missing" | "error";
  includeSubfolders: boolean;
}

export interface PersonInfo {
  id: string;
  name: string | null;
  faceUrl: string;
  imageCount: number;
  lastSeen?: string;
}

export interface ImageResult {
  id: string;
  imageId?: number;
  url: string;
  thumbnailUrl?: string;
  path?: string;
  filename: string;
  folder: string;
  dateTaken: string;
  width: number;
  height: number;
  isFavorite: boolean;
  faceCount: number;
  people: string[];
  collections: string[];
  score?: number;
}

export interface CollectionInfo {
  id: string;
  name: string;
  description?: string;
  imageCount: number;
  previewUrls: string[];
  modifiedDate: string;
}

export interface SavedSearch {
  id: string;
  name: string;
  query: string;
  filters: Record<string, unknown>;
  lastUsed: string;
}
