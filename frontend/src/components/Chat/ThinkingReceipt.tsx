import type { MessageReceipt } from '../../types/chat';

function Check({ size = 10, color = 'var(--text-muted)' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}

function formatAgentList(agents: string[]): string {
  if (agents.length === 0) return '';
  if (agents.length === 1) return agents[0];
  if (agents.length === 2) return `${agents[0]} & ${agents[1]}`;
  return `${agents.slice(0, -1).join(', ')} & ${agents[agents.length - 1]}`;
}

interface ThinkingReceiptProps {
  receipt: MessageReceipt;
}

export function ThinkingReceipt({ receipt }: ThinkingReceiptProps) {
  return (
    <div style={{
      fontSize: 11,
      color: 'var(--text-muted)',
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      paddingLeft: 40,
      marginBottom: 6,
    }}>
      <Check />
      Worked with {formatAgentList(receipt.agents)} &middot; {receipt.seconds}s
    </div>
  );
}
