import { Frame } from "@/components/onboarding/Frame";
import { ButtonLink } from "@/components/ui";

export default function NotFound() {
  return (
    <Frame>
      <h1 className="text-[2rem] font-extrabold">That page doesn’t exist</h1>
      <p className="mt-3 text-ink-2">If you followed an invite link, check it’s complete, or ask the person who sent it for a new one.</p>
      <ButtonLink href="/" className="mt-7">Go to the home page</ButtonLink>
    </Frame>
  );
}
