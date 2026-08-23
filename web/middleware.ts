import { auth } from "@/auth";
import { getRole } from "@/lib/auth";

export default auth((req) => {
  const isLoggedIn = !!req.auth;
  const { pathname } = req.nextUrl;
  const role = getRole(req.auth);

  const isProtectedRoute =
    pathname === "/" ||
    pathname.startsWith("/os") ||
    pathname.startsWith("/settings") ||
    pathname.startsWith("/chat") ||
    pathname.startsWith("/onboarding");

  if (isProtectedRoute && !isLoggedIn) {
    const loginUrl = new URL("/login", req.nextUrl);
    loginUrl.searchParams.set("callbackUrl", pathname);
    return Response.redirect(loginUrl);
  }

  // Admin-only routes
  if (pathname.startsWith("/admin") && role !== "ADMIN") {
    return Response.redirect(new URL("/settings", req.nextUrl));
  }

  // Operator-level write routes (API only)
  if (pathname.startsWith("/api/admin") && role !== "ADMIN") {
    return Response.json({ ok: false, error: "forbidden" }, { status: 403 });
  }
});

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
  // Next.js 15.5+: run middleware on the Node.js runtime instead of the
  // deprecated Edge runtime (Vercel deprecated Edge for anonymous deployments).
  runtime: "nodejs",
};
