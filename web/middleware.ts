import { auth } from "@/auth";
import { getRole } from "@/lib/auth";

export default auth((req) => {
  const isLoggedIn = !!req.auth;
  const { pathname } = req.nextUrl;
  const role = getRole(req.auth);

  const isProtectedRoute =
    pathname.startsWith("/os") || pathname.startsWith("/settings");

  if (isProtectedRoute && !isLoggedIn) {
    return Response.redirect(new URL("/login", req.nextUrl));
  }

  // Admin-only routes
  if (pathname.startsWith("/admin") && role !== "ADMIN") {
    return Response.redirect(new URL("/settings", req.nextUrl));
  }

  // Operator-level write routes (API only)
  if (
    pathname.startsWith("/api/admin") &&
    role !== "ADMIN"
  ) {
    return Response.json({ ok: false, error: "forbidden" }, { status: 403 });
  }
});

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
