/** Shapes returned by the Python site's /api (see README "Frontend API"). */

export type Status = "scam" | "careful" | "safe" | "waiting";
export type Role = "self" | "guardian";
export type Period = "7" | "30" | "all";

export interface Account {
  email: string;
  name: string;
}

export interface SessionInfo {
  account: Account | null;
  googleSignIn: boolean;
  devSignIn: boolean;
}

export interface PersonSummary {
  id: string;
  name: string;
  email: string;
  role: Role;
  status: Status;
  flagged30d: number;
}

export interface WaitingInvite {
  token: string;
  protectedName: string;
  inviteUrl: string;
}

export interface Counts {
  checked: number;
  scam: number;
  suspicious: number;
  safe: number;
  warningsSent: number;
  markedSafe: number;
}

export interface SeriesPoint {
  start: string; // YYYY-MM-DD
  safe: number;
  suspicious: number;
  scam: number;
}

export interface FlaggedEmail {
  id: string;
  verdict: "scam" | "suspicious";
  receivedAt: string | null;
  checkedAt: string | null;
  senderName: string | null;
  senderDomain: string | null;
  subject: string | null; // null for family contacts
  reasons: string[];
  labeled: boolean;
  warnedAt: string | null;
  warnedTo: string | null;
  markedSafe: { at: string; by: string } | null;
}

export interface ScanState {
  status: "idle" | "running" | "started" | "done" | "error";
  message: string | null;
}

export interface InboxView {
  person: { id: string; name: string; email: string; role: Role; guardianName: string | null; guardianEmail: string | null };
  period: Period;
  periodLabel: string;
  status: Status;
  counts: Counts;
  previous: { checked: number; scam: number; suspicious: number; safe: number } | null;
  lastCheckedAt: string | null;
  series: { unit: "day" | "week"; points: SeriesPoint[] };
  flagged: FlaggedEmail[];
  scan: ScanState;
}

export interface Dashboard {
  account: Account;
  people: PersonSummary[];
  waiting: WaitingInvite[];
  view: InboxView | null;
}

export interface InviteInfo {
  protectedName: string;
  guardianName: string;
  connected: boolean;
  inviteUrl: string;
}
