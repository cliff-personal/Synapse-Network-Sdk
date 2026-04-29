import {
  RegisterProviderServiceOptions,
  RegisterProviderServiceResult,
  ProviderServiceRecord,
  ProviderServiceStatus,
  IssueCredentialOptions,
  IssueProviderSecretResult,
  ProviderSecret,
  ProviderEarningsSummary,
  ProviderRegistrationGuide,
  ProviderSecretDeleteResult,
  ProviderServiceDeleteResult,
  ProviderServiceHealthHistory,
  ProviderServicePingResult,
  ProviderServiceUpdateResult,
  ProviderWithdrawalCapability,
  ProviderWithdrawalIntentResult,
  ProviderWithdrawalList,
  ServiceManifestDraft,
} from "./types";
import { AuthenticationError } from "./errors";

type FetchJson = <T>(
  url: string,
  init?: { method?: string; body?: string; headers?: Record<string, string> }
) => Promise<T>;

export interface AuthProviderControlContext {
  gatewayUrl: string;
  walletAddress: string;
  getToken: () => Promise<string>;
  fetchJson: FetchJson;
  requireValue: (value: string, name: string) => string;
  withQuery: (url: string, params: Record<string, string | number | boolean | null | undefined>) => string;
}

function credentialOptionsBody(opts: IssueCredentialOptions): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (opts.name) body["name"] = opts.name;
  if (opts.maxCalls != null) body["maxCalls"] = opts.maxCalls;
  if (opts.creditLimit != null) body["creditLimit"] = opts.creditLimit;
  if (opts.resetInterval != null) body["resetInterval"] = opts.resetInterval;
  if (opts.rpm != null) body["rpm"] = opts.rpm;
  if (opts.expiresInSec != null) body["expiresInSec"] = opts.expiresInSec;
  return body;
}

export async function issueProviderSecret(
  ctx: AuthProviderControlContext,
  opts: IssueCredentialOptions = {}
): Promise<IssueProviderSecretResult> {
  const token = await ctx.getToken();
  const resp = await ctx.fetchJson<Record<string, unknown>>(`${ctx.gatewayUrl}/api/v1/secrets/provider/issue`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(credentialOptionsBody(opts)),
  });
  const secret = (resp["secret"] as ProviderSecret | undefined) ?? undefined;
  if (!secret?.id) {
    throw new AuthenticationError(`Provider secret payload missing: ${JSON.stringify(resp)}`);
  }
  return { status: resp["status"] as string | undefined, secret };
}

export async function listProviderSecrets(ctx: AuthProviderControlContext): Promise<ProviderSecret[]> {
  const token = await ctx.getToken();
  const resp = await ctx.fetchJson<{ secrets?: ProviderSecret[] }>(`${ctx.gatewayUrl}/api/v1/secrets/provider/list`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return resp.secrets ?? [];
}

export async function deleteProviderSecret(
  ctx: AuthProviderControlContext,
  secretId: string
): Promise<ProviderSecretDeleteResult> {
  const token = await ctx.getToken();
  const id = ctx.requireValue(secretId, "secretId");
  return ctx.fetchJson<ProviderSecretDeleteResult>(
    `${ctx.gatewayUrl}/api/v1/secrets/provider/${encodeURIComponent(id)}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

function defaultServiceId(serviceName: string): string {
  const normalized = serviceName.trim().toLowerCase().replace(/\s+/g, "_");
  const sanitized = normalized
    .replace(/[^a-z0-9_-]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
  return sanitized || `service_${Date.now().toString(36)}`;
}

function requiredTrim(value: string | undefined, name: string): string {
  const resolved = String(value ?? "").trim();
  if (!resolved) throw new Error(`${name} is required`);
  return resolved;
}

function optionalTrim(value: string | undefined): string | null {
  const resolved = String(value ?? "").trim();
  return resolved.length > 0 ? resolved : null;
}

function valueOr<T>(value: T | null | undefined, fallback: T): T {
  return value === null || value === undefined ? fallback : value;
}

function providerServiceValues(opts: RegisterProviderServiceOptions) {
  const serviceName = requiredTrim(opts.serviceName, "serviceName");
  const endpointUrl = requiredTrim(opts.endpointUrl, "endpointUrl");
  return {
    serviceName,
    endpointUrl,
    description: requiredTrim(opts.descriptionForModel, "descriptionForModel"),
    serviceId: optionalTrim(opts.serviceId) ?? defaultServiceId(serviceName),
  };
}

function providerServiceBody(ctx: AuthProviderControlContext, opts: RegisterProviderServiceOptions) {
  const service = providerServiceValues(opts);
  const serviceKind = opts.serviceKind ?? (opts.priceModel === "token_metered" ? "llm" : "api");
  const priceModel = opts.priceModel ?? (serviceKind === "llm" ? "token_metered" : "fixed");
  return {
    serviceId: service.serviceId,
    agentToolName: service.serviceId,
    serviceName: service.serviceName,
    serviceKind,
    priceModel,
    role: "Provider",
    status: valueOr(opts.status, "active"),
    isActive: valueOr(opts.isActive, true),
    pricing: providerPricing(opts, priceModel),
    summary: service.description,
    tags: valueOr(opts.tags, []),
    auth: { type: "gateway_signed" },
    invoke: providerInvokeConfig(service.endpointUrl, opts),
    healthCheck: providerHealthCheck(opts),
    providerProfile: providerProfile(opts.providerDisplayName, service.serviceName),
    payoutAccount: providerPayoutAccount(ctx, opts),
    governance: {
      termsAccepted: true,
      riskAcknowledged: true,
      note: valueOr(opts.governanceNote, null),
    },
  };
}

function providerPricing(opts: RegisterProviderServiceOptions, priceModel: string): Record<string, unknown> {
  if (priceModel === "token_metered") {
    if (opts.inputPricePer1MTokensUsdc == null) throw new Error("inputPricePer1MTokensUsdc is required");
    if (opts.outputPricePer1MTokensUsdc == null) throw new Error("outputPricePer1MTokensUsdc is required");
    const pricing: Record<string, unknown> = {
      priceModel: "token_metered",
      inputPricePer1MTokensUsdc: String(opts.inputPricePer1MTokensUsdc),
      outputPricePer1MTokensUsdc: String(opts.outputPricePer1MTokensUsdc),
      currency: "USDC",
    };
    if (opts.defaultMaxOutputTokens != null) pricing["defaultMaxOutputTokens"] = opts.defaultMaxOutputTokens;
    if (opts.holdBufferMultiplier != null) pricing["holdBufferMultiplier"] = opts.holdBufferMultiplier;
    if (opts.maxAutoHoldUsdc != null) pricing["maxAutoHoldUsdc"] = String(opts.maxAutoHoldUsdc);
    return pricing;
  }
  if (opts.basePriceUsdc == null) throw new Error("basePriceUsdc is required");
  return {
    amount: String(opts.basePriceUsdc),
    currency: "USDC",
  };
}

function providerInvokeConfig(endpointUrl: string, opts: RegisterProviderServiceOptions) {
  return {
    method: valueOr(opts.endpointMethod, "POST"),
    targets: [{ url: endpointUrl }],
    timeoutMs: valueOr(opts.requestTimeoutMs, 15_000),
    request: { body: valueOr(opts.inputSchema, { type: "object", properties: {}, required: [] }) },
    response: { body: valueOr(opts.outputSchema, { type: "object", properties: {} }) },
  };
}

function providerHealthCheck(opts: RegisterProviderServiceOptions) {
  return {
    path: valueOr(opts.healthPath, "/health"),
    method: valueOr(opts.healthMethod, "GET"),
    timeoutMs: valueOr(opts.healthTimeoutMs, 3_000),
    successCodes: [200],
    healthyThreshold: 1,
    unhealthyThreshold: 3,
  };
}

function providerProfile(providerDisplayName: string | undefined, serviceName: string) {
  return { displayName: optionalTrim(providerDisplayName) ?? serviceName };
}

function providerPayoutAccount(ctx: AuthProviderControlContext, opts: RegisterProviderServiceOptions) {
  return {
    payoutAddress: optionalTrim(opts.payoutAddress) ?? ctx.walletAddress,
    chainId: valueOr(opts.chainId, 31337),
    settlementCurrency: valueOr(opts.settlementCurrency, "USDC"),
  };
}

export async function registerProviderService(
  ctx: AuthProviderControlContext,
  opts: RegisterProviderServiceOptions
): Promise<RegisterProviderServiceResult> {
  const body = providerServiceBody(ctx, opts);
  const token = await ctx.getToken();
  const resp = await ctx.fetchJson<Record<string, unknown>>(`${ctx.gatewayUrl}/api/v1/services`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });

  const service =
    (resp["service"] as ProviderServiceRecord | undefined) ??
    ({
      serviceId: body.serviceId,
    } as ProviderServiceRecord);
  const responseServiceId =
    (resp["serviceId"] as string | undefined) ?? service.serviceId ?? service.id ?? body.serviceId;
  return {
    status: resp["status"] as string | undefined,
    serviceId: responseServiceId,
    service,
  };
}

export async function listProviderServices(ctx: AuthProviderControlContext): Promise<ProviderServiceRecord[]> {
  const token = await ctx.getToken();
  const resp = await ctx.fetchJson<{ services?: ProviderServiceRecord[] }>(`${ctx.gatewayUrl}/api/v1/services`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return resp.services ?? [];
}

export async function getRegistrationGuide(ctx: AuthProviderControlContext): Promise<ProviderRegistrationGuide> {
  const token = await ctx.getToken();
  return ctx.fetchJson<ProviderRegistrationGuide>(`${ctx.gatewayUrl}/api/v1/services/registration-guide`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function parseCurlToServiceManifest(
  ctx: AuthProviderControlContext,
  curlCommand: string
): Promise<ServiceManifestDraft> {
  const token = await ctx.getToken();
  const command = ctx.requireValue(curlCommand, "curlCommand");
  return ctx.fetchJson<ServiceManifestDraft>(`${ctx.gatewayUrl}/api/v1/services/parse-curl`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ curlCommand: command }),
  });
}

export async function updateProviderService(
  ctx: AuthProviderControlContext,
  serviceRecordId: string,
  patch: Record<string, unknown>
): Promise<ProviderServiceUpdateResult> {
  const token = await ctx.getToken();
  const id = ctx.requireValue(serviceRecordId, "serviceRecordId");
  return ctx.fetchJson<ProviderServiceUpdateResult>(`${ctx.gatewayUrl}/api/v1/services/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(patch ?? {}),
  });
}

export async function deleteProviderService(
  ctx: AuthProviderControlContext,
  serviceRecordId: string
): Promise<ProviderServiceDeleteResult> {
  const token = await ctx.getToken();
  const id = ctx.requireValue(serviceRecordId, "serviceRecordId");
  return ctx.fetchJson<ProviderServiceDeleteResult>(`${ctx.gatewayUrl}/api/v1/services/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function pingProviderService(
  ctx: AuthProviderControlContext,
  serviceRecordId: string
): Promise<ProviderServicePingResult> {
  const token = await ctx.getToken();
  const id = ctx.requireValue(serviceRecordId, "serviceRecordId");
  return ctx.fetchJson<ProviderServicePingResult>(`${ctx.gatewayUrl}/api/v1/services/${encodeURIComponent(id)}/ping`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getProviderServiceHealthHistory(
  ctx: AuthProviderControlContext,
  serviceRecordId: string,
  opts: { limitPerTarget?: number } = {}
): Promise<ProviderServiceHealthHistory> {
  const token = await ctx.getToken();
  const id = ctx.requireValue(serviceRecordId, "serviceRecordId");
  const url = ctx.withQuery(`${ctx.gatewayUrl}/api/v1/services/${encodeURIComponent(id)}/health/history`, {
    limitPerTarget: opts.limitPerTarget ?? 100,
  });
  return ctx.fetchJson<ProviderServiceHealthHistory>(url, { headers: { Authorization: `Bearer ${token}` } });
}

export async function getProviderEarningsSummary(ctx: AuthProviderControlContext): Promise<ProviderEarningsSummary> {
  const token = await ctx.getToken();
  return ctx.fetchJson<ProviderEarningsSummary>(`${ctx.gatewayUrl}/api/v1/providers/earnings/summary`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getProviderWithdrawalCapability(
  ctx: AuthProviderControlContext
): Promise<ProviderWithdrawalCapability> {
  const token = await ctx.getToken();
  return ctx.fetchJson<ProviderWithdrawalCapability>(`${ctx.gatewayUrl}/api/v1/providers/withdrawals/capability`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function createProviderWithdrawalIntent(
  ctx: AuthProviderControlContext,
  amountUsdc: number,
  opts: { idempotencyKey?: string; destinationAddress?: string } = {}
): Promise<ProviderWithdrawalIntentResult> {
  const token = await ctx.getToken();
  const body: Record<string, unknown> = { amountUsdc };
  if (opts.destinationAddress) body["destinationAddress"] = opts.destinationAddress;
  return ctx.fetchJson<ProviderWithdrawalIntentResult>(`${ctx.gatewayUrl}/api/v1/providers/withdrawals/intent`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Idempotency-Key":
        opts.idempotencyKey ?? `provider-withdraw-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    },
    body: JSON.stringify(body),
  });
}

export async function listProviderWithdrawals(
  ctx: AuthProviderControlContext,
  opts: { limit?: number } = {}
): Promise<ProviderWithdrawalList> {
  const token = await ctx.getToken();
  const url = ctx.withQuery(`${ctx.gatewayUrl}/api/v1/providers/withdrawals`, { limit: opts.limit ?? 100 });
  return ctx.fetchJson<ProviderWithdrawalList>(url, { headers: { Authorization: `Bearer ${token}` } });
}

export async function getProviderService(
  ctx: AuthProviderControlContext,
  serviceId: string
): Promise<ProviderServiceRecord> {
  const resolvedServiceId = serviceId?.trim();
  if (!resolvedServiceId) throw new Error("serviceId is required");
  const services = await listProviderServices(ctx);
  const found = services.find((service) => service.serviceId === resolvedServiceId);
  if (!found) {
    throw new AuthenticationError(`Provider service not found: ${resolvedServiceId}`);
  }
  return found;
}

export async function getProviderServiceStatus(
  ctx: AuthProviderControlContext,
  serviceId: string
): Promise<ProviderServiceStatus> {
  const service = await getProviderService(ctx, serviceId);
  return {
    serviceId: service.serviceId ?? service.id ?? serviceId,
    lifecycleStatus: service.status ?? "unknown",
    runtimeAvailable: Boolean(service.runtimeAvailable),
    health: (service.health ?? {}) as ProviderServiceStatus["health"],
  };
}
