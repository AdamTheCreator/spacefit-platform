import { useParams, useSearchParams } from 'react-router-dom';
import { AppLayout } from '../components/Layout';
import { ChatContainer } from '../components/Chat';

export function ChatPage() {
  const { sessionId } = useParams<{ sessionId?: string }>();
  const [searchParams] = useSearchParams();
  const chatContext = searchParams.get('context') || undefined;

  return (
    <AppLayout>
      <ChatContainer key={sessionId} initialSessionId={sessionId} chatContext={chatContext} />
    </AppLayout>
  );
}
