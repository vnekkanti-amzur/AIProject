import axios from 'axios';

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

export async function streamChat(
  message: string,
  threadId: string | null,
  onToken: (token: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id: threadId }),
    signal,
  });
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
    if (payload === '[DONE]') return;
    onToken(payload);
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) {
      buffer += decoder.decode();
      if (buffer.trim()) {
        flushEvent(buffer);
      }
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';
    for (const rawEvent of events) {
      flushEvent(rawEvent);
    }
  }
}
