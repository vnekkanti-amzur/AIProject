import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { me } from '../../lib/api';

export function GoogleAuthCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const oauthError = useMemo(() => params.get('error'), [params]);

  useEffect(() => {
    let mounted = true;

    const verify = async () => {
      if (oauthError) {
        setError(oauthError);
        return;
      }

      try {
        await me();
        if (mounted) {
          navigate('/chat', { replace: true });
        }
      } catch {
        if (mounted) {
          setError('Authentication failed. Please try again.');
        }
      }
    };

    void verify();

    return () => {
      mounted = false;
    };
  }, [navigate, oauthError]);

  if (error) {
    return (
      <div className="min-h-full grid place-items-center p-6">
        <div className="w-full max-w-md rounded-xl border border-red-300 bg-red-50 p-4 text-red-900">
          <p className="font-semibold">Google sign-in failed</p>
          <p className="mt-1 text-sm">{error}</p>
          <Link to="/login" className="mt-3 inline-block text-sm underline">
            Back to login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-full grid place-items-center p-6">
      <p className="text-sm text-slate-600 dark:text-slate-300">Completing sign-in...</p>
    </div>
  );
}
