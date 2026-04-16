import React, { createContext, useContext, ReactNode } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { type CollectionInfo } from "@/data/mockData";

interface CollectionContextType {
  collections: CollectionInfo[];
  isLoading: boolean;
  createCollection: (name: string, desc?: string) => Promise<void>;
  deleteCollection: (id: string) => Promise<void>;
}

const CollectionContext = createContext<CollectionContextType | null>(null);

export function CollectionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();

  const { data: collections = [], isLoading } = useQuery({
    queryKey: ["collections"],
    queryFn: () => api.collections.getAll() as Promise<CollectionInfo[]>,
    staleTime: 5 * 60 * 1000,
  });

  const createMutation = useMutation({
    mutationFn: ({ name, desc }: { name: string; desc?: string }) =>
      api.collections.create(name, desc),
    onSuccess: (newCollection) => {
      queryClient.setQueryData<CollectionInfo[]>(["collections"], (old = []) => [
        ...old,
        newCollection as CollectionInfo,
      ]);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.collections.delete(id),
    onSuccess: (_, id) => {
      queryClient.setQueryData<CollectionInfo[]>(["collections"], (old = []) =>
        old.filter((col) => col.id !== id)
      );
    },
  });

  const createCollection = async (name: string, desc?: string) => {
    await createMutation.mutateAsync({ name, desc });
  };

  const deleteCollection = async (id: string) => {
    await deleteMutation.mutateAsync(id);
  };

  return (
    <CollectionContext.Provider
      value={{
        collections,
        isLoading,
        createCollection,
        deleteCollection,
      }}
    >
      {children}
    </CollectionContext.Provider>
  );
}

export function useCollectionContext() {
  const ctx = useContext(CollectionContext);
  if (!ctx) throw new Error("useCollectionContext must be used within CollectionProvider");
  return ctx;
}
