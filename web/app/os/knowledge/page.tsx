import { guardModuleRoute } from "@/lib/module-guard";
import KnowledgePageClient from "./KnowledgePageClient";

export default async function KnowledgePage() {
  await guardModuleRoute("knowledge", "/os");
  return <KnowledgePageClient />;
}
