import { useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';
import { projectKeys } from './useProjects';

export interface PromotedSession {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  project_id: string | null;
  project_name: string | null;
}

interface PromoteToExisting {
  sessionId: string;
  projectId: string;
}

interface PromoteToNew {
  sessionId: string;
  newProject: { name: string; propertyAddress?: string };
}

export type PromoteChatArgs = PromoteToExisting | PromoteToNew;

/**
 * Attach a free-form chat to a project — either an existing one or a new one
 * created inline. Backed by `POST /chat/sessions/{id}/promote`. The chat's
 * history stays; only future turns pick up the project's context.
 */
export function usePromoteChat() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (args: PromoteChatArgs): Promise<PromotedSession> => {
      const body =
        'projectId' in args
          ? { project_id: args.projectId }
          : {
              new_project: {
                name: args.newProject.name,
                property_address: args.newProject.propertyAddress || undefined,
              },
            };
      const response = await api.post<PromotedSession>(
        `/chat/sessions/${args.sessionId}/promote`,
        body,
      );
      return response.data;
    },
    onSuccess: () => {
      // The sidebar chat list (scope pill) and the projects list (new/updated
      // session count) both change once a chat is attached.
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
      queryClient.invalidateQueries({ queryKey: projectKeys.all });
    },
  });
}
