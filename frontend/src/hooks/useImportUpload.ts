import { useCallback, useState } from 'react';
import api from '../lib/axios';

export type ImportSource = 'costar' | 'placer' | 'siteusa';
export type ImportUploadStatus = 'idle' | 'uploading' | 'parsing' | 'ready' | 'error';

export interface ImportUploadState {
  status: ImportUploadStatus;
  fileName: string | null;
  error: string | null;
}

export function detectImportSource(file: File): ImportSource {
  const name = file.name.toLowerCase();
  if (name.endsWith('.pdf')) return 'placer';
  return 'costar';
}

export function useImportUpload(projectId?: string) {
  const [state, setState] = useState<Record<ImportSource, ImportUploadState>>(() => ({
    costar: { status: 'idle', fileName: null, error: null },
    placer: { status: 'idle', fileName: null, error: null },
    siteusa: { status: 'idle', fileName: null, error: null },
  }));

  const reset = useCallback((source: ImportSource) => {
    setState((prev) => ({
      ...prev,
      [source]: { status: 'idle', fileName: null, error: null },
    }));
  }, []);

  const upload = useCallback(
    async (
      file: File,
      source: ImportSource,
      onComplete?: () => void,
    ) => {
      setState((prev) => ({
        ...prev,
        [source]: { status: 'uploading', fileName: file.name, error: null },
      }));

      const formData = new FormData();
      formData.append('file', file);
      const endpoint = projectId
        ? `/projects/${projectId}/imports/${source}`
        : `/imports/${source}`;

      try {
        const res = await api.post(endpoint, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        const jobId = res.data.id;
        setState((prev) => ({
          ...prev,
          [source]: { ...prev[source], status: 'parsing' },
        }));

        for (let i = 0; i < 60; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          const detail = await api.get(`/imports/${jobId}`);
          if (detail.data.status === 'ready') {
            setState((prev) => ({
              ...prev,
              [source]: { ...prev[source], status: 'ready' },
            }));
            onComplete?.();
            return;
          }
          if (detail.data.status === 'error') {
            setState((prev) => ({
              ...prev,
              [source]: {
                ...prev[source],
                status: 'error',
                error: detail.data.error_message || 'Parse failed',
              },
            }));
            return;
          }
        }
        setState((prev) => ({
          ...prev,
          [source]: {
            ...prev[source],
            status: 'error',
            error: 'Timed out waiting for parse',
          },
        }));
      } catch (err: unknown) {
        setState((prev) => ({
          ...prev,
          [source]: {
            ...prev[source],
            status: 'error',
            error: err instanceof Error ? err.message : 'Upload failed',
          },
        }));
      }
    },
    [projectId],
  );

  return { state, upload, reset };
}
