import { periodPhrase, plural } from "./format";
import type { Period, Role, Status } from "./types";

/** The status panel's words, in the reader's voice ("your inbox" vs "Margaret's inbox"). */
export function statusCopy(o: {
  status: Status; role: Role; name: string; scams: number; careful: number; period: Period;
}): { word: string; headline: string; detail: string } {
  const own = o.role === "self";
  const whose = own ? "Your" : `${o.name}’s`;
  const phrase = periodPhrase(o.period);
  switch (o.status) {
    case "scam":
      return {
        word: plural(o.scams, "scam caught", "scams caught"),
        headline: own ? `We caught ${plural(o.scams, "scam email", "scam emails")}` : `We caught ${plural(o.scams, "scam email", "scam emails")} sent to ${o.name}`,
        detail: own
          ? `${capitalize(phrase)}. ${o.scams === 1 ? "It’s" : "They’re"} labeled “ScamShield” in Gmail. Don’t click ${o.scams === 1 ? "its" : "their"} links or call any numbers in ${o.scams === 1 ? "it" : "them"}.`
          : `${capitalize(phrase)}. ${o.scams === 1 ? "It’s" : "They’re"} labeled in Gmail and ${o.name} was warned. A quick call to check in never hurts.`,
      };
    case "careful":
      return {
        word: "Take care",
        headline: `${plural(o.careful, "email needs", "emails need")} a careful look`,
        detail: own
          ? `No scams ${phrase}, but something looked off. Ask someone you trust before you click.`
          : `No scams ${phrase}, but something looked off. ${o.name} was told to check before clicking.`,
      };
    case "safe":
      return { word: "All clear", headline: `${whose} inbox looks safe`, detail: `No scam emails found ${phrase}.` };
    default:
      return {
        word: "Not checked yet",
        headline: "Waiting for the first check",
        detail: "ScamShield hasn’t looked at this inbox yet. Results show up here after the first check.",
      };
  }
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
