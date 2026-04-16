import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { type FolderInfo } from "@/data/mockData";

export function useFolders() {
  return useQuery({
    queryKey: ["folders"],
    queryFn: () => api.folders.getAll() as Promise<FolderInfo[]>,
  });
}

export function useAddFolder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (path: string) => api.folders.add(path),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders"] });
    },
  });
}

export function useRemoveFolder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.folders.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders"] });
    },
  });
}
