"use client";

import { useState, Suspense } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  loginToFlask,
  registerToFlask,
  storeFlaskSession,
} from "@/lib/flask-auth";

const AEON_URL = process.env.NEXT_PUBLIC_AEON_PYTHON_URL || "http://127.0.0.1:5000";

function AuthForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/chat";
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    // 1. Authenticate via NextAuth
    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
      callbackUrl,
    });

    if (result?.error) {
      // If login fails and we're in register mode, try registering
      if (mode === "register") {
        // Do Flask registration below, then re-auth via NextAuth
        await handleRegister();
        setLoading(false);
        return;
      }
      setError(result.error);
      setLoading(false);
      return;
    }

    if (!result?.ok) {
      setError("Authentication failed");
      setLoading(false);
      return;
    }

    // 2. Log into Flask to get a JWT for backend API calls
    const flask = await loginToFlask(email, password);
    if (flask) {
      storeFlaskSession(flask.token, flask.user);
    }

    setLoading(false);
    router.push(callbackUrl);
  };

  const handleRegister = async () => {
    try {
      // Register via Flask
      const res = await fetch(`${AEON_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name: name || email.split("@")[0] }),
      });
      const data = await res.json();
      if (!data.ok) {
        setError(data.error || "Registration failed");
        return;
      }

      // Store Flask token
      storeFlaskSession(data.token, data.user);

      // Also sign in via NextAuth with the same credentials
      const signInResult = await signIn("credentials", {
        email,
        password,
        redirect: false,
        callbackUrl,
      });

      if (signInResult?.ok) {
        router.push(callbackUrl);
      } else {
        // Flask worked but NextAuth didn't — redirect to login
        setError("Account created! Please sign in.");
        setMode("login");
      }
    } catch (err: any) {
      setError(err.message || "Registration failed");
    }
  };

  return (
    <>
      {/* Mode tabs */}
      <div className="login-tabs">
        <button
          className={`login-tab ${mode === "login" ? "active" : ""}`}
          onClick={() => { setMode("login"); setError(""); }}
        >
          Sign In
        </button>
        <button
          className={`login-tab ${mode === "register" ? "active" : ""}`}
          onClick={() => { setMode("register"); setError(""); }}
        >
          Create Account
        </button>
      </div>

      <form onSubmit={handleSubmit} className="login-form">
        {error && <div className="login-error">{error}</div>}
        {mode === "register" && (
          <div className="login-field">
            <label htmlFor="name">Name (optional)</label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
            />
          </div>
        )}
        <div className="login-field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
          />
        </div>
        <div className="login-field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            minLength={6}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading
            ? "Processing..."
            : mode === "login"
              ? "Sign In"
              : "Create Account"}
        </button>
      </form>
      <p className="login-hint">
        {mode === "login"
          ? "Sign in with your AEON OS account credentials."
          : "Create a free workspace to start using AEON OS."}
      </p>
    </>
  );
}

export default function LoginPage() {
  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="login-logo">⟁</div>
          <h1>AEON OS</h1>
          <p>Enterprise AI Operating System</p>
        </div>
        <Suspense fallback={<div className="login-hint">Loading...</div>}>
          <AuthForm />
        </Suspense>
      </div>
    </div>
  );
}
