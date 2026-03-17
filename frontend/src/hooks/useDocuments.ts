import { useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';
import type {
  ParsedDocumentDetail,
  DocumentListResponse,
  DocumentUploadResponse,
  DocumentType,
  DocumentStatus,
  StartAnalysisResponse,
} from '../types/document';
import { useUploadStore } from '../stores/uploadStore';

interface DocumentsQueryParams {
  page?: number;
  pageSize?: number;
  documentType?: DocumentType;
  status?: DocumentStatus;
}

// Query keys
export const documentKeys = {
  all: ['documents'] as const,
  lists: () => [...documentKeys.all, 'list'] as const,
  list: (params: DocumentsQueryParams) => [...documentKeys.lists(), params] as const,
  details: () => [...documentKeys.all, 'detail'] as const,
  detail: (id: string) => [...documentKeys.details(), id] as const,
};

// Fetch documents list
export function useDocuments(params: DocumentsQueryParams = {}) {
  const { page = 1, pageSize = 20, documentType, status } = params;

  return useQuery<DocumentListResponse>({
    queryKey: documentKeys.list(params),
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      searchParams.set('page', String(page));
      searchParams.set('page_size', String(pageSize));
      if (documentType) searchParams.set('document_type', documentType);
      if (status) searchParams.set('status', status);

      const response = await api.get<DocumentListResponse>(`/documents?${searchParams}`);
      return response.data;
    },
    // Refetch periodically to check for processing updates
    refetchInterval: (query) => {
      // Only refetch if there are pending/processing documents
      const data = query.state.data;
      if (data?.items.some((doc) => doc.status === 'pending' || doc.status === 'processing')) {
        return 3000; // Refetch every 3 seconds
      }
      return false;
    },
  });
}

// Fetch single document with details
export function useDocument(documentId: string | null) {
  return useQuery<ParsedDocumentDetail>({
    queryKey: documentKeys.detail(documentId || ''),
    queryFn: async () => {
      const response = await api.get<ParsedDocumentDetail>(`/documents/${documentId}`);
      return response.data;
    },
    enabled: !!documentId,
    // Refetch if document is still processing
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === 'pending' || data?.status === 'processing') {
        return 2000;
      }
      return false;
    },
  });
}

// Upload document mutation
export function useUploadDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      propertyId,
      projectId,
      documentType,
    }: {
      file: File;
      propertyId?: string;
      projectId?: string;
      documentType?: DocumentType;
    }) => {
      const formData = new FormData();
      formData.append('file', file);
      if (propertyId) formData.append('property_id', propertyId);
      if (projectId) formData.append('project_id', projectId);
      if (documentType) formData.append('document_type', documentType);

      const response = await api.post<DocumentUploadResponse>('/documents/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentKeys.all });
    },
  });
}

// Archive / restore document
export function useArchiveDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, is_archived }: { id: string; is_archived: boolean }) => {
      const response = await api.patch(`/documents/${id}/archive`, { is_archived });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentKeys.all });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

// Delete document mutation
export function useDeleteDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: string) => {
      await api.delete(`/documents/${documentId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentKeys.all });
    },
  });
}

// Reprocess document mutation
export function useReprocessDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (documentId: string) => {
      const response = await api.post<DocumentUploadResponse>(`/documents/${documentId}/reprocess`);
      return response.data;
    },
    onSuccess: (_, documentId) => {
      queryClient.invalidateQueries({ queryKey: documentKeys.detail(documentId) });
      queryClient.invalidateQueries({ queryKey: documentKeys.lists() });
    },
  });
}

// Fetch document file as blob URL
export async function fetchDocumentFile(documentId: string): Promise<string> {
  const response = await api.get(`/documents/${documentId}/file`, {
    responseType: 'blob',
  });
  const blob = new Blob([response.data], { type: response.headers['content-type'] });
  return URL.createObjectURL(blob);
}

// Hook to get document file URL
export function useDocumentFile(documentId: string | null) {
  return useQuery<string>({
    queryKey: [...documentKeys.detail(documentId || ''), 'file'],
    queryFn: async () => {
      if (!documentId) throw new Error('No document ID');
      return fetchDocumentFile(documentId);
    },
    enabled: !!documentId,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    gcTime: 10 * 60 * 1000, // Keep in cache for 10 minutes
  });
}

// Property analysis types
export interface PropertyAnalysisResult {
  success: boolean;
  property_address: string | null;
  latitude: number | null;
  longitude: number | null;
  demographics: Record<string, unknown> | null;
  competitors: Array<{
    name: string;
    category: string;
    address: string;
    rating: number | null;
  }> | null;
  void_analysis: {
    property_summary?: string;
    categories?: Array<{
      category_name: string;
      is_void: boolean;
      match_score: number;
      priority: string;
      rationale?: string;
      suggested_tenants?: string[];
    }>;
    summary?: {
      total_voids: number;
      high_priority: string[];
      medium_priority?: string[];
      well_served?: string[];
      key_recommendation?: string;
    };
  } | null;
  investment_memo: Record<string, unknown> | null;
  errors: string[] | null;
}

// Start analysis session from document (fast endpoint)
export function useStartAnalysis() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      documentId,
      analysisType = 'void_analysis',
      tradeAreaMiles = 3.0,
      notes,
    }: {
      documentId: string;
      analysisType?: string;
      tradeAreaMiles?: number;
      notes?: string;
    }) => {
      const { data } = await api.post<StartAnalysisResponse>(
        `/documents/${documentId}/start-analysis`,
        {
          analysis_type: analysisType,
          trade_area_miles: tradeAreaMiles,
          notes: notes || null,
        },
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Upload with progress tracking — bridges to the upload store
// ---------------------------------------------------------------------------

/**
 * Upload a single file with real progress tracking via axios onUploadProgress.
 * Manages transitions in the upload store automatically:
 *   file selected → uploading (with %) → processing → completed/failed
 *
 * Processing→completed is handled by `useUploadStatusSync`.
 */
export function useUploadWithProgress() {
  const queryClient = useQueryClient();
  const store = useUploadStore.getState;

  const uploadFile = useCallback(
    async (file: File) => {
      const clientId = store().addItem(file);
      const formData = new FormData();
      formData.append('file', file);

      try {
        const response = await api.post<DocumentUploadResponse>(
          '/documents/upload',
          formData,
          {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (event) => {
              if (event.total) {
                const pct = Math.round((event.loaded / event.total) * 100);
                store().setUploadProgress(clientId, pct);
              }
            },
          },
        );

        // Upload HTTP done — document now in 'pending'/'processing' on server
        store().markUploaded(clientId, response.data.id);
        queryClient.invalidateQueries({ queryKey: documentKeys.all });
        return response.data;
      } catch (error: unknown) {
        const msg =
          error instanceof Error ? error.message : 'Upload failed';
        store().markFailed(clientId, msg);
        throw error;
      }
    },
    [queryClient, store],
  );

  return { uploadFile };
}

/**
 * Watches the document list query and transitions upload-store items
 * from 'processing' to 'completed' or 'failed' when the server status changes.
 *
 * Call this once in the page that shows the upload queue.
 */
export function useUploadStatusSync(documents: DocumentListResponse | undefined) {
  const items = useUploadStore((s) => s.items);
  const markCompletedByDocId = useUploadStore((s) => s.markCompletedByDocumentId);
  const markFailedByDocId = useUploadStore((s) => s.markFailedByDocumentId);

  useEffect(() => {
    if (!documents?.items) return;

    // Only check items currently in 'processing'
    const processingItems = items.filter(
      (i) => i.status === 'processing' && i.documentId,
    );
    if (processingItems.length === 0) return;

    for (const item of processingItems) {
      const serverDoc = documents.items.find((d) => d.id === item.documentId);
      if (!serverDoc) continue;

      if (serverDoc.status === 'completed') {
        markCompletedByDocId(serverDoc.id);
      } else if (serverDoc.status === 'failed') {
        markFailedByDocId(
          serverDoc.id,
          serverDoc.error_message || 'Processing failed',
        );
      }
      // 'pending' and 'processing' — keep waiting
    }
  }, [documents, items, markCompletedByDocId, markFailedByDocId]);
}

// Run property analysis mutation
export function usePropertyAnalysis() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      documentId,
      includeDemographics = true,
      includeCompetitors = true,
      includeVoidAnalysis = true,
      includeMemo = false,
      radiusMiles = 3.0,
    }: {
      documentId: string;
      includeDemographics?: boolean;
      includeCompetitors?: boolean;
      includeVoidAnalysis?: boolean;
      includeMemo?: boolean;
      radiusMiles?: number;
    }) => {
      const params = new URLSearchParams();
      params.set('include_demographics', String(includeDemographics));
      params.set('include_competitors', String(includeCompetitors));
      params.set('include_void_analysis', String(includeVoidAnalysis));
      params.set('include_memo', String(includeMemo));
      params.set('radius_miles', String(radiusMiles));

      const response = await api.post<PropertyAnalysisResult>(
        `/documents/${documentId}/analyze?${params}`
      );
      return response.data;
    },
    onSuccess: (_, { documentId }) => {
      queryClient.invalidateQueries({ queryKey: documentKeys.detail(documentId) });
    },
  });
}
