import { createClient } from "@supabase/supabase-js";

const publicUrl = () => process.env.NEXT_PUBLIC_SUPABASE_URL;
const publicKey = () => process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

/**
 * Browser-safe client. It only accepts NEXT_PUBLIC_* values and therefore
 * respects Supabase Row Level Security without exposing the service-role key.
 */
export function getSupabaseBrowserClient() {
  const url = publicUrl();
  const key = publicKey();
  if (!url || !key) return null;
  return createClient(url, key);
}

/**
 * Server-only client for trusted Next.js route handlers and auth callbacks.
 * SUPABASE_SERVICE_ROLE_KEY is never read by the browser client or returned
 * from any API response.
 */
export function getSupabaseServerClient() {
  const url = process.env.SUPABASE_URL || publicUrl();
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY || publicKey();
  if (!url || !key) return null;
  return createClient(url, key, { auth: { persistSession: false } });
}
