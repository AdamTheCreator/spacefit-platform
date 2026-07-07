import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';

export interface ChatSession {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  /** Project link — null for free-form chats. */
  project_id: string | null;
  project_name: string | null;
}

export function useChatSessions() {
  const queryClient = useQueryClient();

  const { data: sessions = [], isLoading } = useQuery<ChatSession[]>({
    queryKey: ['chatSessions'],
    queryFn: async () => {
      const response = await api.get<ChatSession[]>('/chat/sessions');
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post<ChatSession>('/chat/sessions');
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      await api.delete(`/chat/sessions/${sessionId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
    },
  });

  return {
    sessions,
    isLoading,
    createSession: async () => {
      const session = await createMutation.mutateAsync();
      return session.id;
    },
    deleteSession: deleteMutation.mutateAsync,
  };
}
