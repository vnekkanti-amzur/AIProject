import axios from 'axios';
import type { UploadedAttachment } from '../types';

export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
});

export async function login(email: string, password: string) {
  const { data } = await api.post('/auth/login', { email, password });
  return data as { email: string };
}

export async function register(email: string, password: string) {
  const { data } = await api.post('/auth/register', { email, password });
  return data as { email: string };
}

export async function logout() {
  await api.post('/auth/logout');
}

export async function me() {
  const { data } = await api.get('/auth/me');
  return data as { email: string };
}

export interface ThreadDTO {
  id: string;
  title: string;
  updated_at: string;
}

export interface MessageDTO {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  attachments?: { images?: string[] } | null;
}

export async function listThreads(): Promise<ThreadDTO[]> {
  const { data } = await api.get<ThreadDTO[]>('/threads');
  return data;
}

export async function createThread(title?: string): Promise<ThreadDTO> {
  const { data } = await api.post<ThreadDTO>('/threads', { title });
  return data;
}

export async function updateThread(id: string, title: string): Promise<ThreadDTO> {
  const { data } = await api.patch<ThreadDTO>(`/threads/${id}`, { title });
  return data;
}

export async function deleteThread(id: string): Promise<void> {
  await api.delete(`/threads/${id}`);
}

export async function getThreadMessages(id: string): Promise<MessageDTO[]> {
  const { data } = await api.get<MessageDTO[]>(`/threads/${id}/messages`);
  return data;
}

export async function streamChat(
  message: string,
  threadId: string | null,
  attachments: string[],
  onToken: (token: string) => void,
  signal?: AbortSignal,
  onThreadId?: (id: string) => void,
  onUserMessage?: (msg: string) => void,
): Promise<void> {
  console.log('[streamChat] Starting with message:', message, 'threadId:', threadId);
  const res = await fetch('/api/chat', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      thread_id: threadId,
      attachments: attachments.map((storedName) => ({ stored_name: storedName })),
    }),
    signal,
  });
  console.log('[streamChat] Response status:', res.status, 'body exists:', !!res.body);
  if (!res.ok || !res.body) {
    throw new Error(`Chat request failed: ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const flushEvent = (rawEvent: string) => {
    const lines = rawEvent.split('\n');
    const dataLines: string[] = [];
    for (const line of lines) {
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart());
      }
    }
    if (dataLines.length === 0) return;
    const payload = dataLines.join('\n');
    if (payload === '[DONE]') {
      console.log('[flushEvent] Received DONE');
      return;
    }
    if (payload.startsWith('__THREAD__')) {
      const id = payload.slice('__THREAD__'.length).trim();
      console.log('[flushEvent] Thread ID:', id);
      if (id && onThreadId) onThreadId(id);
      return;
    }
    if (payload.startsWith('__USER_MESSAGE__')) {
      const msg = payload.slice('__USER_MESSAGE__'.length).trim();
      console.log('[flushEvent] User message echoed:', msg);
      if (msg && onUserMessage) onUserMessage(msg);
      return;
    }
    console.log('[flushEvent] Token:', payload.substring(0, 50));
    onToken(payload);
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) {
      console.log('[streamChat] Stream done, processing final buffer');
      buffer += decoder.decode();
      if (buffer.trim()) {
        flushEvent(buffer);
      }
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';
    console.log('[streamChat] Processing', events.length, 'events, buffer size:', buffer.length);
    for (const rawEvent of events) {
      flushEvent(rawEvent);
    }
  }
  console.log('[streamChat] Stream completed');
}

export async function uploadAttachments(files: File[]): Promise<UploadedAttachment[]> {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });

  const { data } = await api.post<UploadedAttachment[]>('/chat/uploads', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return data;
}
