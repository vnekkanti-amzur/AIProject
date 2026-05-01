import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import type { ChatMessage } from '../../types';

interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <div className="flex flex-col gap-4 px-4 py-6">
      {messages.map((m) => (
        <div
          key={m.id}
          className={
            m.role === 'user'
              ? 'self-end max-w-2xl rounded-2xl bg-blue-600 text-white px-4 py-3 text-justify'
              : 'self-start max-w-2xl rounded-2xl bg-slate-100 dark:bg-slate-800 px-4 py-3 text-justify'
          }
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex, rehypeHighlight]}
          >
            {m.content}
          </ReactMarkdown>
        </div>
      ))}
    </div>
  );
}
