import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';
import { useUploadStore } from '../stores/uploadStore';
import type {
  Project,
  ProjectDetail,
  ProjectListResponse,
  ProjectCreate,
  ProjectUpdate,
  ChatSessionBrief,
} from '../types/project';

// Query keys
export const projectKeys = {
  all: ['projects'] as const,
  lists: () => [...projectKeys.all, 'list'] as const,
  list: (params: { page?: number; search?: string }) =>
    [...projectKeys.lists(), params] as const,
  details: () => [...projectKeys.all, 'detail'] as const,
  detail: (id: string) => [...projectKeys.details(), id] as const,
};

function hasProcessingDocuments(project: ProjectDetail | undefined) {
  return (
    project?.documents.some(
      (doc) => doc.status === 'pending' || doc.status === 'processing',
    ) ?? false
  );
}

// List projects
export function useProjects(params: { page?: number; search?: string; archived?: boolean } = {}) {
  const { page = 1, search, archived = false } = params;

  return useQuery<ProjectListResponse>({
    queryKey: projectKeys.list(params),
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      searchParams.set('page', String(page));
      if (search) searchParams.set('search', search);
      if (archived) searchParams.set('archived', 'true');

      const response = await api.get<ProjectListResponse>(
        `/projects?${searchParams}`,
      );
      return response.data;
    },
  });
}

// Get single project detail
export function useProject(projectId: string | null) {
  const hasActiveProjectUploads = useUploadStore((s) =>
    s.items.some(
      (item) =>
        item.projectId === projectId &&
        (item.status === 'uploading' || item.status === 'processing'),
    ),
  );

  return useQuery<ProjectDetail>({
    queryKey: projectKeys.detail(projectId || ''),
    queryFn: async () => {
      const response = await api.get<ProjectDetail>(`/projects/${projectId}`);
      if (import.meta.env.DEV) {
        console.debug('[useProject] fetched project detail', {
          projectId,
          documentStatuses: response.data.documents.map((doc) => ({
            id: doc.id,
            status: doc.status,
          })),
        });
      }
      return response.data;
    },
    enabled: !!projectId,
    // Poll while the server still reports work in flight, or while the local
    // upload queue knows this project has an active upload and we are waiting
    // for the project detail query to observe that new document.
    refetchInterval: (query) => {
      const queryData = query.state.data as ProjectDetail | undefined;
      const serverHasProcessing = hasProcessingDocuments(queryData);
      if (import.meta.env.DEV) {
        console.debug('[useProject] refetchInterval evaluation', {
          projectId,
          hasActiveProjectUploads,
          serverHasProcessing,
          fetchStatus: query.state.fetchStatus,
          documentStatuses:
            queryData?.documents.map((doc) => ({
              id: doc.id,
              status: doc.status,
            })) ?? [],
        });
      }
      if (
        hasActiveProjectUploads ||
        serverHasProcessing
      ) {
        return 3000;
      }
      return false;
    },
    refetchIntervalInBackground: true,
  });
}

// Create project
export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: ProjectCreate) => {
      const response = await api.post<Project>('/projects', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.all });
    },
  });
}

// Update project
export function useUpdateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: ProjectUpdate;
    }) => {
      const response = await api.patch<Project>(`/projects/${id}`, data);
      return response.data;
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
    },
  });
}

// Archive / restore project
export function useArchiveProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, is_archived }: { id: string; is_archived: boolean }) => {
      const response = await api.patch<Project>(`/projects/${id}/archive`, { is_archived });
      return response.data;
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: projectKeys.all });
    },
  });
}

// Delete project
export function useDeleteProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/projects/${id}`);
    },
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: projectKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: projectKeys.all });
    },
  });
}

// Create a chat session within a project
export function useCreateProjectSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (projectId: string) => {
      const response = await api.post<ChatSessionBrief>(
        `/projects/${projectId}/sessions`,
      );
      return response.data;
    },
    onSuccess: (_, projectId) => {
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectId) });
    },
  });
}
