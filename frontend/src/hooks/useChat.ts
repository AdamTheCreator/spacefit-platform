/**
 * useChat Hook - ChatGPT-style conversation management
 *
 * Architecture:
 * - REST API for loading/creating conversations (instant switching)
 * - Single WebSocket connection for all real-time streaming
 * - Clean separation of concerns
 */

import { useCallback, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useChatStore } from '../stores/chatStore';
import { projectKeys } from './useProjects';
import api from '../lib/axios';
import type { Message, TenantCandidate, WorkflowStep } from '../types/chat';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

interface ChatMessage {
  id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  agent_type?: string;
  created_at: string;
}

interface WebSocketMessage {
  type:
    | 'message'
    | 'workflow_init'
    | 'workflow_update'
    | 'session_created'
    | 'title_update'
    | 'error'
    | 'message_start'
    | 'text_delta'
    | 'tool_use_start'
    | 'message_end'
    | 'fact_candidates'
    | 'tenant_candidates';
  data: unknown;
}

// Server datetimes are UTC. Older/naive payloads can arrive without an
// offset suffix — parse those as UTC, never as local (offset-less parsing
// skewed transcripts by hours), and never return an Invalid Date.
function parseServerDate(raw?: string): Date {
  if (!raw) return new Date();
  const hasOffset = /(Z|[+-]\d{2}:?\d{2})$/.test(raw);
  const d = new Date(hasOffset ? raw : `${raw}Z`);
  return isNaN(d.getTime()) ? new Date() : d;
}

// Fetch messages for a session via REST API
async function fetchSessionMessages(sessionId: string): Promise<Message[]> {
  const response = await api.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`);
  return response.data.map((msg) => ({
    id: msg.id,
    role: msg.role,
    content: msg.content,
    agentType: msg.agent_type as Message['agentType'],
    timestamp: parseServerDate(msg.created_at),
  }));
}

export function useChat(sessionId?: string, systemPromptId?: string, projectId?: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const currentSessionRef = useRef<string | null>(null);
  const pendingUserMessagesRef = useRef<Array<{ id: string; content: string }>>([]);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(true);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 3;
  const systemPromptIdRef = useRef<string | undefined>(systemPromptId);
  const projectIdRef = useRef<string | undefined>(projectId);
  const queryClient = useQueryClient();

  // Keep refs in sync with props
  useEffect(() => {
    systemPromptIdRef.current = systemPromptId;
  }, [systemPromptId]);

  useEffect(() => {
    projectIdRef.current = projectId;
  }, [projectId]);

  const {
    messages,
    workflowSteps,
    isProcessing,
    activeAgentType,
    setCurrentSession,
    addMessage,
    updateMessage,
    appendToMessage,
    setWorkflowSteps,
    updateWorkflowStep,
    setIsProcessing,
    setActiveAgentType,
    connectionStatus,
    setConnectionStatus,
    setTenantCandidates,
    removeMessage,
  } = useChatStore();

  const streamingMessageIdsRef = useRef<Set<string>>(new Set());
  // A streamed bubble that ended in tool_use is intermediate: the backend
  // never persists it and a follow-up synthesis bubble is coming. We remove
  // it only when that next bubble actually starts — if the follow-up never
  // arrives (recursion depth cap, provider error), the interim text stays
  // so the turn is never left empty.
  const supersededMsgIdRef = useRef<string | null>(null);

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
        pendingUserMessagesRef.current = [];
        setCurrentSession(null, []);
      } else if (historyMessages) {
        // Existing conversation - load history from cache/API
        pendingUserMessagesRef.current = [];
        setCurrentSession(sessionId, historyMessages);
      }
    } else if (historyMessages && sessionId && sessionId !== 'new') {
      // History loaded for current session
      pendingUserMessagesRef.current = [];
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
      setConnectionStatus('disconnected');
      console.warn('No access token for WebSocket');
      return;
    }

    setConnectionStatus('connecting');

    // Single WebSocket endpoint - session is passed in message payload
    const wsUrl = `${WS_BASE_URL}/api/v1/chat/ws?token=${encodeURIComponent(token)}`;
    console.log('Connecting to chat WebSocket');
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0;
      setConnectionStatus('connected');
      console.log('Chat WebSocket connected');
    };

    ws.onclose = (event) => {
      setIsProcessing(false);
      console.log('Chat WebSocket closed:', event.code, event.reason);

      // Handle auth failure
      if (event.code === 4001) {
        setConnectionStatus('disconnected');
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        // Wipe persisted zustand auth state too — otherwise LoginPage hydrates
        // with isAuthenticated:true and ping-pongs the user back in.
        localStorage.removeItem('auth-storage');
        window.location.href = '/login';
        return;
      }

      if (shouldReconnectRef.current && reconnectAttemptsRef.current < maxReconnectAttempts) {
        reconnectAttemptsRef.current += 1;
        setConnectionStatus('connecting');
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 3000);
      } else {
        setConnectionStatus('disconnected');
      }
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
  }, [setConnectionStatus, setIsProcessing]);

  // Handle incoming WebSocket messages
  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    // A stream killed mid-flight (provider error surfaced as a system bubble
    // or an 'error' event) leaves an empty streaming shell behind. Clear any
    // such shells so error turns don't litter the transcript.
    const sweepEmptyStreamingBubbles = () => {
      for (const m of useChatStore.getState().messages) {
        if (m.isStreaming && !(m.content ?? '').trim()) {
          streamingMessageIdsRef.current.delete(m.id);
          removeMessage(m.id);
        }
      }
    };

    switch (message.type) {
      case 'session_created': {
        const data = message.data as { session_id: string };
        // Update URL and refs for new session
        currentSessionRef.current = data.session_id;
        setCurrentSession(data.session_id, useChatStore.getState().messages);
        const nextUrl = projectIdRef.current
          ? `/projects/${projectIdRef.current}/chat/${data.session_id}`
          : `/chat/${data.session_id}`;
        window.history.replaceState(null, '', nextUrl);
        queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
        if (projectIdRef.current) {
          queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectIdRef.current) });
        }
        break;
      }

      case 'message': {
        const msgData = message.data as {
          id: string;
          role: 'user' | 'agent' | 'system';
          content: string;
          created_at?: string;
          timestamp?: string;
          agent_type?: string;
          is_streaming?: boolean;
          visible?: boolean;
        };

        // Skip intermediate agent messages hidden from UI (e.g., raw tool outputs)
        if (msgData.visible === false) break;

        // System bubbles are how server-side errors surface; any streaming
        // shell still empty at that point is dead.
        if (msgData.role === 'system') sweepEmptyStreamingBubbles();

        // REST history rows carry created_at; live WS Message payloads carry
        // timestamp (the backend model's field name). Reading only created_at
        // produced "Invalid Date" on every live bubble.
        const msgTimestamp = parseServerDate(msgData.created_at ?? msgData.timestamp);

        if (msgData.role === 'user') {
          const pendingIndex = pendingUserMessagesRef.current.findIndex(
            (pendingMessage) => pendingMessage.content === msgData.content
          );

          if (pendingIndex !== -1) {
            const [{ id: pendingId }] = pendingUserMessagesRef.current.splice(pendingIndex, 1);
            updateMessage(pendingId, {
              id: msgData.id,
              content: msgData.content,
              timestamp: msgTimestamp,
              pending: false,
            });
            break;
          }
        }

        addMessage({
          id: msgData.id,
          role: msgData.role,
          content: msgData.content,
          agentType: msgData.agent_type as Message['agentType'],
          timestamp: msgTimestamp,
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
        if (projectIdRef.current) {
          queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectIdRef.current) });
        }
        break;
      }

      case 'message_start': {
        const data = message.data as {
          msg_id: string;
          role: 'agent';
          agent_type?: string;
        };
        // The follow-up round is here — drop the interim tool_use bubble it
        // supersedes (its content was never persisted server-side).
        if (supersededMsgIdRef.current) {
          removeMessage(supersededMsgIdRef.current);
          supersededMsgIdRef.current = null;
        }
        streamingMessageIdsRef.current.add(data.msg_id);
        addMessage({
          id: data.msg_id,
          role: 'agent',
          content: '',
          agentType: data.agent_type as Message['agentType'],
          timestamp: new Date(),
          isStreaming: true,
        });
        break;
      }

      case 'text_delta': {
        const data = message.data as { msg_id: string; delta: string };
        if (streamingMessageIdsRef.current.has(data.msg_id)) {
          appendToMessage(data.msg_id, data.delta);
        }
        break;
      }

      case 'tool_use_start': {
        const data = message.data as {
          msg_id: string;
          tool_id: string;
          tool_name: string;
        };
        // The workflow strip rendering picks up tool_call_start from the
        // existing workflow_update path; this event is informational and
        // lets us optionally render an inline "calling …" chip later.
        // No-op for now; preserved so the WS protocol stays explicit.
        void data;
        break;
      }

      case 'message_end': {
        const data = message.data as {
          msg_id: string;
          content: string;
          stop_reason?: string;
          tool_calls?: unknown[];
          error?: string;
        };
        streamingMessageIdsRef.current.delete(data.msg_id);
        const finalContent = (data.content ?? '').trim();
        if (!finalContent) {
          // Dead stream or a zero-preamble tool round: an empty finalized
          // bubble helps nobody (and used to litter transcripts). Drop it.
          removeMessage(data.msg_id);
          if (supersededMsgIdRef.current === data.msg_id) {
            supersededMsgIdRef.current = null;
          }
        } else {
          updateMessage(data.msg_id, {
            content: data.content,
            isStreaming: false,
          });
        }
        // If there are no follow-on tool calls and no workflow steps,
        // we can drop the processing indicator here. Otherwise the
        // workflow_update path will clear it when all steps complete.
        const tool_calls_present =
          Array.isArray(data.tool_calls) && data.tool_calls.length > 0;
        if (tool_calls_present && finalContent) {
          // Intermediate answer: more tools are about to run and a fresh
          // synthesis bubble will replace this one (mirrors the backend,
          // which only persists tool-free turns). Mark it superseded; the
          // next message_start removes it.
          supersededMsgIdRef.current = data.msg_id;
        }
        if (!tool_calls_present) {
          setTimeout(() => {
            const state = useChatStore.getState();
            if (
              state.workflowSteps.length === 0 ||
              state.workflowSteps.every((s) => s.status === 'completed')
            ) {
              setIsProcessing(false);
            }
          }, 100);
        }
        break;
      }

      case 'fact_candidates': {
        // Surface pending facts via the React Query cache so the
        // Memory sidebar refetches without a manual reload.
        queryClient.invalidateQueries({ queryKey: ['userFacts'] });
        break;
      }

      case 'tenant_candidates': {
        // A void/matchmaker turn surfaced recruitable tenants — stash them so
        // the chat can offer "save these as Contacts".
        const payload = message.data as {
          tenants?: TenantCandidate[];
          source_address?: string | null;
        };
        setTenantCandidates(payload.tenants ?? [], payload.source_address ?? null);
        break;
      }

      case 'error': {
        console.error('Server error:', message.data);
        sweepEmptyStreamingBubbles();
        setIsProcessing(false);
        break;
      }
    }
  }, [addMessage, updateMessage, appendToMessage, removeMessage, setWorkflowSteps, updateWorkflowStep, setIsProcessing, setActiveAgentType, setCurrentSession, setTenantCandidates, queryClient]);

  // Send a message
  const sendMessage = useCallback((content: string) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected');
      return;
    }

    const optimisticMessageId = crypto.randomUUID();
    pendingUserMessagesRef.current.push({ id: optimisticMessageId, content });
    addMessage({
      id: optimisticMessageId,
      role: 'user',
      content,
      pending: true,
    });

    // Clear workflow for new message
    setWorkflowSteps([]);
    setActiveAgentType(null);
    setIsProcessing(true);

    // Build message payload
    const payload: { session_id: string | null; content: string; system_prompt_id?: string; project_id?: string } = {
      session_id: currentSessionRef.current,
      content,
    };

    // Include system_prompt_id and project_id for new sessions (when no current session)
    if (!currentSessionRef.current) {
      if (systemPromptIdRef.current) {
        payload.system_prompt_id = systemPromptIdRef.current;
      }
      if (projectIdRef.current) {
        payload.project_id = projectIdRef.current;
      }
    }

    // Send message with session ID (null = create new session)
    wsRef.current.send(JSON.stringify(payload));
  }, [addMessage, setIsProcessing, setWorkflowSteps, setActiveAgentType]);

  // Cancel an in-flight orchestrator turn. The server task is wrapped in
  // ``asyncio.create_task`` and a ``{"type":"cancel"}`` event raises
  // ``CancelledError`` inside the streaming generator. We also finalize
  // any local streaming bubbles so the UI doesn't show a spinner for
  // text the server has already stopped producing.
  const cancelInflight = useCallback(() => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: 'cancel' }));

    // Finalize any messages that are still flagged as streaming locally.
    const ids = Array.from(streamingMessageIdsRef.current);
    streamingMessageIdsRef.current.clear();
    for (const id of ids) {
      updateMessage(id, { isStreaming: false });
    }
    setIsProcessing(false);
  }, [setIsProcessing, updateMessage]);

  // Connect on mount
  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();
    return () => {
      shouldReconnectRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
      setConnectionStatus('disconnected');
    };
  }, [connect, setConnectionStatus]);

  return {
    // State
    messages,
    workflowSteps,
    isProcessing,
    activeAgentType,
    isConnected: connectionStatus === 'connected',
    isLoading: isLoadingHistory,
    currentSessionId: currentSessionRef.current,

    // Actions
    sendMessage,
    cancelInflight,
  };
}
