import { useState, useCallback, useEffect, useRef } from 'react';
import type { Message, WorkflowStep, AgentType } from '../types/chat';
import { DEMO_STEPS, generateDemoId } from '../data/demoConversation';

interface DemoPlaybackState {
  messages: Message[];
  workflowSteps: WorkflowStep[];
  isProcessing: boolean;
  activeAgentType: AgentType | null;
  currentStepIndex: number;
  isComplete: boolean;
}

export function useDemoPlayback() {
  const [state, setState] = useState<DemoPlaybackState>({
    messages: [],
    workflowSteps: [],
    isProcessing: false,
    activeAgentType: null,
    currentStepIndex: -1,
    isComplete: false,
  });

  const timeoutRef = useRef<number | null>(null);
  const messageCountRef = useRef(0);
  const stepCountRef = useRef(0);
  const isAutoAdvancingRef = useRef(false);

  // Clear any pending timeouts
  const clearPendingTimeout = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    isAutoAdvancingRef.current = false;
  }, []);

  // Add a message to the conversation
  const addMessage = useCallback((message: Omit<Message, 'id' | 'timestamp'>) => {
    messageCountRef.current += 1;
    const newMessage: Message = {
      ...message,
      id: generateDemoId('msg', messageCountRef.current),
      timestamp: new Date(),
    };
    setState(prev => ({
      ...prev,
      messages: [...prev.messages, newMessage],
    }));
  }, []);

  // Set workflow steps
  const setWorkflowSteps = useCallback((steps: Partial<WorkflowStep>[]) => {
    const fullSteps: WorkflowStep[] = steps.map((step) => {
      stepCountRef.current += 1;
      return {
        id: generateDemoId('step', stepCountRef.current),
        agentType: step.agentType || 'orchestrator',
        status: step.status || 'pending',
        description: step.description || '',
      } as WorkflowStep;
    });
    setState(prev => ({
      ...prev,
      workflowSteps: fullSteps,
    }));
  }, []);

  // Update a workflow step status
  const updateWorkflowStep = useCallback((agentType: AgentType, status: WorkflowStep['status']) => {
    setState(prev => ({
      ...prev,
      workflowSteps: prev.workflowSteps.map(step =>
        step.agentType === agentType ? { ...step, status } : step
      ),
    }));
  }, []);

  // Process a single step immediately (no delays)
  const processStepImmediate = useCallback((stepIndex: number): void => {
    if (stepIndex >= DEMO_STEPS.length) {
      setState(prev => ({
        ...prev,
        isComplete: true,
        isProcessing: false,
        activeAgentType: null,
      }));
      return;
    }

    const step = DEMO_STEPS[stepIndex];

    setState(prev => ({
      ...prev,
      currentStepIndex: stepIndex,
    }));

    switch (step.type) {
      case 'user_message':
      case 'user_followup':
        addMessage({
          role: 'user',
          content: step.content || '',
        });
        break;

      case 'orchestrator':
      case 'synthesis':
        setState(prev => ({ ...prev, isProcessing: true, activeAgentType: 'orchestrator' }));
        addMessage({
          role: 'agent',
          agentType: 'orchestrator',
          content: step.content || '',
        });
        if (!step.autoAdvance) {
          setState(prev => ({ ...prev, isProcessing: false, activeAgentType: null }));
        }
        break;

      case 'workflow_init':
        if (step.workflowSteps) {
          setWorkflowSteps(step.workflowSteps);
        }
        setState(prev => ({ ...prev, isProcessing: true }));
        break;

      case 'agents_start':
        // Set all workflow steps to running simultaneously
        setState(prev => ({
          ...prev,
          isProcessing: true,
          workflowSteps: prev.workflowSteps.map(s => ({ ...s, status: 'running' as const })),
        }));
        break;

      case 'agent_working':
        if (step.agentType) {
          setState(prev => ({ ...prev, activeAgentType: step.agentType || null }));
          updateWorkflowStep(step.agentType, 'running');
        }
        break;

      case 'agent_result':
      case 'notification':
        if (step.agentType) {
          updateWorkflowStep(step.agentType, 'completed');
          addMessage({
            role: 'agent',
            agentType: step.agentType,
            content: step.content || '',
          });
        }
        break;
    }
  }, [addMessage, setWorkflowSteps, updateWorkflowStep]);

  // Process a step with optional delay for auto-advance
  const processStep = useCallback((stepIndex: number) => {
    clearPendingTimeout();

    if (stepIndex >= DEMO_STEPS.length) {
      setState(prev => ({
        ...prev,
        isComplete: true,
        isProcessing: false,
        activeAgentType: null,
      }));
      return;
    }

    const step = DEMO_STEPS[stepIndex];

    // Process the step immediately
    processStepImmediate(stepIndex);

    // If this step auto-advances, set up the timeout
    if (step.autoAdvance && step.delayMs) {
      isAutoAdvancingRef.current = true;
      timeoutRef.current = window.setTimeout(() => {
        isAutoAdvancingRef.current = false;
        processStep(stepIndex + 1);
      }, step.delayMs);
    }
  }, [clearPendingTimeout, processStepImmediate]);

  // Handle advancing to the next step (Enter key pressed)
  const advanceStep = useCallback(() => {
    // If demo is complete, restart
    if (state.isComplete) {
      clearPendingTimeout();
      messageCountRef.current = 0;
      stepCountRef.current = 0;
      setState({
        messages: [],
        workflowSteps: [],
        isProcessing: false,
        activeAgentType: null,
        currentStepIndex: -1,
        isComplete: false,
      });
      return;
    }

    // Clear any pending auto-advance timeout
    clearPendingTimeout();

    // Move to the next step
    const nextIndex = state.currentStepIndex + 1;

    if (nextIndex >= DEMO_STEPS.length) {
      setState(prev => ({
        ...prev,
        isComplete: true,
        isProcessing: false,
        activeAgentType: null,
      }));
      return;
    }

    processStep(nextIndex);
  }, [state.isComplete, state.currentStepIndex, processStep, clearPendingTimeout]);

  // Handle Enter key press
  const handleKeyPress = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      advanceStep();
    }
  }, [advanceStep]);

  // Set up keyboard listener
  useEffect(() => {
    window.addEventListener('keydown', handleKeyPress);
    return () => {
      window.removeEventListener('keydown', handleKeyPress);
      clearPendingTimeout();
    };
  }, [handleKeyPress, clearPendingTimeout]);

  // Reset the demo
  const resetDemo = useCallback(() => {
    clearPendingTimeout();
    messageCountRef.current = 0;
    stepCountRef.current = 0;
    setState({
      messages: [],
      workflowSteps: [],
      isProcessing: false,
      activeAgentType: null,
      currentStepIndex: -1,
      isComplete: false,
    });
  }, [clearPendingTimeout]);

  // Check if we're currently auto-advancing
  const isAutoAdvancing = isAutoAdvancingRef.current;

  return {
    messages: state.messages,
    workflowSteps: state.workflowSteps,
    isProcessing: state.isProcessing,
    activeAgentType: state.activeAgentType,
    isComplete: state.isComplete,
    isWaitingForInput: !isAutoAdvancing && !state.isComplete,
    currentStep: state.currentStepIndex + 1,
    totalSteps: DEMO_STEPS.length,
    advanceStep,
    resetDemo,
  };
}
