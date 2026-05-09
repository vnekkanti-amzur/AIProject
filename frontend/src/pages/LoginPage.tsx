import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { GoogleLoginButton } from '../components/auth/GoogleLoginButton';
import { login, register } from '../lib/api';

type ApiError = {
  response?: {
    data?: {
      detail?: string | { message?: string };
    };
  };
};

export default function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(email, password);
      }
      navigate('/chat');
    } catch (err) {
      const apiErr = err as ApiError;
      const detail = apiErr.response?.data?.detail;
      const message =
        typeof detail === 'string'
          ? detail
          : detail?.message ?? (err instanceof Error ? err.message : 'Auth failed');
      setError(message);
    }
  };

  return (
    <div className="min-h-full flex items-center justify-center p-6">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-xl border border-slate-200 dark:border-slate-800 p-6 flex flex-col gap-3"
      >
        <h1 className="text-xl font-semibold">
          {mode === 'login' ? 'Sign in' : 'Create account'}
        </h1>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
          className="rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2"
        />
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2"
        />
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        <button
          type="submit"
          className="rounded-md bg-blue-600 hover:bg-blue-700 text-white px-3 py-2"
        >
          {mode === 'login' ? 'Sign in' : 'Register'}
        </button>
        <div className="relative py-1">
          <div className="absolute inset-0 flex items-center" aria-hidden="true">
            <span className="w-full border-t border-slate-200 dark:border-slate-700" />
          </div>
          <span className="relative bg-white dark:bg-slate-950 px-2 text-xs text-slate-500">OR</span>
        </div>
        <GoogleLoginButton />
        <button
          type="button"
          onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
          className="text-sm text-blue-600 hover:underline"
        >
          {mode === 'login' ? 'Need an account? Register' : 'Have an account? Sign in'}
        </button>
      </form>
    </div>
  );
}
