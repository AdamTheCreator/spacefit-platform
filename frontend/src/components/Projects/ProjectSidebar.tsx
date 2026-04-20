import { useState, useRef, useCallback, useEffect } from 'react';
import { Plus, Pencil, Check, X, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { useUpdateProject, projectKeys } from '../../hooks/useProjects';
import { useArchiveDocument, useDeleteDocument } from '../../hooks/useDocuments';
import { useUploadStore, type UploadItem } from '../../stores/uploadStore';
import { DocumentCard } from './DocumentCard';
import { ProjectDocumentPreviewModal } from './ProjectDocumentPreviewModal';
import { ImportUploadCard } from '../Imports/ImportUploadCard';
import type { ProjectDetail } from '../../types/project';
import type { DocumentUploadResponse, ParsedDocument } from '../../types/document';
import api from '../../lib/axios';
import { useQueryClient } from '@tanstack/react-query';

interface ProjectSidebarProps {
  project: ProjectDetail;
}

function getEstimatedProcessingProgress(item: UploadItem, now: number) {
  if (item.status !== 'processing') return item.uploadProgress;
  const startedAt = item.processingStartedAt ?? item.addedAt;
  const elapsed = Math.max(now - startedAt, 0);
  const estimated = 8 + (elapsed / 30000) * 84;
  return Math.min(Math.round(estimated), 96);
}

export function ProjectSidebar({ project }: ProjectSidebarProps) {
  const [editingInstructions, setEditingInstructions] = useState(false);
  const [instructions, setInstructions] = useState(
    project.instructions || '',
  );
  const [previewDocument, setPreviewDocument] = useState<ParsedDocument | null>(null);
  const [progressNow, setProgressNow] = useState(() => Date.now());
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
      if (!files) return;

      for (const file of Array.from(files)) {
        const clientId = store().addItem(file, project.id);
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

  return (
    <>
      <div className="h-full overflow-y-auto p-4 space-y-5 scrollbar-thin">
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
          {visibleDocuments.length > 0 ? (
            <div className="space-y-2">
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
              className="w-full py-6 rounded-lg border border-dashed border-[var(--border-subtle)] text-xs text-industrial-muted hover:border-[var(--accent)]/30 hover:text-[var(--accent)] transition-colors flex flex-col items-center gap-2"
            >
              <Upload size={16} />
              Upload documents
            </button>
          )}

          {/* Data Imports */}
          <div className="mt-4">
            <h3 className="text-[11px] font-bold text-industrial-muted uppercase tracking-widest mb-2">
              Data Imports
            </h3>
            <div className="space-y-2">
              {(['costar', 'placer', 'siteusa'] as const).map((source) => (
                <ImportUploadCard
                  key={source}
                  source={source}
                  projectId={project.id}
                  onUploadComplete={() => {
                    queryClient.invalidateQueries({
                      queryKey: projectKeys.detail(project.id),
                    });
                  }}
                />
              ))}
            </div>
          </div>

          {/* Upload progress */}
          {activeUploadItems.length > 0 && (
            <div className="mt-2 space-y-2">
              {activeUploadItems.map((item) => (
                  (() => {
                    const displayProgress =
                      item.status === 'uploading'
                        ? item.uploadProgress
                        : getEstimatedProcessingProgress(item, progressNow);
                    return (
                  <div
                    key={item.clientId}
                    className="p-3 rounded-2xl border border-[var(--accent)]/20 bg-[var(--accent-subtle)]"
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
                        style={{
                          width: `${displayProgress}%`,
                        }}
                      />
                    </div>
                    <p className="text-[11px] text-industrial-muted mt-1.5">
                      {item.status === 'uploading'
                        ? item.statusText
                        : `Extracting property info and spaces… ${displayProgress}%`}
                    </p>
                  </div>
                    );
                  })()
                ))}
            </div>
          )}
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
