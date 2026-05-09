import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MessageList } from '../components/chat/MessageList';
import { InputBar } from '../components/chat/InputBar';
import { ThreadSidebar } from '../components/chat/ThreadSidebar';
import {
  streamChat,
  uploadAttachments,
  me,
  logout,
  listThreads,
  createThread,
  updateThread,
  deleteThread,
  getThreadMessages,
  type ThreadDTO,
  type MessageDTO,
} from '../lib/api';
import type { ChatMessage, Thread } from '../types';

const toThread = (t: ThreadDTO): Thread => ({
  id: t.id,
  title: t.title,
  updatedAt: t.updated_at,
});

const toMessage = (m: MessageDTO): ChatMessage => ({
  id: m.id,
  role: m.role,
  content: m.content,
  attachments: m.attachments,
});

export default function ChatPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Check if user is authenticated on mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const u = await me();
        setUserEmail(u.email);
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
    queryFn: async () => (await listThreads()).map(toThread),
  });

  const { data: messages = [] } = useQuery<ChatMessage[]>({
    queryKey: activeKey,
    queryFn: async () => {
      if (!activeThreadId) return [];
      const msgs = await getThreadMessages(activeThreadId);
      return msgs.map(toMessage);
    },
  });

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;
    element.scrollTop = element.scrollHeight;
  }, [messages]);

  const sendMutation = useMutation({
    mutationFn: async (vars: {
      text: string;
      assistantId: string;
      controller: AbortController;
      threadId: string | null;
      attachments: string[];
    }) => {
      let resolvedThreadId = vars.threadId;
      console.log('[handleSend] Calling streamChat with text:', vars.text);
      try {
        await streamChat(
          vars.text,
          vars.threadId,
          vars.attachments,
          (token) => {
            console.log('[onToken callback] Received token:', token.substring(0, 50));
            const key = ['chat', 'messages', resolvedThreadId ?? 'draft'] as const;
            queryClient.setQueryData<ChatMessage[]>(key, (prev = []) =>
              prev.map((m) =>
                m.id === vars.assistantId ? { ...m, content: m.content + token } : m,
              ),
            );
          },
          vars.controller.signal,
          (newId) => {
            console.log('[onThreadId callback] New thread ID:', newId);
            if (resolvedThreadId === newId) return;
            // Migrate the draft cache onto the real thread key when the
            // backend tells us the id of a freshly-created thread.
          if (resolvedThreadId === null) {
            const draft = queryClient.getQueryData<ChatMessage[]>([
              'chat',
              'messages',
              'draft',
            ]);
            if (draft) {
              queryClient.setQueryData(['chat', 'messages', newId], draft);
              queryClient.removeQueries({ queryKey: ['chat', 'messages', 'draft'] });
            }
            setActiveThreadId(newId);
          }
          resolvedThreadId = newId;
        },
      );
      console.log('[handleSend] streamChat completed successfully');
      return resolvedThreadId;
    } catch (error) {
      console.error('[handleSend] streamChat error:', error);
      throw error;
    }
    },
    onSuccess: (threadId) => {
      // Invalidate both the thread list and the messages for this thread
      queryClient.invalidateQueries({ queryKey: ['chat', 'threads'] });
      queryClient.invalidateQueries({ queryKey: ['chat', 'messages', threadId ?? activeThreadId ?? 'draft'] });
    },
  });

  const handleNew = async () => {
    const t = await createThread();
    queryClient.setQueryData<Thread[]>(['chat', 'threads'], (prev = []) => [
      toThread(t),
      ...prev.filter((p) => p.id !== t.id),
    ]);
    queryClient.setQueryData<ChatMessage[]>(['chat', 'messages', t.id], []);
    setActiveThreadId(t.id);
  };

  const handleSend = async (text: string, files: File[]) => {
    const uploaded = files.length > 0 ? await uploadAttachments(files) : [];
    const attachmentNames = uploaded.map((item) => item.stored_name);
    const controller = new AbortController();
    const note = files.length > 0 ? `\n\n[Attached: ${files.map((f) => f.name).join(', ')}]` : '';
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: `${text}${note}`.trim(),
      attachments: null,
    };
    const assistantId = crypto.randomUUID();
    queryClient.setQueryData<ChatMessage[]>(activeKey, (prev = []) => [
      ...prev,
      userMsg,
      { id: assistantId, role: 'assistant', content: '', attachments: null },
    ]);
    sendMutation.mutate({
      text,
      assistantId,
      controller,
      threadId: activeThreadId,
      attachments: attachmentNames,
    });
  };

  const handleRename = async (id: string, title: string) => {
    const updated = await updateThread(id, title);
    queryClient.setQueryData<Thread[]>(['chat', 'threads'], (prev = []) =>
      prev.map((t) => (t.id === id ? toThread(updated) : t)),
    );
  };

  const handleDelete = async (id: string) => {
    await deleteThread(id);
    queryClient.setQueryData<Thread[]>(['chat', 'threads'], (prev = []) =>
      prev.filter((t) => t.id !== id),
    );
    if (activeThreadId === id) setActiveThreadId(null);
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // Ignore network errors — clear client state regardless.
    }
    queryClient.clear();
    navigate('/login', { replace: true });
  };

  return (
    <div className="flex h-full">
      <ThreadSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelect={setActiveThreadId}
        onNew={handleNew}
        onRename={handleRename}
        onDelete={handleDelete}
      />
      <main className="flex-1 flex flex-col">
        <header className="flex items-center justify-end gap-4 border-b border-gray-200 dark:border-gray-700 px-4 py-2">
          {userEmail && (
            <span className="text-sm text-gray-600 dark:text-gray-300">{userEmail}</span>
          )}
          <button
            type="button"
            onClick={handleLogout}
            className="text-sm font-medium text-gray-700 hover:text-gray-900 dark:text-gray-200 dark:hover:text-white underline-offset-4 hover:underline"
          >
            Logout
          </button>
        </header>
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <MessageList messages={messages} />
        </div>
        <InputBar onSend={handleSend} disabled={sendMutation.isPending} />
      </main>
    </div>
  );
}
