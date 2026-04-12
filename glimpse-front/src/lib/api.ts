const API_BASE_URL = "http://localhost:8000/api";

async function fetcher<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export const api = {
  // ===================================
  // 🟢 EXISTING APIS (Folders, Collections, Images, People)
  // ===================================
  
  images: {
    getAll: () => fetcher("/images/"),
    getById: (id: string) => fetcher(`/images/${id}`),
    toggleFavorite: (id: string, isFavorite: boolean) => 
      fetcher(`/images/${id}/favorite`, { method: "PUT", body: JSON.stringify({ isFavorite }) }),
  },

  folders: {
    getAll: () => fetcher("/folders/"),
    add: (path: string) => fetcher("/folders/", { method: "POST", body: JSON.stringify({ path }) }),
    delete: (id: string) => fetcher(`/folders/${id}`, { method: "DELETE" }),
  },

  collections: {
    getAll: () => fetcher("/collections/"),
    create: (name: string, description?: string) => 
      fetcher("/collections/", { method: "POST", body: JSON.stringify({ name, description }) }),
    delete: (id: string) => fetcher(`/collections/${id}`, { method: "DELETE" }),
  },

  people: {
    getAll: () => fetcher("/people/"),
    rename: (id: string, name: string) => 
      fetcher(`/people/${id}`, { method: "PUT", body: JSON.stringify({ name }) }),
  },

  // ===================================
  // 🔴 MISSING APIS (Need to be built next)
  // ===================================
  
  savedSearches: {
    // You created the service, but the router in `backend/api/` is missing!
    getAll: () => fetcher("/saved-searches/"),
    create: (data: { name: string, query: string, filters: Record<string, unknown> }) => 
      fetcher("/saved-searches/", { method: "POST", body: JSON.stringify(data) }),
    delete: (id: string) => fetcher(`/saved-searches/${id}`, { method: "DELETE" }),
  },

  models: {
    // Missing APIs for the AI Models
    getAll: () => fetcher("/models/"),
    download: (id: string) => fetcher(`/models/${id}/download`, { method: "POST" }),
    setActive: (id: string) => fetcher(`/models/${id}/active`, { method: "POST" }),
    remove: (id: string) => fetcher(`/models/${id}`, { method: "DELETE" }),
  },

  system: {
    // Missing APIs for indexing status and general app state (onboarding phase)
    startIndexing: () => fetcher("/system/index/start", { method: "POST" }),
    getIndexingStatus: () => fetcher("/system/index/status"),
    getSettings: () => fetcher("/system/settings"),
    updateSettings: (settings: any) => fetcher("/system/settings", { method: "PUT", body: JSON.stringify(settings) })
  }
};
