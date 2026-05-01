import { AuthenticationError, InvokeError, SynapseClient } from "../src";
import type { ServiceRecord } from "../src";

export const DEFAULT_FIXED_PAYLOAD: Record<string, unknown> = { prompt: "hello" };
export const DEFAULT_LLM_PAYLOAD: Record<string, unknown> = {
  messages: [{ role: "user", content: "hello" }],
};

export interface E2eEvent {
  language: "typescript";
  scenario: string;
  invocationId?: string;
  status?: string;
  chargedUsdc?: string;
  receiptStatus?: string;
  serviceId?: string;
}

export function client(credential = requireEnv("SYNAPSE_AGENT_KEY")): SynapseClient {
  const gatewayUrl = process.env.SYNAPSE_GATEWAY_URL?.trim();
  return new SynapseClient({
    credential,
    gatewayUrl: gatewayUrl || undefined,
    environment: gatewayUrl ? undefined : "staging",
  });
}

export function requireEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required`);
  return value;
}

export function envDefault(name: string, fallback: string): string {
  return process.env[name]?.trim() || fallback;
}

export function envBool(name: string): boolean {
  return ["1", "true", "yes", "y"].includes((process.env[name] ?? "").trim().toLowerCase());
}

export function idempotencyKey(language: string, scenario: string): string {
  const runId = process.env.E2E_RUN_ID?.trim();
  const prefix = runId ? `${runId}-${language}-e2e` : `${language}-e2e`;
  return `${prefix}-${scenario}-${Date.now()}`;
}

export function envInt(name: string, fallback: number): number {
  const value = Number.parseInt((process.env[name] ?? "").trim(), 10);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

export function jsonPayload(name: string, fallback: Record<string, unknown>): Record<string, unknown> {
  const raw = process.env[name]?.trim();
  if (!raw) return fallback;
  const parsed = JSON.parse(raw) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${name} must be a JSON object`);
  }
  return parsed as Record<string, unknown>;
}

export async function fixedTarget(
  synapse: SynapseClient
): Promise<{ serviceId: string; costUsdc: string; payload: Record<string, unknown> }> {
  const payload = jsonPayload("SYNAPSE_E2E_FIXED_PAYLOAD_JSON", DEFAULT_FIXED_PAYLOAD);
  const configuredServiceId = process.env.SYNAPSE_E2E_FIXED_SERVICE_ID?.trim();
  if (configuredServiceId) {
    const configuredCost = process.env.SYNAPSE_E2E_FIXED_COST_USDC?.trim();
    if (!configuredCost) {
      throw new Error("SYNAPSE_E2E_FIXED_COST_USDC is required when SYNAPSE_E2E_FIXED_SERVICE_ID is set");
    }
    return { serviceId: configuredServiceId, costUsdc: configuredCost, payload };
  }

  const services = await synapse.search("free", { limit: 25 });
  const service = services.find(isFreeFixedApiService);
  if (!service) {
    throw new Error(
      "no free fixed-price API service found; set SYNAPSE_E2E_FIXED_SERVICE_ID, " +
        "SYNAPSE_E2E_FIXED_COST_USDC, and SYNAPSE_E2E_FIXED_PAYLOAD_JSON"
    );
  }
  return {
    serviceId: service.serviceId ?? service.id ?? "",
    costUsdc: pricingAmount(service),
    payload,
  };
}

export function pricingAmount(service: ServiceRecord): string {
  const pricing = service.pricing;
  if (typeof pricing === "string") return pricing;
  if (pricing && typeof pricing === "object" && "amount" in pricing) {
    return String(pricing.amount ?? "");
  }
  return "";
}

export function isFreeFixedApiService(service: ServiceRecord): boolean {
  return (
    Boolean(service.serviceId ?? service.id) &&
    String(service.serviceKind ?? "").toLowerCase() === "api" &&
    String(service.priceModel ?? "").toLowerCase() === "fixed" &&
    decimalEquals(pricingAmount(service), "0")
  );
}

export async function awaitReceipt(synapse: SynapseClient, invocationId: string) {
  if (!invocationId.trim()) throw new Error("invoke returned empty invocationId");
  const deadline = Date.now() + envInt("SYNAPSE_E2E_RECEIPT_TIMEOUT_S", 60) * 1000;
  while (true) {
    const receipt = await synapse.getInvocation(invocationId);
    if (receipt.invocationId && receipt.invocationId !== invocationId) {
      throw new Error(`receipt invocationId mismatch: got ${receipt.invocationId} want ${invocationId}`);
    }
    if (receipt.status === "SUCCEEDED" || receipt.status === "SETTLED") return receipt;
    if (Date.now() > deadline) {
      throw new Error(`receipt ${invocationId} did not reach a terminal status, last status=${receipt.status}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
}

export async function localNegative(synapse: SynapseClient): Promise<void> {
  await expectError(
    () =>
      synapse.invoke(
        "svc_local",
        {},
        {
          costUsdc: "",
        }
      ),
    Error
  );
  await expectError(() => synapse.invokeLlm("svc_llm", { stream: true }), InvokeError);
  emit({ language: "typescript", scenario: "local-negative", status: "ok" });
}

export async function authNegative(): Promise<void> {
  await expectError(
    () =>
      client("agt_invalid").invoke(
        "svc_invalid_auth_probe",
        {},
        {
          costUsdc: "0",
        }
      ),
    AuthenticationError
  );
  emit({ language: "typescript", scenario: "auth-negative", status: "ok" });
}

export async function expectError<T extends Error>(
  action: () => Promise<unknown>,
  expectedType: new (...args: any[]) => T
): Promise<void> {
  try {
    await action();
  } catch (err) {
    if (err instanceof expectedType) return;
    throw err;
  }
  throw new Error(`expected ${expectedType.name}`);
}

export function emit(event: E2eEvent): void {
  const compact = Object.fromEntries(Object.entries(event).filter(([, value]) => value !== undefined && value !== ""));
  console.log(JSON.stringify(compact));
}

export function decimalEquals(left: string, right: string): boolean {
  return decimalCents(left) === decimalCents(right);
}

export function decimalLessThanOrEqual(left: string, right: string): boolean {
  return decimalCents(left) <= decimalCents(right);
}

function decimalCents(value: string): bigint {
  const [whole, fraction = ""] = value.trim().split(".");
  return BigInt(whole || "0") * 1_000_000n + BigInt((fraction + "000000").slice(0, 6));
}
