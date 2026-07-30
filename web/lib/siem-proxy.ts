import { proxyApiRequest, ProxyOptions } from "./proxy";

export type { ProxyOptions };

/**
 * @deprecated Use proxyApiRequest from "@/lib/proxy" instead.
 * Kept for backward compatibility with existing SIEM routes.
 */
export const proxySiemRequest = proxyApiRequest;
