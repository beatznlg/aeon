"use client";

import { useState, Suspense } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { loginToFlask, registerToFlask, storeFlaskSession } from "@/lib/flask-auth";
import AeonLogo from "@/components/AeonLogo";

const DEMO_EMAIL = "admin@demo.local";
const DEMO_PASSWORD = "demo123";

const ERRORS: Record<string, string> = {
  CredentialsSignin: "Invalid email or password.",
  Configuration: "Server configuration error. Check environment variables.",
  AccessDenied: "Access denied.",
};

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/";
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const finishSignIn = async () => {
    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
      callbackUrl,
    });
    if (result?.error) {
      setError(ERRORS[result.error] || "Sign-in failed. Check your credentials.");
      return false;
    }
    if (!result?.ok) {
      setError("Authentication failed");
      return false;
    }
    // Also get Flask JWT for backend API calls.
    const flask = await loginToFlask(email, password);
    if (flask) storeFlaskSession(flask.token, flask.user);
    router.push(callbackUrl);
    return true;
  };

  const doSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "register") {
        const registered = await registerToFlask(email, password, name);
        if (!registered.ok) {
          setError(
            registered.error === "EMAIL_TAKEN"
              ? "That email is already registered. Try signing in instead."
              : registered.error || "Registration failed. Please try again."
          );
          return;
        }
        storeFlaskSession(registered.token, registered.user);
      }
      await finishSignIn();
    } catch {
      setError("Network error — try again");
    } finally {
      setLoading(false);
    }
  };

  const doDemo = async () => {
    setLoading(true);
    setError("");
    try {
      // Seed demo data, but never block the demo on it: the built-in demo
      // account signs in even when the backend is unreachable. Cap the seed
      // attempt so a wedged backend can't leave the button spinning forever.
      let data: { email?: string; password?: string; error?: string } = {};
      try {
        const res = await fetch("/api/demo/seed", {
          method: "POST",
          signal: AbortSignal.timeout(10000),
        });
        if (res.ok) data = await res.json();
      } catch {
        // Backend unreachable or slow — fall back to the built-in demo login.
      }
      const email = data.email || DEMO_EMAIL;
      const password = data.password || DEMO_PASSWORD;
      // Sign in with demo credentials
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
        callbackUrl,
      });
      if (result?.ok) {
        const flask = await loginToFlask(email, password);
        if (flask) storeFlaskSession(flask.token, flask.user);
        // Demo accounts follow the same setup path as registered companies.
        router.push("/onboarding?demo=1");
      } else {
        setError("Demo sign-in failed");
        setLoading(false);
      }
    } catch {
      setError("Demo setup failed — the backend may not be reachable");
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      {/* Background */}
      <div style={styles.bg} />

      {/* Main card */}
      <div style={styles.card}>
        {/* Logo + Title */}
        <div style={styles.header}>
          <div style={styles.logo}>
            <AeonLogo size={48} />
          </div>
          <h1 style={styles.title}>AEON OS</h1>
          <p style={styles.subtitle}>AI OPERATIVE SYSTEM</p>
        </div>

        {/* Tabs */}
        <div style={styles.tabs}>
          <button
            style={{ ...styles.tab, ...(mode === "login" ? styles.tabActive : {}) }}
            onClick={() => { setMode("login"); setError(""); }}
          >
            Sign In
          </button>
          <button
            style={{ ...styles.tab, ...(mode === "register" ? styles.tabActive : {}) }}
            onClick={() => { setMode("register"); setError(""); }}
          >
            Create Account
          </button>
        </div>

        {/* Error */}
        {error && (
          <div style={styles.error}>
            <span style={{ marginRight: 6 }}>✕</span> {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={doSubmit} style={styles.form}>
          {mode === "register" && (
            <div style={styles.field}>
              <label style={styles.label}>Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                style={styles.input}
              />
            </div>
          )}
          <div style={styles.field}>
            <label style={styles.label}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              style={styles.input}
            />
          </div>
          <div style={styles.field}>
            <label style={styles.label}>Password</label>
            <div style={styles.passwordWrap}>
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={6}
                style={{ ...styles.input, paddingRight: 48 }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={styles.eyeBtn}
                tabIndex={-1}
              >
                {showPassword ? "🙈" : "👁"}
              </button>
            </div>
          </div>
          <button type="submit" style={styles.primaryBtn} disabled={loading}>
            {loading ? (
              <span style={styles.spinner} />
            ) : mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>

        {/* Divider */}
        <div style={styles.divider}>
          <div style={styles.dividerLine} />
          <span style={styles.dividerText}>or</span>
          <div style={styles.dividerLine} />
        </div>

        {/* Demo */}
        <button onClick={doDemo} style={styles.demoBtn} disabled={loading}>
          ▶ Try Demo Account
        </button>
        <p style={styles.demoHint}>
          One-click demo with sample data · No setup required
        </p>

        {/* Footer hint */}
        <p style={styles.footer}>
          {mode === "login"
            ? "Sign in with your AEON OS credentials."
            : "Create a free workspace to get started."}
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div style={{ ...styles.container, background: "#0a0a0f" }}>
        <div style={{ ...styles.card, textAlign: "center" }}>
          <div style={{ ...styles.logo, margin: "0 auto 16px" }}>
            <AeonLogo size={48} />
          </div>
          <p style={{ color: "#666" }}>Loading...</p>
        </div>
      </div>
    }>
      <LoginForm />
    </Suspense>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#0a0a0f",
    position: "relative",
    overflow: "hidden",
    padding: 24,
  },
  bg: {
    position: "absolute",
    inset: 0,
    background:
      "radial-gradient(ellipse at 30% 20%, rgba(99,102,241,0.12) 0%, transparent 50%), " +
      "radial-gradient(ellipse at 70% 80%, rgba(139,92,246,0.08) 0%, transparent 50%)",
    pointerEvents: "none",
  },
  card: {
    position: "relative",
    width: "100%",
    maxWidth: 420,
    background: "rgba(18,18,24,0.95)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: 20,
    padding: "40px 32px 32px",
    backdropFilter: "blur(20px)",
    boxShadow: "0 24px 80px rgba(0,0,0,0.5)",
  },
  header: {
    textAlign: "center" as const,
    marginBottom: 32,
  },
  logo: {
    display: "flex",
    justifyContent: "center",
    marginBottom: 12,
  },
  title: {
    fontSize: 24,
    fontWeight: 700,
    color: "#f1f1f4",
    margin: 0,
    letterSpacing: "-0.02em",
  },
  subtitle: {
    fontSize: 13,
    color: "#888",
    marginTop: 6,
  },
  tabs: {
    display: "flex",
    gap: 4,
    marginBottom: 24,
    background: "rgba(255,255,255,0.04)",
    borderRadius: 10,
    padding: 4,
  },
  tab: {
    flex: 1,
    padding: "10px 0",
    border: "none",
    borderRadius: 8,
    background: "transparent",
    color: "#888",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    transition: "all 0.2s",
  },
  tabActive: {
    background: "rgba(99,102,241,0.15)",
    color: "#a5b4fc",
  },
  error: {
    background: "rgba(239,68,68,0.1)",
    border: "1px solid rgba(239,68,68,0.2)",
    borderRadius: 10,
    padding: "10px 14px",
    marginBottom: 16,
    color: "#f87171",
    fontSize: 13,
  },
  form: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 16,
  },
  field: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 6,
  },
  label: {
    fontSize: 12,
    fontWeight: 600,
    color: "#aaa",
    letterSpacing: "0.03em",
    textTransform: "uppercase" as const,
  },
  input: {
    width: "100%",
    padding: "12px 14px",
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 10,
    color: "#f1f1f4",
    fontSize: 14,
    outline: "none",
    transition: "border-color 0.2s",
    boxSizing: "border-box" as const,
  },
  passwordWrap: {
    position: "relative" as const,
  },
  eyeBtn: {
    position: "absolute" as const,
    right: 10,
    top: "50%",
    transform: "translateY(-50%)",
    background: "none",
    border: "none",
    cursor: "pointer",
    fontSize: 16,
    padding: 4,
  },
  primaryBtn: {
    width: "100%",
    padding: "13px 0",
    background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
    border: "none",
    borderRadius: 10,
    color: "#fff",
    fontSize: 14,
    fontWeight: 700,
    cursor: "pointer",
    transition: "opacity 0.2s, transform 0.1s",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginTop: 4,
  },
  spinner: {
    display: "inline-block",
    width: 16,
    height: 16,
    border: "2px solid rgba(255,255,255,0.3)",
    borderTopColor: "#fff",
    borderRadius: "50%",
    animation: "spin 0.6s linear infinite",
  },
  divider: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    margin: "20px 0",
  },
  dividerLine: {
    flex: 1,
    height: 1,
    background: "rgba(255,255,255,0.06)",
  },
  dividerText: {
    fontSize: 12,
    color: "#666",
    textTransform: "uppercase" as const,
  },
  demoBtn: {
    width: "100%",
    padding: "12px 0",
    background: "rgba(99,102,241,0.08)",
    border: "1px solid rgba(99,102,241,0.2)",
    borderRadius: 10,
    color: "#a5b4fc",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    transition: "all 0.2s",
  },
  demoHint: {
    fontSize: 11,
    color: "#666",
    textAlign: "center" as const,
    marginTop: 8,
  },
  footer: {
    fontSize: 12,
    color: "#555",
    textAlign: "center" as const,
    marginTop: 20,
  },
};
