import { guardModuleRoute } from "@/lib/module-guard";
import AIStudioPageClient from "./AIStudioPageClient";

export default async function AIStudioPage() {
  await guardModuleRoute("aiStudio", "/os");
  return <AIStudioPageClient />;
}
