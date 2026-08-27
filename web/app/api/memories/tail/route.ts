import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(_req: NextRequest) {
  // Memory history is served by the AEON Flask backend (aeon_memories /
  // /memories endpoints). Supabase is no longer part of the stack, so this
  // legacy route returns an empty result instead of importing the removed
  // @supabase/supabase-js package.
  return NextResponse.json({ ok: true, rows: [] });
}