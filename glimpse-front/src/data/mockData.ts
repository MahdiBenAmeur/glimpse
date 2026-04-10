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
  url: string;
  filename: string;
  folder: string;
  dateTaken: string;
  width: number;
  height: number;
  isFavorite: boolean;
  faceCount: number;
  people: string[];
  collections: string[];
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

export const MOCK_MODELS: ModelInfo[] = [
  {
    id: "clip-vit-b32",
    name: "CLIP ViT-B/32",
    description: "Good balance of speed and quality. Recommended for most users.",
    quality: "standard",
    speed: "fast",
    diskSize: "340 MB",
    suitability: "CPU & GPU",
    status: "not_installed",
  },
  {
    id: "clip-vit-l14",
    name: "CLIP ViT-L/14",
    description: "Higher quality embeddings with better semantic understanding.",
    quality: "high",
    speed: "moderate",
    diskSize: "890 MB",
    suitability: "GPU recommended",
    status: "not_installed",
  },
  {
    id: "siglip-so400m",
    name: "SigLIP SO400M",
    description: "Best quality for nuanced queries and fine details.",
    quality: "best",
    speed: "slow",
    diskSize: "1.5 GB",
    suitability: "GPU required",
    status: "not_installed",
  },
];

export const MOCK_FOLDERS: FolderInfo[] = [
  { id: "f1", path: "/Users/alex/Photos/2024", imageCount: 2847, lastScanTime: "2024-03-15T10:30:00Z", status: "ready", includeSubfolders: true },
  { id: "f2", path: "/Users/alex/Photos/Family", imageCount: 1203, lastScanTime: "2024-03-15T10:30:00Z", status: "ready", includeSubfolders: true },
  { id: "f3", path: "/Users/alex/Desktop/Screenshots", imageCount: 456, lastScanTime: "2024-03-14T08:00:00Z", status: "ready", includeSubfolders: false },
];

const SAMPLE_IMAGES = [
  "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=400&h=300&fit=crop",
  "https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=400&h=500&fit=crop",
  "https://images.unsplash.com/photo-1501785888041-af3ef285b470?w=400&h=350&fit=crop",
  "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=400&h=400&fit=crop",
  "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=400&h=300&fit=crop",
  "https://images.unsplash.com/photo-1518173946687-a4c26634babd?w=400&h=450&fit=crop",
  "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=300&h=400&fit=crop",
  "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=400&h=400&fit=crop",
  "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=400&h=500&fit=crop",
  "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=350&fit=crop",
  "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&h=400&fit=crop",
  "https://images.unsplash.com/photo-1488590528505-98d2b5aba04b?w=400&h=300&fit=crop",
  "https://images.unsplash.com/photo-1518770660439-4636190af475?w=400&h=350&fit=crop",
  "https://images.unsplash.com/photo-1649972904349-6e44c42644a7?w=400&h=450&fit=crop",
  "https://images.unsplash.com/photo-1486312338219-ce68d2c6f44d?w=400&h=300&fit=crop",
  "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=400&h=400&fit=crop",
];

export const MOCK_PEOPLE: PersonInfo[] = [
  { id: "p1", name: "Lina", faceUrl: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=80&h=80&fit=crop&crop=face", imageCount: 234, lastSeen: "2024-03-15" },
  { id: "p2", name: "Omar", faceUrl: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=80&h=80&fit=crop&crop=face", imageCount: 189, lastSeen: "2024-03-14" },
  { id: "p3", name: "Sara", faceUrl: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=80&h=80&fit=crop&crop=face", imageCount: 156, lastSeen: "2024-03-15" },
  { id: "p4", name: null, faceUrl: "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=80&h=80&fit=crop&crop=face", imageCount: 45, lastSeen: "2024-03-12" },
  { id: "p5", name: null, faceUrl: "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=80&h=80&fit=crop&crop=face", imageCount: 23, lastSeen: "2024-03-10" },
  { id: "p6", name: "David", faceUrl: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=80&h=80&fit=crop&crop=face", imageCount: 78, lastSeen: "2024-03-13" },
];

export const MOCK_IMAGES: ImageResult[] = SAMPLE_IMAGES.map((url, i) => ({
  id: `img-${i}`,
  url,
  filename: `IMG_${2000 + i}.jpg`,
  folder: MOCK_FOLDERS[i % 3].path,
  dateTaken: `2024-0${(i % 3) + 1}-${String((i % 28) + 1).padStart(2, "0")}`,
  width: 3000 + i * 100,
  height: 2000 + i * 150,
  isFavorite: i % 4 === 0,
  faceCount: i % 3,
  people: i % 3 === 0 ? ["Lina"] : i % 3 === 1 ? ["Omar", "Sara"] : [],
  collections: i % 5 === 0 ? ["Vacation 2024"] : [],
}));

export const MOCK_COLLECTIONS: CollectionInfo[] = [
  { id: "c1", name: "Vacation 2024", description: "Summer trip photos", imageCount: 84, previewUrls: SAMPLE_IMAGES.slice(0, 4), modifiedDate: "2024-03-10" },
  { id: "c2", name: "Best Portraits", description: "Favorite portrait shots", imageCount: 32, previewUrls: SAMPLE_IMAGES.slice(4, 8), modifiedDate: "2024-03-12" },
  { id: "c3", name: "Nature & Landscapes", imageCount: 56, previewUrls: SAMPLE_IMAGES.slice(8, 12), modifiedDate: "2024-03-08" },
];

export const MOCK_SAVED_SEARCHES: SavedSearch[] = [
  { id: "ss1", name: "Sunset photos", query: "sunset on the beach", filters: { folder: "/Users/alex/Photos/2024" }, lastUsed: "2024-03-15" },
  { id: "ss2", name: "Family group shots", query: "group photo indoors", filters: { containsFaces: true, people: ["Lina", "Omar"] }, lastUsed: "2024-03-14" },
  { id: "ss3", name: "City at night", query: "city skyline at night", filters: {}, lastUsed: "2024-03-10" },
];

export const EXAMPLE_SEARCHES = [
  "sunset on the beach with Lina",
  "a red car at night",
  "group selfie indoors",
  "mountain landscape with snow",
  "birthday party with cake",
  "dog playing in the park",
];
