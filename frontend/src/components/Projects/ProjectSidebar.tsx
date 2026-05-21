import { useState, useRef, useCallback, useEffect, type DragEvent } from 'react';
import {
  Plus,
  Pencil,
  Check,
  X,
  Upload,
  PanelRightClose,
  PanelRightOpen,
  FileText,
  Database,
  StickyNote,
} from 'lucide-react';
import { toast } from 'sonner';
import { useUpdateProject, projectKeys } from '../../hooks/useProjects';
import {
  useArchiveDocument,
  useDeleteDocument,
  documentKeys,
} from '../../hooks/useDocuments';
import { useUploadStore, type UploadItem } from '../../stores/uploadStore';
import { DocumentCard } from './DocumentCard';
import { ProjectDocumentPreviewModal } from './ProjectDocumentPreviewModal';
import { DataImportsSection } from '../Imports/DataImportsSection';
import type { ProjectDetail } from '../../types/project';
import type { DocumentUploadResponse, ParsedDocument } from '../../types/document';
import api from '../../lib/axios';
import { useQueryClient } from '@tanstack/react-query';

interface ProjectSidebarProps {
  project: ProjectDetail;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
}

function getEstimatedProcessingProgress(item: UploadItem, now: number) {
  if (item.status !== 'processing') return item.uploadProgress;
  const startedAt = item.processingStartedAt ?? item.addedAt;
  const elapsed = Math.max(now - startedAt, 0);
  const estimated = 8 + (elapsed / 30000) * 84;
  return Math.min(Math.round(estimated), 96);
}

export function ProjectSidebar({
  project,
  collapsed = false,
  onToggleCollapsed,
}: ProjectSidebarProps) {
  const [editingInstructions, setEditingInstructions] = useState(false);
  const [instructions, setInstructions] = useState(
    project.instructions || '',
  );
  const [previewDocument, setPreviewDocument] = useState<ParsedDocument | null>(null);
  const [progressNow, setProgressNow] = useState(() => Date.now());
  const [isDragging, setIsDragging] = useState(false);
  const updateProject = useUpdateProject();
  const archiveDocument = useArchiveDocument();
  const deleteDocument = useDeleteDocument();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const store = useUploadStore.getState;
  const uploadItems = useUploadStore((s) => s.items);
  const markCompletedByDocId = useUploadStore((s) => s.markCompletedByDocumentId);
  const markFailedByDocId = useUploadStore((s) => s.markFailedByDocumentId);
  const queryClient = useQueryClient();
  const activeUploadItems = uploadItems.filter(
    (item) => item.status === 'uploading' || item.status === 'processing',
  );
  const activeUploadDocumentIds = new Set(
    activeUploadItems
      .map((item) => item.documentId)
      .filter((documentId): documentId is string => Boolean(documentId)),
  );
  const visibleDocuments = project.documents.filter(
    (doc) => !activeUploadDocumentIds.has(doc.id),
  );

  useEffect(() => {
    if (!activeUploadItems.some((item) => item.status === 'processing')) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      setProgressNow(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [activeUploadItems]);

  // Sync project document statuses → upload store (same role as useUploadStatusSync)
  useEffect(() => {
    if (!project.documents.length) return;

    const processingItems = uploadItems.filter(
      (i) => i.status === 'processing' && i.documentId,
    );
    if (processingItems.length === 0) return;

    for (const item of processingItems) {
      const serverDoc = project.documents.find((d) => d.id === item.documentId);
      if (!serverDoc) continue;

      if (import.meta.env.DEV) {
        console.debug('[ProjectSidebar] syncing upload item with server document', {
          projectId: project.id,
          documentId: serverDoc.id,
          uploadStatus: item.status,
          serverStatus: serverDoc.status,
        });
      }

      if (serverDoc.status === 'completed') {
        markCompletedByDocId(serverDoc.id);
      } else if (serverDoc.status === 'failed') {
        markFailedByDocId(
          serverDoc.id,
          serverDoc.error_message || 'Processing failed',
        );
      }
    }
  }, [project.documents, project.id, uploadItems, markCompletedByDocId, markFailedByDocId]);

  const handleSaveInstructions = async () => {
    await updateProject.mutateAsync({
      id: project.id,
      data: { instructions: instructions.trim() || undefined },
    });
    setEditingInstructions(false);
  };

  const handleFileUpload = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;

      // Reset the input so re-selecting the same file still fires onChange.
      if (fileInputRef.current) fileInputRef.current.value = '';

      for (const file of Array.from(files)) {
        const clientId = store().addItem(file, project.id);
        toast.success(`Added "${file.name}"`);
        const formData = new FormData();
        formData.append('file', file);
        formData.append('project_id', project.id);

        if (import.meta.env.DEV) {
          console.debug('[ProjectSidebar] starting upload', {
            projectId: project.id,
            clientId,
            fileName: file.name,
            fileSize: file.size,
          });
        }

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
          store().markUploaded(clientId, response.data.id);

          // Seed the file-URL cache with the already-in-memory File so the
          // first preview opens instantly (zero network).
          const localUrl = URL.createObjectURL(file);
          queryClient.setQueryData(
            [...documentKeys.detail(response.data.id), 'file'],
            localUrl,
          );

          if (import.meta.env.DEV) {
            console.debug('[ProjectSidebar] upload completed, invalidating project', {
              projectId: project.id,
              clientId,
              documentId: response.data.id,
              documentStatus: response.data.status,
            });
          }
          queryClient.invalidateQueries({
            queryKey: projectKeys.detail(project.id),
          });
        } catch (error: unknown) {
          const msg =
            error instanceof Error ? error.message : 'Upload failed';
          if (import.meta.env.DEV) {
            console.debug('[ProjectSidebar] upload failed', {
              projectId: project.id,
              clientId,
              error: msg,
            });
          }
          store().markFailed(clientId, msg);
        }
      }
    },
    [project.id, queryClient, store],
  );

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    // Only clear when leaving the drop container itself (not a child).
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      handleFileUpload(e.dataTransfer.files);
    },
    [handleFileUpload],
  );

  const handleArchiveDoc = async (doc: ParsedDocument) => {
    try {
      await archiveDocument.mutateAsync({ id: doc.id, is_archived: true });
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(project.id) });
      toast.success(`Archived "${doc.filename}"`);
    } catch {
      toast.error('Failed to archive document');
    }
  };

  const handleDeleteDoc = async (doc: ParsedDocument) => {
    try {
      await deleteDocument.mutateAsync(doc.id);
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(project.id) });
      toast.success(`Deleted "${doc.filename}"`);
    } catch {
      toast.error('Failed to delete document');
    }
  };

  const prop = project.property;

  if (collapsed) {
    const expand = () => onToggleCollapsed?.();
    return (
      <>
        <div className="h-full flex flex-col items-center gap-3 py-3 px-1">
          <button
            type="button"
            onClick={onToggleCollapsed}
            title="Expand panel"
            aria-label="Expand panel"
            className="p-2 rounded-lg text-industrial-muted hover:bg-[var(--bg-tertiary)] hover:text-industrial-secondary transition-colors"
          >
            <PanelRightOpen size={16} />
          </button>
          <div className="w-8 h-px bg-[var(--border-subtle)]" />
          <button
            type="button"
            onClick={expand}
            title="Instructions"
            aria-label="Instructions"
            className="p-2 rounded-lg text-industrial-muted hover:bg-[var(--bg-tertiary)] hover:text-industrial transition-colors"
          >
            <StickyNote size={16} />
          </button>
          <button
            type="button"
            onClick={expand}
            title={`Documents (${project.documents.length})`}
            aria-label={`Documents (${project.documents.length})`}
            className="relative p-2 rounded-lg text-industrial-muted hover:bg-[var(--bg-tertiary)] hover:text-industrial transition-colors"
          >
            <FileText size={16} />
            {project.documents.length > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-3.5 px-1 rounded-full bg-[var(--accent)] text-[9px] font-semibold text-white flex items-center justify-center">
                {project.documents.length}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={expand}
            title="Data Imports"
            aria-label="Data Imports"
            className="p-2 rounded-lg text-industrial-muted hover:bg-[var(--bg-tertiary)] hover:text-industrial transition-colors"
          >
            <Database size={16} />
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="h-full overflow-y-auto p-4 space-y-4 scrollbar-thin">
        {/* Collapse toggle */}
        {onToggleCollapsed && (
          <div className="flex items-center justify-end -mt-1 -mr-1">
            <button
              type="button"
              onClick={onToggleCollapsed}
              title="Collapse panel"
              aria-label="Collapse panel"
              className="p-1.5 rounded-md text-industrial-muted hover:bg-[var(--bg-tertiary)] hover:text-industrial-secondary transition-colors"
            >
              <PanelRightClose size={15} />
            </button>
          </div>
        )}

        {/* Property overview */}
        {prop && (
          <div>
            <h3 className="text-[11px] font-bold text-industrial-muted uppercase tracking-widest mb-2">
              Property
            </h3>
            <div className="text-sm text-industrial space-y-0.5">
              <p className="font-medium">{prop.name}</p>
              <p className="text-xs text-industrial-muted">
                {prop.address}, {prop.city}, {prop.state} {prop.zip_code}
              </p>
              <div className="flex items-center gap-2 text-xs text-industrial-muted mt-1">
                {prop.property_type && <span>{prop.property_type}</span>}
                {prop.total_sf && <span>{prop.total_sf.toLocaleString()} SF</span>}
              </div>
            </div>
          </div>
        )}

        {/* Instructions */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[11px] font-bold text-industrial-muted uppercase tracking-widest">
              Instructions
            </h3>
            {!editingInstructions ? (
              <button
                onClick={() => setEditingInstructions(true)}
                className="p-1 rounded text-industrial-muted hover:text-[var(--accent)] transition-colors"
                title="Edit instructions"
              >
                <Pencil size={12} />
              </button>
            ) : (
              <div className="flex items-center gap-1">
                <button
                  onClick={handleSaveInstructions}
                  disabled={updateProject.isPending}
                  className="p-1 rounded text-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors"
                  title="Save"
                >
                  <Check size={14} />
                </button>
                <button
                  onClick={() => {
                    setInstructions(project.instructions || '');
                    setEditingInstructions(false);
                  }}
                  className="p-1 rounded text-industrial-muted hover:bg-[var(--bg-tertiary)] transition-colors"
                  title="Cancel"
                >
                  <X size={14} />
                </button>
              </div>
            )}
          </div>
          {editingInstructions ? (
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Add custom instructions for AI chats in this project..."
              rows={4}
              className="w-full px-3 py-2 rounded-lg border border-[var(--accent)]/30 bg-[var(--bg-secondary)] text-xs text-industrial placeholder:text-industrial-muted focus:outline-none focus:border-[var(--accent)]/50 transition-colors resize-none"
              autoFocus
            />
          ) : (
            <p className="text-xs text-industrial-muted italic">
              {project.instructions || 'No custom instructions set'}
            </p>
          )}
        </div>

        {/* Documents */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[11px] font-bold text-industrial-muted uppercase tracking-widest">
              Documents ({project.documents.length})
            </h3>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="p-1 rounded text-industrial-muted hover:text-[var(--accent)] transition-colors"
              title="Upload document"
            >
              <Plus size={14} />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.gif,.webp"
              multiple
              className="hidden"
              onChange={(e) => handleFileUpload(e.target.files)}
            />
          </div>

          {/* Upload progress — rendered directly under the header so feedback
              appears exactly where the user clicked / dropped. */}
          {activeUploadItems.length > 0 && (
            <div className="mb-2 space-y-2">
              {activeUploadItems.map((item) => {
                const displayProgress =
                  item.status === 'uploading'
                    ? item.uploadProgress
                    : getEstimatedProcessingProgress(item, progressNow);
                return (
                  <div
                    key={item.clientId}
                    className="animate-slide-down p-3 rounded-2xl border border-[var(--accent)]/20 bg-[var(--accent-subtle)]"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-industrial truncate mr-2">
                        {item.fileName}
                      </span>
                      <span className="text-[11px] text-[var(--accent)] whitespace-nowrap">
                        {displayProgress}%
                      </span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-[var(--border-subtle)] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[var(--accent)] transition-all duration-300"
                        style={{ width: `${displayProgress}%` }}
                      />
                    </div>
                    <p className="text-[11px] text-industrial-muted mt-1.5">
                      {item.status === 'uploading'
                        ? item.statusText
                        : `Extracting property info and spaces… ${displayProgress}%`}
                    </p>
                  </div>
                );
              })}
            </div>
          )}

          <div
            onDragOver={handleDragOver}
            onDragEnter={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {visibleDocuments.length > 0 ? (
              <div
                className={`space-y-2 rounded-lg transition-all ${
                  isDragging
                    ? 'ring-2 ring-[var(--accent)]/40 ring-offset-2 ring-offset-[var(--bg-secondary)] scale-[1.01]'
                    : ''
                }`}
              >
                {visibleDocuments.map((doc) => (
                  <DocumentCard
                    key={doc.id}
                    document={doc}
                    onClick={() => setPreviewDocument(doc)}
                    onArchive={handleArchiveDoc}
                    onDelete={handleDeleteDoc}
                  />
                ))}
              </div>
            ) : (
              <button
                onClick={() => fileInputRef.current?.click()}
                className={`w-full py-6 rounded-lg border border-dashed text-xs transition-all flex flex-col items-center gap-2 ${
                  isDragging
                    ? 'border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent)] scale-[1.01]'
                    : 'border-[var(--border-subtle)] text-industrial-muted hover:border-[var(--accent)]/30 hover:text-[var(--accent)]'
                }`}
              >
                <Upload size={16} />
                {isDragging ? 'Drop to upload' : 'Upload or drag documents here'}
              </button>
            )}
          </div>

          {/* Data Imports */}
          <div className="mt-4">
            <DataImportsSection
              projectId={project.id}
              onUploadComplete={() => {
                queryClient.invalidateQueries({
                  queryKey: projectKeys.detail(project.id),
                });
              }}
            />
          </div>
        </div>
      </div>

      <ProjectDocumentPreviewModal
        previewDocument={previewDocument}
        isOpen={previewDocument !== null}
        onClose={() => setPreviewDocument(null)}
      />
    </>
  );
}
