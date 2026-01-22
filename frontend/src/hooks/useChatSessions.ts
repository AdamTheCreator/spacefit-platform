import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/axios';

interface ChatSession {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
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
