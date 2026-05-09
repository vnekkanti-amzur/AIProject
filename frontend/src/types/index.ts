export type ChatRole = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  attachments?: { images?: string[] } | null;
}

export interface Thread {
  id: string;
  title: string;
  updatedAt: string;
}

export interface User {
  email: string;
}

export type AttachmentCategory = 'image' | 'document' | 'code';

export interface UploadedAttachment {
  original_name: string;
  stored_name: string;
  content_type: string | null;
  size_bytes: number;
  category: AttachmentCategory;
}
