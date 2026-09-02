/**
 * Supabase compatibility stub.
 *
 * AEON OS is deployed with the bundled PostgreSQL database (Cloud SQL on
 * Google Cloud); Supabase is no longer part of the stack. These helpers
 * intentionally return null so every caller falls back to the Flask backend,
 * the local user store, or demo data exactly as it already does when Supabase
 * is not configured. Keeping the module (without the @supabase/supabase-js
 * dependency) avoids touching the ~13 call sites that guard on a null client.
 *
 * The return type is intentionally loose ("unknown client shape") so those
 * call sites keep typechecking without importing the removed package. At
 * runtime this is always null.
 */

export function getSupabaseBrowserClient(): any {
  return null;
}

export function getSupabaseServerClient(): any {
  return null;
}
