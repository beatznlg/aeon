type JsonRecord = Record<string, unknown>;

function parseRecord(value: unknown): JsonRecord {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as JsonRecord;
  }
  if (typeof value === "string") {
    try {
      const parsed: unknown = JSON.parse(value);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed)
        ? (parsed as JsonRecord)
        : {};
    } catch {
      return {};
    }
  }
  return {};
}

function capabilityIdFrom(approval: JsonRecord): string | null {
  const actionConfig = parseRecord(approval.action_config);
  const eventPayload = parseRecord(approval.event_payload);
  const payload = parseRecord(eventPayload.payload);
  const review = parseRecord(approval.capability_review);
  const candidate = review.capability_id ?? actionConfig.capability_id ?? payload.capability_id;
  return typeof candidate === "string" && candidate.trim() ? candidate : null;
}

/** Strip sensitive approval fields before a response is returned to the browser. */
export function sanitizeApproval(value: unknown): JsonRecord {
  const approval = parseRecord(value);
  const safe: JsonRecord = { ...approval };
  const isCapability = safe.action_type === "capability" || Boolean(capabilityIdFrom(safe));

  if (isCapability) {
    delete safe.action_config;
    delete safe.event_payload;
    delete safe.result;
    safe.capability_review = {
      capability_id: capabilityIdFrom(approval),
      sensitive_values_withheld: true,
    };
  } else {
    // Generic automation payloads may also contain webhook bodies or secrets.
    delete safe.event_payload;
    delete safe.action_config;
    delete safe.result;
  }

  return safe;
}

/** Sanitize the response envelopes used by the approval proxy routes. */
export function sanitizeApprovalResponse(value: unknown): unknown {
  const body = parseRecord(value);
  const safe: JsonRecord = { ...body };
  if (Array.isArray(body.approvals)) {
    safe.approvals = body.approvals.map(sanitizeApproval);
  }
  if (body.approval) {
    safe.approval = sanitizeApproval(body.approval);
  }
  delete safe.result;
  return safe;
}
