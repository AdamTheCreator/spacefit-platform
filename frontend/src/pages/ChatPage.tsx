import { useParams } from 'react-router-dom';
import { AppLayout } from '../components/Layout';
import { ChatContainer } from '../components/Chat';

export function ChatPage() {
  const { sessionId } = useParams<{ sessionId?: string }>();

  return (
    <AppLayout>
      <ChatContainer key={sessionId} initialSessionId={sessionId} />
    </AppLayout>
  );
}
