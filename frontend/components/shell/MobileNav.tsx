"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Menu, X } from "lucide-react";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

export function MobileNav({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const search = useSearchParams();
  useEffect(() => setOpen(false), [pathname, search]);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger className="lg:hidden grid place-items-center w-10 h-10 -ml-1 rounded-lg text-ink-2 hover:bg-surface-2" aria-label="Open menu">
        <Menu aria-hidden className="w-5 h-5" />
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="sheet-overlay fixed inset-0 z-40 bg-black/60" />
        <Dialog.Content className="fixed inset-y-0 left-0 z-50 w-[19rem] max-w-[88vw] bg-raised border-r border-line overflow-y-auto focus:outline-none">
          <Dialog.Title className="sr-only">Menu</Dialog.Title>
          <Dialog.Close className="absolute right-3 top-4 grid place-items-center w-10 h-10 rounded-lg text-muted hover:bg-surface-2" aria-label="Close menu">
            <X aria-hidden className="w-5 h-5" />
          </Dialog.Close>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
