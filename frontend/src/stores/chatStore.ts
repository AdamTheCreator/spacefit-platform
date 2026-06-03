import { create } from 'zustand';
import { useShallow } from 'zustand/react/shallow';
import type { Message, TenantCandidate, WorkflowStep } from '../types/chat';

interface ChatState {
  connectionStatus: 'connected' | 'connecting' | 'disconnected';
  // Current conversation state
  currentSessionId: string | null;
  currentProjectId: string | null;
  messages: Message[];
  workflowSteps: WorkflowStep[];
  isProcessing: boolean;
  activeAgentType: string | null;
  // Tenant suggestions from the latest void/matchmaker turn, awaiting a
  // "save to Contacts" decision (cleared when the user saves or switches chats).
  tenantCandidates: TenantCandidate[];
  tenantCandidatesSource: string | null;

  // Actions
  setCurrentSession: (sessionId: string | null, messages?: Message[]) => void;
  addMessage: (message: Omit<Message, 'id' | 'timestamp'> & Partial<Pick<Message, 'id' | 'timestamp'>>) => void;
  setMessages: (messages: Message[]) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  appendToMessage: (id: string, delta: string) => void;
  setWorkflowSteps: (steps: WorkflowStep[]) => void;
  updateWorkflowStep: (id: string, updates: Partial<WorkflowStep>) => void;
  setIsProcessing: (isProcessing: boolean) => void;
  setActiveAgentType: (agentType: string | null) => void;
  setConnectionStatus: (status: 'connected' | 'connecting' | 'disconnected') => void;
  setCurrentProjectId: (projectId: string | null) => void;
  setTenantCandidates: (tenants: TenantCandidate[], source: string | null) => void;
  clearTenantCandidates: () => void;
  clearChat: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  connectionStatus: 'disconnected',
  currentSessionId: null,
  currentProjectId: null,
  messages: [],
  workflowSteps: [],
  isProcessing: false,
  activeAgentType: null,
  tenantCandidates: [],
  tenantCandidatesSource: null,

  setCurrentSession: (sessionId, messages = []) =>
    set({
      currentSessionId: sessionId,
      messages,
      workflowSteps: [],
      isProcessing: false,
      activeAgentType: null,
      tenantCandidates: [],
      tenantCandidatesSource: null,
    }),

  addMessage: (message) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...message,
          id: message.id ?? crypto.randomUUID(),
          timestamp: message.timestamp ?? new Date(),
        },
      ],
    })),

  setMessages: (messages) => set({ messages }),

  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, ...updates } : msg
      ),
    })),

  appendToMessage: (id, delta) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, content: msg.content + delta } : msg
      ),
    })),

  setWorkflowSteps: (steps) => set({ workflowSteps: steps }),

  updateWorkflowStep: (id, updates) =>
    set((state) => ({
      workflowSteps: state.workflowSteps.map((step) =>
        step.id === id ? { ...step, ...updates } : step
      ),
    })),

  setIsProcessing: (isProcessing) => set({ isProcessing }),

  setActiveAgentType: (agentType) => set({ activeAgentType: agentType }),

  setConnectionStatus: (status) => set({ connectionStatus: status }),

  setCurrentProjectId: (projectId: string | null) =>
    set({ currentProjectId: projectId }),

  setTenantCandidates: (tenants, source) =>
    set({ tenantCandidates: tenants, tenantCandidatesSource: source }),

  clearTenantCandidates: () =>
    set({ tenantCandidates: [], tenantCandidatesSource: null }),

  clearChat: () =>
    set({
      currentSessionId: null,
      currentProjectId: null,
      messages: [],
      workflowSteps: [],
      isProcessing: false,
      activeAgentType: null,
      tenantCandidates: [],
      tenantCandidatesSource: null,
    }),
}));

// Selector hooks for optimized subscriptions (prevents unnecessary re-renders)
export const useChatMessages = () => useChatStore(state => state.messages);
export const useChatWorkflowSteps = () => useChatStore(state => state.workflowSteps);
export const useChatIsProcessing = () => useChatStore(state => state.isProcessing);
export const useChatActiveAgent = () => useChatStore(state => state.activeAgentType);
export const useChatSessionId = () => useChatStore(state => state.currentSessionId);
export const useChatConnectionStatus = () => useChatStore(state => state.connectionStatus);

// Combined selector for components that need multiple values
export const useChatStatus = () => useChatStore(
  useShallow(state => ({
    isProcessing: state.isProcessing,
    activeAgentType: state.activeAgentType,
  }))
);

// Actions-only selector (never causes re-renders on state changes)
export const useChatActions = () => useChatStore(
  useShallow(state => ({
    setCurrentSession: state.setCurrentSession,
    addMessage: state.addMessage,
    setMessages: state.setMessages,
    updateMessage: state.updateMessage,
    appendToMessage: state.appendToMessage,
    setWorkflowSteps: state.setWorkflowSteps,
    updateWorkflowStep: state.updateWorkflowStep,
    setIsProcessing: state.setIsProcessing,
    setActiveAgentType: state.setActiveAgentType,
    setConnectionStatus: state.setConnectionStatus,
    setTenantCandidates: state.setTenantCandidates,
    clearTenantCandidates: state.clearTenantCandidates,
    clearChat: state.clearChat,
  }))
);

// Tenant suggestions awaiting a "save to Contacts" decision.
export const useTenantCandidates = () =>
  useChatStore(
    useShallow(state => ({
      tenantCandidates: state.tenantCandidates,
      tenantCandidatesSource: state.tenantCandidatesSource,
    }))
  );
