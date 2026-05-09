import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import type { ChatMessage } from '../../types';
import { ImageViewer } from './ImageViewer';
import { ImageLoadingSkeleton } from './ImageLoadingSkeleton';

interface MessageListProps {
  messages: ChatMessage[];
}

function isExplicitImageRequest(message: string): boolean {
  const msg = message.trim().toLowerCase();
  if (!msg) return false;

  const strongPatterns = [
    /\b(generate|create|make|draw|paint|design|render|produce)\b\s+(?:an?\s+)?\b(image|picture|photo|illustration|artwork|graphic|portrait|logo|icon)\b/,
    /\b(image|picture|photo|illustration|artwork|graphic|portrait|logo|icon)\b\s+\b(of|for)\b/,
    /\bturn\b.+\binto\b.+\b(image|picture|photo|illustration)\b/,
  ];

  return strongPatterns.some((pattern) => pattern.test(msg));
}

function getMostRecentUserMessage(messages: ChatMessage[], beforeIndex: number): string {
  for (let i = beforeIndex - 1; i >= 0; i -= 1) {
    if (messages[i].role === 'user') {
      return messages[i].content ?? '';
    }
  }
  return '';
}

function extractMarkdownImageUrls(content: string): string[] {
  const pattern = /!\[.*?\]\(((?:https?:\/\/|data:)[^\)]+)\)/g;
  const urls: string[] = [];
  let match;
  while ((match = pattern.exec(content)) !== null) {
    urls.push(match[1]);
  }
  return urls;
}

function extractAttachmentImages(attachments: ChatMessage['attachments']): string[] {
  if (!attachments?.images) return [];
  return attachments.images;
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <div className="flex flex-col gap-4 px-4 py-6">
      {messages.map((m, index) => {
        const markdownImages = extractMarkdownImageUrls(m.content);
        const attachmentImages = extractAttachmentImages(m.attachments);
        
        // Combine images from both sources (avoid duplicates)
        const allImages = [...new Set([...attachmentImages, ...markdownImages])];
        
        // Check if message is incomplete (empty assistant message = generating)
        const isGenerating = m.role === 'assistant' && m.content === '';
        const latestUserMessage = getMostRecentUserMessage(messages, index);
        const isImageGenerating = isGenerating && isExplicitImageRequest(latestUserMessage);

        return (
          <div key={m.id}>
            {/* Message Bubble */}
            <div
              className={
                m.role === 'user'
                  ? 'self-end max-w-2xl rounded-2xl bg-blue-600 text-white px-4 py-3 text-justify ml-auto'
                  : 'self-start max-w-2xl rounded-2xl bg-slate-100 dark:bg-slate-800 px-4 py-3 text-justify'
              }
            >
              {/* Render markdown content, or show loading skeleton if message is empty (generating) */}
              {m.content ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex, rehypeHighlight]}
                >
                  {m.content}
                </ReactMarkdown>
              ) : (
                isImageGenerating ? (
                  <ImageLoadingSkeleton />
                ) : (
                  isGenerating && <p className="text-sm text-slate-600 dark:text-slate-300">Thinking...</p>
                )
              )}
            </div>

            {/* Images rendered outside bubble for proper fullscreen display */}
            {allImages.length > 0 && (
              <div className={`mt-3 space-y-2 ${m.role === 'user' ? 'ml-auto max-w-2xl' : ''}`}>
                {allImages.map((url, idx) => (
                  <ImageViewer key={`${m.id}-${idx}`} src={url} alt="Generated image" />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
