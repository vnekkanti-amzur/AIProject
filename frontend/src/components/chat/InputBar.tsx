import { useState, type FormEvent } from 'react';

interface InputBarProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export function InputBar({ onSend, disabled }: InputBarProps) {
  const [text, setText] = useState('');

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    onSend(value);
    setText('');
  };

  return (
    <form
      onSubmit={submit}
      className="flex gap-2 border-t border-slate-200 dark:border-slate-800 p-3"
    >
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled}
        placeholder="Send a message..."
        className="flex-1 rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2"
      />
      <button
        type="submit"
        disabled={disabled}
        className="rounded-md bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 disabled:opacity-50"
      >
        Send
      </button>
    </form>
  );
}
