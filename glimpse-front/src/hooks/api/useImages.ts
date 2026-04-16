import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { type ImageResult } from "@/data/mockData";

export function useImages() {
  return useQuery({
    queryKey: ["images"],
    queryFn: () => api.images.getAll() as Promise<ImageResult[]>,
  });
}

export function useImageById(id: string) {
  return useQuery({
    queryKey: ["images", id],
    queryFn: () => api.images.getById(id) as Promise<ImageResult>,
    enabled: !!id,
  });
}

export function useToggleFavorite() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, isFav }: { id: string; isFav: boolean }) =>
      api.images.toggleFavorite(id, isFav),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["images"] });
    },
  });
}
