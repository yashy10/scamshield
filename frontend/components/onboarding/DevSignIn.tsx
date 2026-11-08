/** Local preview only: the Python site shows this when SCAMSHIELD_DEV_SIGNIN=1 on localhost, never on Vercel. */
export function DevSignIn() {
  return (
    <form method="post" action="/signin/dev" className="mt-8 border-t border-dashed border-line-strong pt-6">
      <label htmlFor="dev-email" className="block font-semibold">Local preview: sign in as</label>
      <p className="text-[0.82rem] text-muted">Only on localhost with SCAMSHIELD_DEV_SIGNIN=1. Hidden everywhere else.</p>
      <div className="mt-3 flex gap-2">
        <input
          id="dev-email" name="email" type="email" autoComplete="email" required placeholder="alex@example.com"
          className="min-w-0 flex-1 h-12 rounded-xl border border-line-strong bg-surface-2 px-4 placeholder:text-muted focus:border-accent focus:outline-none"
        />
        <button type="submit" className="h-12 px-5 rounded-xl border border-line-strong bg-surface-3 font-semibold hover:bg-surface-2">Preview</button>
      </div>
    </form>
  );
}
