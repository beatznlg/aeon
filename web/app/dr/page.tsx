import { guardModuleRoute } from "@/lib/module-guard";
import DRPageClient from "./DRPageClient";

export default async function DRPage() {
  await guardModuleRoute("dr", "/os");
  return <DRPageClient />;
}
