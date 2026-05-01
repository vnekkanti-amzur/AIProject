export type ChatRole = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
}

export interface Thread {
  id: string;
  title: string;
  updatedAt: string;
}

export interface User {
  email: string;
}
