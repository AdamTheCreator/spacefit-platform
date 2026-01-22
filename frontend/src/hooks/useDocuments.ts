import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';
import type {
  ParsedDocumentDetail,
  DocumentListResponse,
  DocumentUploadResponse,
  DocumentType,
  DocumentStatus,
} from '../types/document';

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
      documentType,
    }: {
      file: File;
      propertyId?: string;
      documentType?: DocumentType;
    }) => {
      const formData = new FormData();
      formData.append('file', file);
      if (propertyId) formData.append('property_id', propertyId);
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
