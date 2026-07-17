import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * GET /api/onboarding/status
 *
 * Same paranoid secret policy as /api/setup_check — never echoes the actual
 * value, only { present, length|host }. Powers the DeployGuidePanel UI.
 */
function safe(value: string | undefined) {
  if (!value) return { present: false, length: 0 };
  return { present: true, length: value.length };
}
function hostOf(url: string | undefined) {
  if (!url) return null;
  try {
    return new URL(url).host;
  } catch {
    return null;
  }
}

export async function GET() {
  const HF = process.env.HUGGINGFACE_TOKEN;
  const SB_URL = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL;
  const SB_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const SB_SR = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const SPACE = process.env.AEON_HF_SPACE_URL;
  const GH = process.env.GH_TOKEN;

  const hasHf = !!HF;
  const hasSb = !!SB_URL && (!!SB_ANON || !!SB_SR);
  const hasSpace = !!SPACE;

  type Step = {
    id: string;
    title: string;
    state: "ok" | "warn" | "missing" | "external";
    detail: string;
    href?: string;
    cta?: string;
  };

  const steps: Step[] = [
    {
      id: "git-push",
      title: "1. Commit is on origin/main",
      state: "external",
      detail:
        "Push the local commit via Freebuff's changes panel, or `git push origin main` from the dev env.",
      href: "https://github.com/beatznlg/aeon",
      cta: "Open repo",
    },
    {
      id: "vercel-env",
      title: "2. Vercel env vars wired",
      state:
        hasHf && (hasSpace || HF)
          ? "ok"
          : hasHf
          ? "warn"
          : "missing",
      detail: hasHf
        ? `HUGGINGFACE_TOKEN is set (length ${HF!.length}). ${
            hasSpace
              ? "AEON_HF_SPACE_URL is set; closed-loop AEON kernel path active."
              : "AEON_HF_SPACE_URL missing — /api/chat will fall back to HF Inference API directly."
          }`
        : "HUGGINGFACE_TOKEN missing on Vercel — /api/chat will return 401 errors immediately.",
      href: "https://vercel.com/dashboard",
      cta: "Open Vercel",
    },
    {
      id: "hf-space",
      title: "3. HF Space (AEON backend)",
      state: hasSpace ? "ok" : "warn",
      detail: hasSpace
        ? `AEON_HF_SPACE_URL = ${hostOf(SPACE)} (kernel reachable).`
        : "AEON_HF_SPACE_URL not set. Create a Gradio Space (scripts/deploy-hf-space.sh) and paste its URL into Vercel env vars.",
      href: "https://huggingface.co/new-space",
      cta: "Create Space",
    },
    {
      id: "supabase",
      title: "4. Supabase memory table",
      state: hasSb ? "ok" : "warn",
      detail: hasSb
        ? `SUPABASE_URL = ${hostOf(SB_URL)}. Key present (${
            SB_SR ? "service-role" : "anon"
          }). episodes table will be auto-created on first append.`
        : "SUPABASE_URL or its key is missing. Memory browser will be empty. Create free project at supabase.com/dashboard.",
      href: "https://supabase.com/dashboard",
      cta: "Open Supabase",
    },
    {
      id: "ghas",
      title: "5. GitHub Advanced Security",
      state: "external",
      detail:
        "Enable 5 toggles in Settings ▸ Code security and analysis: CodeQL, Dependabot security, Dependabot version, Secret scanning, Push protection. All free for public repos.",
      href:
        "https://github.com/beatznlg/aeon/settings/security_analysis",
      cta: "Open GHAS settings",
    },
  ];

  const notes: string[] = [];
  if (!hasHf) notes.push("HUGGINGFACE_TOKEN missing on Vercel.");
  if (!hasSpace) notes.push("AEON_HF_SPACE_URL missing — closed-loop path off.");
  if (!hasSb) notes.push("Supabase is not wired; episodes will not persist to cloud.");
  if (!GH) notes.push("GH_TOKEN missing — GitHub code search capped at 10/min/IP.");

  return NextResponse.json({
    ok: true,
    ts: Date.now(),
    steps,
    notes,
  });
}
