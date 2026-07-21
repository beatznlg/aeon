import { DefaultSession } from "next-auth";
import "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      role: string;
      workspaceId?: string;
    } & DefaultSession["user"];
  }

  interface User {
    workspaceId?: string;
  }

  interface JWT {
    workspaceId?: string;
  }
}
