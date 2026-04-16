import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { type PersonInfo } from "@/data/mockData";

export function usePeople() {
  return useQuery({
    queryKey: ["people"],
    queryFn: () => api.people.getAll() as Promise<PersonInfo[]>,
  });
}

export function useRenamePerson() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      api.people.rename(id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["people"] });
    },
  });
}
