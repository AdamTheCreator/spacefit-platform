import { create } from 'zustand';
import type { Message, WorkflowStep } from '../types/chat';

interface ChatState {
  // Current conversation state
  currentSessionId: string | null;
  messages: Message[];
  workflowSteps: WorkflowStep[];
  isProcessing: boolean;
  activeAgentType: string | null;

  // Actions
  setCurrentSession: (sessionId: string | null, messages?: Message[]) => void;
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  setMessages: (messages: Message[]) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  setWorkflowSteps: (steps: WorkflowStep[]) => void;
  updateWorkflowStep: (id: string, updates: Partial<WorkflowStep>) => void;
  setIsProcessing: (isProcessing: boolean) => void;
  setActiveAgentType: (agentType: string | null) => void;
  clearChat: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  currentSessionId: null,
  messages: [],
  workflowSteps: [],
  isProcessing: false,
  activeAgentType: null,

  setCurrentSession: (sessionId, messages = []) =>
    set({
      currentSessionId: sessionId,
      messages,
      workflowSteps: [],
      isProcessing: false,
      activeAgentType: null,
    }),

  addMessage: (message) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...message,
          id: crypto.randomUUID(),
          timestamp: new Date(),
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

  setWorkflowSteps: (steps) => set({ workflowSteps: steps }),

  updateWorkflowStep: (id, updates) =>
    set((state) => ({
      workflowSteps: state.workflowSteps.map((step) =>
        step.id === id ? { ...step, ...updates } : step
      ),
    })),

  setIsProcessing: (isProcessing) => set({ isProcessing }),

  setActiveAgentType: (agentType) => set({ activeAgentType: agentType }),

  clearChat: () =>
    set({
      currentSessionId: null,
      messages: [],
      workflowSteps: [],
      isProcessing: false,
      activeAgentType: null,
    }),
}));
