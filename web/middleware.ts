import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  const isProtectedRoute =
    pathname === "/" ||
    pathname.startsWith("/os") ||
    pathname.startsWith("/settings") ||
    pathname.startsWith("/chat") ||
    pathname.startsWith("/onboarding");

  if (isProtectedRoute) {
    const token = await getToken({
      req,
      secret: process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET || "aeon-dev-fallback-do-not-use-in-production",
    });
    if (!token) {
      const loginUrl = new URL("/login", req.nextUrl);
      loginUrl.searchParams.set("callbackUrl", pathname);
      return NextResponse.redirect(loginUrl);
    }
    const role = (token.role as string) || "VIEWER";

    // Admin-only routes
    if (pathname.startsWith("/admin") && role !== "ADMIN") {
      return NextResponse.redirect(new URL("/settings", req.nextUrl));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
