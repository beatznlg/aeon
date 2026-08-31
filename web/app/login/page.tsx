"use client";

import { FormEvent, Suspense, useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { loginToFlask, registerToFlask, storeFlaskSession } from "@/lib/flask-auth";
import AeonLogo from "@/components/AeonLogo";
import "../auth.css";

const ERRORS: Record<string, string> = {
  CredentialsSignin: "Invalid email or password.",
  Configuration: "Authentication is not configured correctly.",
  AccessDenied: "Access denied.",
};

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/";
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const finishSignIn = async (loginEmail: string, loginPassword: string) => {
    const result = await signIn("credentials", { email: loginEmail.trim().toLowerCase(), password: loginPassword, redirect: false, callbackUrl });
    if (result?.error) { setError(ERRORS[result.error] || "Sign-in failed. Check your credentials."); return false; }
    if (!result?.ok) { setError("Authentication failed. Please try again."); return false; }
    const flask = await loginToFlask(loginEmail, loginPassword);
    if (flask) storeFlaskSession(flask.token, flask.user);
    router.push(callbackUrl);
    return true;
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true); setError("");
    try {
      if (mode === "register") {
        const result = await registerToFlask(email.trim().toLowerCase(), password, name.trim());
        if (!result.ok) { setError(result.error === "EMAIL_TAKEN" ? "This email is already registered. Switch to Sign in." : result.error || "Registration failed. Please try again."); return; }
        storeFlaskSession(result.token, result.user);
      }
      await finishSignIn(email, password);
    } catch { setError("Unable to reach AEON. Check the connection and try again."); }
    finally { setLoading(false); }
  };

  const demo = async () => {
    setLoading(true); setError("");
    try {
      const response = await fetch("/api/demo/seed", { method: "POST", signal: AbortSignal.timeout(10000), cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.email || !data.password) { setError(data.error || "Demo account is not ready yet."); return; }
      const ok = await finishSignIn(data.email, data.password);
      if (ok) router.push("/onboarding?demo=1");
    } catch { setError("Demo service is unavailable. Please try again in a moment."); }
    finally { setLoading(false); }
  };

  return (
    <main className="auth-shell">
      <div className="auth-glow auth-glow-one" /><div className="auth-glow auth-glow-two" />
      <section className="auth-card" aria-labelledby="auth-title">
        <header className="auth-header">
          <div className="auth-logo"><AeonLogo size={46} /></div>
          <div className="auth-eyebrow">AI OPERATIVE SYSTEM</div>
          <h1 id="auth-title">Welcome to AEON</h1>
          <p>Build, operate and orchestrate intelligent workflows from one workspace.</p>
        </header>
        <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
          <button type="button" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setError(""); }}>Sign in</button>
          <button type="button" role="tab" aria-selected={mode === "register"} className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setError(""); }}>Create account</button>
        </div>
        {error && <div className="auth-alert" role="alert">{error}</div>}
        <form className="auth-form" onSubmit={submit} noValidate>
          {mode === "register" && <label>Name<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" autoComplete="name" required /></label>}
          <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" autoComplete="email" required /></label>
          <label>Password<span className="auth-password"><input type={showPassword ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={6} required /><button type="button" className="auth-show" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? "Hide" : "Show"}</button></span></label>
          <button className="auth-primary" disabled={loading} type="submit">{loading ? "Working…" : mode === "login" ? "Sign in" : "Create account"}</button>
        </form>
        <div className="auth-divider"><span>or</span></div>
        <button className="auth-demo" disabled={loading} onClick={demo} type="button">Try the demo <span>→</span></button>
        <p className="auth-demo-note">A sandbox workspace with sample data. No setup required.</p>
        <footer className="auth-footer">Secure workspace authentication · Oracle-ready deployment</footer>
      </section>
    </main>
  );
}

export default function LoginPage() {
  return <Suspense fallback={<main className="auth-shell"><section className="auth-card auth-loading">Loading AEON…</section></main>}><LoginForm /></Suspense>;
}
