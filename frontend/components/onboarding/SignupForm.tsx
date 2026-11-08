"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button, cx } from "@/components/ui";
import { apiPost } from "@/lib/client";

type Field = "guardianName" | "guardianEmail" | "protectedName" | "agreed";

function Input({ id, label, hint, error, ...props }: { id: Field; label: string; hint?: string; error?: string } & React.ComponentProps<"input">) {
  return (
    <div>
      <label htmlFor={id} className="block font-semibold">{label}</label>
      {hint && <p id={`${id}-hint`} className="text-[0.85rem] text-muted">{hint}</p>}
      <input
        id={id}
        name={id}
        aria-invalid={!!error || undefined}
        aria-describedby={cx(hint && `${id}-hint`, error && `${id}-err`) || undefined}
        className={cx(
          "mt-2 w-full h-13 rounded-xl border bg-surface-2 px-4 text-[1.05rem] focus:outline-none",
          error ? "border-scam" : "border-line-strong focus:border-accent",
        )}
        {...props}
      />
      {error && <p id={`${id}-err`} className="mt-1.5 text-scam-text font-semibold text-[0.9rem]">{error}</p>}
    </div>
  );
}

export function SignupForm() {
  const router = useRouter();
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setFailed(false);
    const res = await apiPost<{ token?: string; errors?: Partial<Record<Field, string>> }>("/api/signup", {
      guardianName: String(form.get("guardianName") ?? "").trim(),
      guardianEmail: String(form.get("guardianEmail") ?? "").trim(),
      protectedName: String(form.get("protectedName") ?? "").trim(),
      agreed: form.get("agreed") === "yes",
    }).catch(() => null);
    setBusy(false);
    if (res?.ok && res.data?.token) { router.push(`/invite/${res.data.token}`); return; }
    if (res?.data?.errors) {
      setErrors(res.data.errors);
      const first = Object.keys(res.data.errors)[0];
      if (first) document.getElementById(first)?.focus();
      return;
    }
    setFailed(true);
  }

  return (
    <form onSubmit={submit} noValidate className="mt-8 space-y-6">
      <Input id="guardianName" label="Your name" autoComplete="name" error={errors.guardianName} />
      <Input id="guardianEmail" label="Your email" type="email" autoComplete="email" hint="Warnings about their inbox are copied here." error={errors.guardianEmail} />
      <Input id="protectedName" label="Their first name" hint="We use it to greet them." error={errors.protectedName} />
      <div>
        <div className="flex items-start gap-3">
          <input
            id="agreed" name="agreed" type="checkbox" value="yes"
            aria-invalid={!!errors.agreed || undefined}
            aria-describedby={errors.agreed ? "agreed-err" : undefined}
            className="mt-1 w-6 h-6 shrink-0 accent-[var(--color-primary)]"
          />
          <label htmlFor="agreed" className="text-[1.02rem]">They know about this and want the help.</label>
        </div>
        {errors.agreed && <p id="agreed-err" className="mt-1.5 text-scam-text font-semibold text-[0.9rem]">{errors.agreed}</p>}
      </div>
      {failed && <p role="alert" className="text-scam-text">The invite couldn’t be created. Try again in a minute.</p>}
      <Button type="submit" size="lg" disabled={busy} className="w-full sm:w-auto">{busy ? "Creating…" : "Create the invite link"}</Button>
    </form>
  );
}
