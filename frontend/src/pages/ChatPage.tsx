import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MessageList } from '../components/chat/MessageList';
import { InputBar } from '../components/chat/InputBar';
import { ThreadSidebar } from '../components/chat/ThreadSidebar';
import { streamChat, me } from '../lib/api';
import type { ChatMessage, Thread } from '../types';

export default function ChatPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Check if user is authenticated on mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        await me();
      } catch {
        // Not authenticated, redirect to login
        navigate('/login', { replace: true });
      }
    };
    checkAuth();
  }, [navigate]);

  const activeKey = useMemo(
    () => ['chat', 'messages', activeThreadId ?? 'draft'] as const,
    [activeThreadId],
  );

  const { data: threads = [] } = useQuery<Thread[]>({
    queryKey: ['chat', 'threads'],
    queryFn: async () => [],
    staleTime: Infinity,
    gcTime: Infinity,
  });

  const { data: messages = [] } = useQuery<ChatMessage[]>({
    queryKey: activeKey,
    queryFn: async () => [],
    staleTime: Infinity,
    gcTime: Infinity,
    enabled: true,
  });

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;
    element.scrollTop = element.scrollHeight;
  }, [messages]);

  const sendMutation = useMutation({
    mutationFn: async (vars: { text: string; assistantId: string; controller: AbortController }) => {
      await streamChat(
        vars.text,
        activeThreadId,
        (token) => {
          queryClient.setQueryData<ChatMessage[]>(activeKey, (prev = []) =>
            prev.map((m) =>
              m.id === vars.assistantId ? { ...m, content: m.content + token } : m,
            ),
          );
        },
        vars.controller.signal,
      );
    },
  });

  const handleNew = () => {
    const id = crypto.randomUUID();
    queryClient.setQueryData<Thread[]>(['chat', 'threads'], (prev = []) => [
      { id, title: 'New chat', updatedAt: new Date().toISOString() },
      ...prev,
    ]);
    setActiveThreadId(id);
    queryClient.setQueryData<ChatMessage[]>(['chat', 'messages', id], []);
  };

  const handleSend = async (text: string) => {
    const controller = new AbortController();
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: text };
    const assistantId = crypto.randomUUID();
    queryClient.setQueryData<ChatMessage[]>(activeKey, (prev = []) => [
      ...prev,
      userMsg,
      { id: assistantId, role: 'assistant', content: '' },
    ]);
    sendMutation.mutate({ text, assistantId, controller });
  };

  return (
    <div className="flex h-full">
      <ThreadSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelect={setActiveThreadId}
        onNew={handleNew}
      />
      <main className="flex-1 flex flex-col">
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <MessageList messages={messages} />
        </div>
        <InputBar onSend={handleSend} disabled={sendMutation.isPending} />
      </main>
    </div>
  );
}
