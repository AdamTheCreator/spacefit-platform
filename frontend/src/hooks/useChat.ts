/**
 * useChat Hook - ChatGPT-style conversation management
 *
 * Architecture:
 * - REST API for loading/creating conversations (instant switching)
 * - Single WebSocket connection for all real-time streaming
 * - Clean separation of concerns
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useChatStore } from '../stores/chatStore';
import api from '../lib/axios';
import type { Message, WorkflowStep } from '../types/chat';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

interface ChatMessage {
  id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  agent_type?: string;
  created_at: string;
}

interface WebSocketMessage {
  type: 'message' | 'workflow_init' | 'workflow_update' | 'session_created' | 'title_update' | 'error';
  data: unknown;
}

// Fetch messages for a session via REST API
async function fetchSessionMessages(sessionId: string): Promise<Message[]> {
  const response = await api.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`);
  return response.data.map((msg) => ({
    id: msg.id,
    role: msg.role,
    content: msg.content,
    agentType: msg.agent_type as Message['agentType'],
    timestamp: new Date(msg.created_at),
  }));
}

export function useChat(sessionId?: string, systemPromptId?: string) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const currentSessionRef = useRef<string | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const systemPromptIdRef = useRef<string | undefined>(systemPromptId);
  const queryClient = useQueryClient();

  // Keep ref in sync with prop
  useEffect(() => {
    systemPromptIdRef.current = systemPromptId;
  }, [systemPromptId]);

  const {
    messages,
    workflowSteps,
    isProcessing,
    activeAgentType,
    setCurrentSession,
    addMessage,
    setWorkflowSteps,
    updateWorkflowStep,
    setIsProcessing,
    setActiveAgentType,
  } = useChatStore();

  // Fetch conversation history when sessionId changes (REST API - instant!)
  const { data: historyMessages, isLoading: isLoadingHistory } = useQuery({
    queryKey: ['chatMessages', sessionId],
    queryFn: () => fetchSessionMessages(sessionId!),
    enabled: !!sessionId && sessionId !== 'new',
    staleTime: 30000, // Cache for 30 seconds
  });

  // Update store when session changes or history loads
  useEffect(() => {
    if (sessionId !== currentSessionRef.current) {
      currentSessionRef.current = sessionId || null;

      if (!sessionId || sessionId === 'new') {
        // New conversation - clear messages
        setCurrentSession(null, []);
      } else if (historyMessages) {
        // Existing conversation - load history from cache/API
        setCurrentSession(sessionId, historyMessages);
      }
    } else if (historyMessages && sessionId && sessionId !== 'new') {
      // History loaded for current session
      setCurrentSession(sessionId, historyMessages);
    }
  }, [sessionId, historyMessages, setCurrentSession]);

  // Connect to WebSocket (single connection, not per-session)
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    const token = localStorage.getItem('access_token');
    if (!token) {
      console.warn('No access token for WebSocket');
      return;
    }

    // Single WebSocket endpoint - session is passed in message payload
    const wsUrl = `${WS_BASE_URL}/api/v1/chat/ws?token=${encodeURIComponent(token)}`;
    console.log('Connecting to chat WebSocket');
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
      console.log('Chat WebSocket connected');
    };

    ws.onclose = (event) => {
      setIsConnected(false);
      setIsProcessing(false);
      console.log('Chat WebSocket closed:', event.code, event.reason);

      // Handle auth failure
      if (event.code === 4001) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return;
      }

      // Reconnect after 3 seconds (unless auth failed)
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        handleWebSocketMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    wsRef.current = ws;
  }, []);

  // Handle incoming WebSocket messages
  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    switch (message.type) {
      case 'session_created': {
        const data = message.data as { session_id: string };
        // Update URL and refs for new session
        currentSessionRef.current = data.session_id;
        setCurrentSession(data.session_id, useChatStore.getState().messages);
        window.history.replaceState(null, '', `/chat/${data.session_id}`);
        queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
        break;
      }

      case 'message': {
        const msgData = message.data as {
          id: string;
          role: 'user' | 'agent' | 'system';
          content: string;
          agent_type?: string;
          is_streaming?: boolean;
        };

        addMessage({
          role: msgData.role,
          content: msgData.content,
          agentType: msgData.agent_type as Message['agentType'],
          isStreaming: msgData.is_streaming,
        });

        // Reset processing when orchestrator sends final message
        if (!msgData.is_streaming && msgData.role === 'agent' && msgData.agent_type === 'orchestrator') {
          setTimeout(() => {
            const state = useChatStore.getState();
            if (state.workflowSteps.length === 0 || state.workflowSteps.every(s => s.status === 'completed')) {
              setIsProcessing(false);
            }
          }, 100);
        }
        break;
      }

      case 'workflow_init': {
        const rawSteps = message.data as Array<{
          id: string;
          agent_type: string;
          status: string;
          description: string;
        }>;
        const steps: WorkflowStep[] = rawSteps.map((step) => ({
          id: step.id,
          agentType: step.agent_type as WorkflowStep['agentType'],
          status: (step.status || 'pending') as WorkflowStep['status'],
          description: step.description,
        }));
        setWorkflowSteps(steps);
        const runningStep = steps.find((s) => s.status === 'running');
        if (runningStep) {
          setActiveAgentType(runningStep.agentType);
        }
        break;
      }

      case 'workflow_update': {
        const update = message.data as { step_id: string; status: string; agent_type?: string };
        updateWorkflowStep(update.step_id, {
          status: update.status as WorkflowStep['status'],
        });

        if (update.status === 'running' && update.agent_type) {
          setActiveAgentType(update.agent_type as WorkflowStep['agentType']);
        }

        if (update.status === 'completed') {
          const steps = useChatStore.getState().workflowSteps;
          const allComplete = steps.every(
            (s) => s.id === update.step_id || s.status === 'completed'
          );
          if (allComplete) {
            setActiveAgentType(null);
            setIsProcessing(false);
          }
        }
        break;
      }

      case 'title_update': {
        queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
        break;
      }

      case 'error': {
        console.error('Server error:', message.data);
        setIsProcessing(false);
        break;
      }
    }
  }, [addMessage, setWorkflowSteps, updateWorkflowStep, setIsProcessing, setActiveAgentType, setCurrentSession, queryClient]);

  // Send a message
  const sendMessage = useCallback((content: string) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected');
      return;
    }

    // Clear workflow for new message
    setWorkflowSteps([]);
    setActiveAgentType(null);
    setIsProcessing(true);

    // Build message payload
    const payload: { session_id: string | null; content: string; system_prompt_id?: string } = {
      session_id: currentSessionRef.current,
      content,
    };

    // Include system_prompt_id for new sessions (when no current session)
    if (!currentSessionRef.current && systemPromptIdRef.current) {
      payload.system_prompt_id = systemPromptIdRef.current;
    }

    // Send message with session ID (null = create new session)
    wsRef.current.send(JSON.stringify(payload));
  }, [setIsProcessing, setWorkflowSteps, setActiveAgentType]);

  // Connect on mount
  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    // State
    messages,
    workflowSteps,
    isProcessing,
    activeAgentType,
    isConnected,
    isLoading: isLoadingHistory,
    currentSessionId: currentSessionRef.current,

    // Actions
    sendMessage,
  };
}
