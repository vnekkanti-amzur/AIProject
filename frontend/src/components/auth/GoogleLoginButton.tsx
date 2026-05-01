export function GoogleLoginButton() {
  const onClick = () => {
    window.location.href = '/api/auth/google/login';
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-800"
    >
      Continue with Google
    </button>
  );
}
