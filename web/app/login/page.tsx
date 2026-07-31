"use client";

import { useState, Suspense, useEffect } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import { loginToFlask, storeFlaskSession } from "@/lib/flask-auth";
import { defaultThemeConfig } from "@/lib/theme-config";

const AEON_URL = process.env.NEXT_PUBLIC_AEON_PYTHON_URL || "http://127.0.0.1:5000";

const DEMO_EMAIL = "admin@demo.local";
const DEMO_PASSWORD = "demo123";

function AuthForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/";
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [demoSeeding, setDemoSeeding] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const finishSignIn = async (userEmail: string, userPassword: string) => {
    const result = await signIn("credentials", {
      email: userEmail,
      password: userPassword,
      redirect: false,
      callbackUrl,
    });

    if (result?.error) {
      setError(result.error);
      setLoading(false);
      return false;
    }

    if (!result?.ok) {
      setError("Authentication failed");
      setLoading(false);
      return false;
    }

    const flask = await loginToFlask(userEmail, userPassword);
    if (flask) {
      storeFlaskSession(flask.token, flask.user);
    }

    router.push(callbackUrl);
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    await finishSignIn(email, password);
    setLoading(false);
  };

  const seedDemo = async () => {
    setDemoSeeding(true);
    setError("");
    try {
      const res = await fetch("/api/demo/seed", { method: "POST" });
      const data = (await res.json()) as {
        ok?: boolean;
        email?: string;
        password?: string;
        error?: string;
      };
      if (!res.ok || !data.ok) {
        setError(data.error || "Demo setup failed");
        setDemoSeeding(false);
        return;
      }
      setEmail(data.email || DEMO_EMAIL);
      setPassword(data.password || DEMO_PASSWORD);
      await finishSignIn(data.email || DEMO_EMAIL, data.password || DEMO_PASSWORD);
    } catch (err: any) {
      setError(err.message || "Demo setup failed");
    } finally {
      setDemoSeeding(false);
    }
  };

  const handleRegister = async () => {
    try {
      const res = await fetch(`${AEON_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          name: name || email.split("@")[0],
        }),
      });
      const data = await res.json();
      if (!data.ok) {
        setError(data.error || "Registration failed");
        return;
      }

      storeFlaskSession(data.token, data.user);

      const signInResult = await signIn("credentials", {
        email,
        password,
        redirect: false,
        callbackUrl,
      });

      if (signInResult?.ok) {
        router.push(callbackUrl);
      } else {
        setError("Account created! Please sign in.");
        setMode("login");
      }
    } catch (err: any) {
      setError(err.message || "Registration failed");
    }
  };

  const productName = defaultThemeConfig.productName;
  const companyName = defaultThemeConfig.companyName;
  const tagline = defaultThemeConfig.tagline;
  const primaryColor = defaultThemeConfig.primaryColor;

  return (
    <div className="login-page">
      <div className="login-bg" aria-hidden="true">
        <div className="login-grid" />
        <div
          className="login-glow"
          style={{
            background: `radial-gradient(circle at 50% 50%, ${primaryColor}22, transparent 60%)`,
          }}
        />
      </div>

      <div className="login-split flex-col md:flex-row">
        {/* Left: value prop */}
        <div className={`login-value ${mounted ? "mounted" : ""} w-full md:w-1/2`}>
          <div className="login-value-content">
            <div className="login-value-logo" style={{ color: primaryColor }}>
              ⟁
            </div>
            <h1 className="login-value-title">{productName}</h1>
            <p className="login-value-tagline">
              {tagline} for {companyName}
            </p>
            <p className="login-value-desc">
              A modular AI operating system that adapts to any enterprise or government sector.
              Launch secure command centers, automate workflows, and govern AI at scale.
            </p>
            <ul className="login-value-features">
              <li>
                <span style={{ color: primaryColor }}>◈</span>
                Multi-vertical AI command centers
              </li>
              <li>
                <span style={{ color: primaryColor }}>◈</span>
                Enterprise security & compliance
              </li>
              <li>
                <span style={{ color: primaryColor }}>◈</span>
                Per-tenant branding & module toggles
              </li>
              <li>
                <span style={{ color: primaryColor }}>◈</span>
                LLM-agnostic, self-improving agents
              </li>
            </ul>
          </div>
        </div>

        {/* Right: auth card */}
        <div className={`login-card-wrapper ${mounted ? "mounted" : ""} w-full md:w-1/2 max-w-md`}>
          <div className="login-card">
            <div className="login-brand">
              <div className="login-logo" style={{ color: primaryColor }}>
                ⟁
              </div>
              <h2>Welcome back</h2>
              <p>Sign in to {productName}</p>
            </div>

            <div className="login-tabs">
              <button
                className={`login-tab ${mode === "login" ? "active" : ""}`}
                onClick={() => {
                  setMode("login");
                  setError("");
                }}
              >
                Sign In
              </button>
              <button
                className={`login-tab ${mode === "register" ? "active" : ""}`}
                onClick={() => {
                  setMode("register");
                  setError("");
                }}
              >
                Create Account
              </button>
            </div>

            <form onSubmit={handleSubmit} className="login-form">
              {error && (
                <div className="login-error" role="alert">
                  <span className="text-aeon-danger font-semibold">✕</span> {error}
                </div>
              )}
              {mode === "register" && (
                <div className="login-field">
                  <label htmlFor="name" className="aeon-label">
                    Name (optional)
                  </label>
                  <input
                    id="name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your name"
                    className="aeon-input"
                  />
                </div>
              )}
              <div className="login-field">
                <label htmlFor="email" className="aeon-label">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="aeon-input"
                />
              </div>
              <div className="login-field">
                <label htmlFor="password" className="aeon-label">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  className="aeon-input"
                />
              </div>
              <button
                type="submit"
                className="aeon-btn-primary w-full justify-center"
                disabled={loading || demoSeeding}
              >
                {loading ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="inline-block w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                    Processing…
                  </span>
                ) : mode === "login" ? (
                  "Sign In"
                ) : (
                  "Create Account"
                )}
              </button>
            </form>

            {mode === "login" && (
              <div className="login-demo">
                <button
                  type="button"
                  className="aeon-btn-secondary w-full justify-center"
                  onClick={seedDemo}
                  disabled={demoSeeding || loading}
                >
                  {demoSeeding ? (
                    <span className="inline-flex items-center gap-2">
                      <span className="inline-block w-3 h-3 rounded-full border-2 border-aeon-primary/30 border-t-aeon-primary animate-spin" />
                      Preparing demo…
                    </span>
                  ) : (
                    <span>▶ Use demo account</span>
                  )}
                </button>
                <p className="login-demo-hint">
                  One-click demo: creates an admin workspace with sample data.
                </p>
              </div>
            )}

            <p className="login-hint">
              {mode === "login"
                ? "Sign in with your AEON OS account credentials."
                : "Create a free workspace to start using AEON OS."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="login-page flex items-center justify-center min-h-screen">
          <div className="skeleton-stat max-w-sm w-full">
            <div
              className="skeleton-shimmer"
              style={{
                height: "1.75rem",
                width: "40%",
                borderRadius: "var(--aeon-radius)",
                margin: "0 auto 1rem",
              }}
            />
            <div
              className="skeleton-shimmer"
              style={{ height: "2.5rem", width: "100%", marginBottom: "0.75rem" }}
            />
            <div
              className="skeleton-shimmer"
              style={{ height: "2.5rem", width: "100%", marginBottom: "0.75rem" }}
            />
            <div
              className="skeleton-shimmer"
              style={{ height: "2.5rem", width: "60%", margin: "0 auto" }}
            />
          </div>
        </div>
      }
    >
      <AuthForm />
    </Suspense>
  );
}
