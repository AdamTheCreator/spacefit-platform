import { create } from 'zustand';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type UploadStatus = 'uploading' | 'processing' | 'completed' | 'failed';

export interface UploadItem {
  /** Client-generated ID for tracking before we have a server document ID. */
  clientId: string;
  /** Server document ID, set once the upload HTTP response arrives. */
  documentId: string | null;
  fileName: string;
  fileSize: number;
  status: UploadStatus;
  /** 0–100 upload progress (only meaningful during 'uploading'). */
  uploadProgress: number;
  /** Human-readable status message. */
  statusText: string;
  /** Error message when status === 'failed'. */
  errorMessage: string | null;
  /** The original File reference, kept for retry. */
  file: File;
  /** Timestamp when the item was added. */
  addedAt: number;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

interface UploadStoreState {
  items: UploadItem[];

  /** Add a new file to the queue in 'uploading' state. Returns the clientId. */
  addItem: (file: File) => string;

  /** Update upload progress (0–100). */
  setUploadProgress: (clientId: string, progress: number) => void;

  /** Transition to 'processing' after the upload POST succeeds. */
  markUploaded: (clientId: string, documentId: string) => void;

  /** Transition to 'completed'. */
  markCompleted: (clientId: string) => void;

  /** Transition to 'failed' with an error message. */
  markFailed: (clientId: string, errorMessage: string) => void;

  /** Reset a failed item back to 'uploading' for retry. */
  resetForRetry: (clientId: string) => void;

  /** Remove an item from the queue. */
  removeItem: (clientId: string) => void;

  /** Remove all completed/failed items. */
  clearFinished: () => void;

  /** Look up an item by documentId (for polling transitions). */
  findByDocumentId: (documentId: string) => UploadItem | undefined;

  /** Transition an item to 'completed' by its documentId. */
  markCompletedByDocumentId: (documentId: string) => void;

  /** Transition an item to 'failed' by its documentId. */
  markFailedByDocumentId: (documentId: string, errorMessage: string) => void;
}

let nextId = 0;
function generateClientId(): string {
  return `upload_${Date.now()}_${nextId++}`;
}

export const useUploadStore = create<UploadStoreState>((set, get) => ({
  items: [],

  addItem: (file: File) => {
    const clientId = generateClientId();
    const item: UploadItem = {
      clientId,
      documentId: null,
      fileName: file.name,
      fileSize: file.size,
      status: 'uploading',
      uploadProgress: 0,
      statusText: 'Uploading…',
      errorMessage: null,
      file,
      addedAt: Date.now(),
    };
    set((state) => ({ items: [item, ...state.items] }));
    return clientId;
  },

  setUploadProgress: (clientId, progress) =>
    set((state) => ({
      items: state.items.map((item) =>
        item.clientId === clientId
          ? { ...item, uploadProgress: Math.min(progress, 100), statusText: `Uploading… ${Math.round(progress)}%` }
          : item,
      ),
    })),

  markUploaded: (clientId, documentId) =>
    set((state) => ({
      items: state.items.map((item) =>
        item.clientId === clientId
          ? {
              ...item,
              documentId,
              status: 'processing' as const,
              uploadProgress: 100,
              statusText: 'Extracting property info and spaces…',
            }
          : item,
      ),
    })),

  markCompleted: (clientId) =>
    set((state) => ({
      items: state.items.map((item) =>
        item.clientId === clientId
          ? { ...item, status: 'completed' as const, statusText: 'Completed' }
          : item,
      ),
    })),

  markFailed: (clientId, errorMessage) =>
    set((state) => ({
      items: state.items.map((item) =>
        item.clientId === clientId
          ? { ...item, status: 'failed' as const, statusText: 'Failed', errorMessage }
          : item,
      ),
    })),

  resetForRetry: (clientId) =>
    set((state) => ({
      items: state.items.map((item) =>
        item.clientId === clientId
          ? {
              ...item,
              status: 'uploading' as const,
              uploadProgress: 0,
              statusText: 'Uploading…',
              errorMessage: null,
              documentId: null,
            }
          : item,
      ),
    })),

  removeItem: (clientId) =>
    set((state) => ({
      items: state.items.filter((item) => item.clientId !== clientId),
    })),

  clearFinished: () =>
    set((state) => ({
      items: state.items.filter(
        (item) => item.status !== 'completed' && item.status !== 'failed',
      ),
    })),

  findByDocumentId: (documentId) =>
    get().items.find((item) => item.documentId === documentId),

  markCompletedByDocumentId: (documentId) =>
    set((state) => ({
      items: state.items.map((item) =>
        item.documentId === documentId
          ? { ...item, status: 'completed' as const, statusText: 'Completed' }
          : item,
      ),
    })),

  markFailedByDocumentId: (documentId, errorMessage) =>
    set((state) => ({
      items: state.items.map((item) =>
        item.documentId === documentId
          ? { ...item, status: 'failed' as const, statusText: 'Failed', errorMessage }
          : item,
      ),
    })),
}));
