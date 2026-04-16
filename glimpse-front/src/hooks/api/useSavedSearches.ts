import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { type SavedSearch } from "@/data/mockData";

export function useSavedSearches() {
  return useQuery({
    queryKey: ["savedSearches"],
    queryFn: () => api.savedSearches.getAll() as Promise<SavedSearch[]>,
  });
}

export function useSaveSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { name: string; query: string; filters: Record<string, unknown> }) =>
      api.savedSearches.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["savedSearches"] });
    },
  });
}

export function useDeleteSavedSearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.savedSearches.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["savedSearches"] });
    },
  });
}
