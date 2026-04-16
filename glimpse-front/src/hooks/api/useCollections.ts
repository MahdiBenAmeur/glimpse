import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { type CollectionInfo } from "@/data/mockData";

export function useCollections() {
  return useQuery({
    queryKey: ["collections"],
    queryFn: () => api.collections.getAll() as Promise<CollectionInfo[]>,
  });
}

export function useCreateCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, desc }: { name: string; desc?: string }) =>
      api.collections.create(name, desc),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });
}

export function useDeleteCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.collections.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });
}
