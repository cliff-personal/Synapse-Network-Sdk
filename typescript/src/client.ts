/**
 * SynapseClient — Consumer API client.
 *
 * Uses an agent credential (X-Credential header) for service discovery,
 * and invocation. Get a credential via SynapseAuth.issueCredential().
 */
import { v4 as uuidv4 } from "uuid";
import { resolveGatewayUrl } from "./config";
import {
  SynapseClientOptions,
  ServiceRecord,
  DiscoverOptions,
  InvokeOptions,
  LlmInvokeOptions,
  InvocationResult,
  InvocationStatus,
  TERMINAL_STATUSES,
} from "./types";
import {
  AuthenticationError,
  InsufficientFundsError,
  InvokeError,
  DiscoveryError,
  TimeoutError,
  PriceMismatchError,
} from "./errors";
import { fetchJson, HttpErrorContext } from "./http";

export class SynapseClient {
  private readonly credential: string;
  private readonly gatewayUrl: string;
  private readonly timeoutMs: number;

  constructor(opts: SynapseClientOptions) {
    if (!opts.credential?.trim()) {
      throw new Error("credential is required. Get one via SynapseAuth.issueCredential().");
    }
    this.credential = opts.credential.trim();
    this.gatewayUrl = resolveGatewayUrl({ environment: opts.environment, gatewayUrl: opts.gatewayUrl });
    this.timeoutMs = opts.timeoutMs ?? 30_000;
  }

  // ── Service Discovery ──────────────────────────────────────────────────────

  /** Discover registered services on the platform. */
  async discover(opts: DiscoverOptions = {}): Promise<ServiceRecord[]> {
    try {
      return await this.search("", opts);
    } catch (err) {
      throw new DiscoveryError(String(err instanceof Error ? err.message : err));
    }
  }

  /** Search for services by text query. */
  async search(query: string, opts: DiscoverOptions = {}): Promise<ServiceRecord[]> {
    try {
      const resp = await this._fetch<{ services?: ServiceRecord[]; results?: ServiceRecord[] }>(
        `${this.gatewayUrl}/api/v1/agent/discovery/search`,
        discoveryRequest(query, opts)
      );
      return discoveryServices(resp);
    } catch (err) {
      throw discoveryError(err);
    }
  }

  /** Check the public gateway health endpoint without consuming agent budget. */
  async checkGatewayHealth(): Promise<Record<string, unknown>> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const resp = await fetch(`${this.gatewayUrl}/health`, { signal: controller.signal });
      const text = await resp.text();
      const data = text ? (JSON.parse(text) as Record<string, unknown>) : {};
      if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${text}`);
      return data;
    } finally {
      clearTimeout(timer);
    }
  }

  /** Return agent-friendly diagnostics for an empty discovery result. */
  explainDiscoveryEmptyResult(opts: { query?: string; tags?: string[] } = {}): Record<string, unknown> {
    return {
      query: opts.query ?? "",
      tags: opts.tags ?? [],
      possibleReasons: [
        "No provider service matched the current discovery filters.",
        "The matching provider may be inactive, unhealthy, or not yet registered in this environment.",
        "The agent credential may target a different environment than the provider service.",
      ],
      suggestions: [
        "Retry with a broader query and no tags.",
        "Confirm environment / gatewayUrl matches the provider registration environment.",
        "Ask the provider owner to verify service status and health history.",
      ],
    };
  }

  // ── Invocation ─────────────────────────────────────────────────────────────

  /**
   * Invoke a service by ID.
   *
   * Pass `opts.costUsdc` — the price the agent observed during discovery.
   * Gateway returns 422 PRICE_MISMATCH if the live price has changed;
   * the caller should re-discover and retry.
   */
  async invoke(
    serviceId: string,
    payload: Record<string, unknown> = {},
    opts: InvokeOptions
  ): Promise<InvocationResult> {
    if (!serviceId.trim()) {
      throw new Error("serviceId is required");
    }
    if (opts.costUsdc === undefined || String(opts.costUsdc).trim() === "") {
      throw new Error("costUsdc is required for fixed-price API services. Use invokeLlm() for LLM services.");
    }
    try {
      const resp = await this._fetch<Record<string, unknown>>(
        `${this.gatewayUrl}/api/v1/agent/invoke`,
        invokeRequest(serviceId, payload, opts)
      );
      return this.completeInvocation(resp, opts);
    } catch (err) {
      throw invokeError(err);
    }
  }

  /**
   * Invoke an LLM service with token-metered billing.
   *
   * Do not pass costUsdc for LLM services. Gateway either uses maxCostUsdc as
   * an explicit cap or computes an automatic pre-authorization hold, then
   * captures only the final Provider-reported usage.
   */
  async invokeLlm(
    serviceId: string,
    payload: Record<string, unknown> = {},
    opts: LlmInvokeOptions = {}
  ): Promise<InvocationResult> {
    assertLlmSyncPayload(payload, opts);
    try {
      const resp = await this._fetch<Record<string, unknown>>(
        `${this.gatewayUrl}/api/v1/agent/invoke`,
        llmInvokeRequest(serviceId, payload, opts)
      );
      return this.completeInvocation(resp, opts);
    } catch (err) {
      throw invokeError(err);
    }
  }

  /**
   * Invoke once, then handle PRICE_MISMATCH by re-discovering and retrying once by default.
   */
  async invokeWithRediscovery(
    serviceId: string,
    payload: Record<string, unknown> = {},
    opts: InvokeOptions & {
      query?: string;
      tags?: string[];
      maxRediscoveryRetries?: number;
    }
  ): Promise<InvocationResult> {
    try {
      return await this.invoke(serviceId, payload, opts);
    } catch (err) {
      if (!(err instanceof PriceMismatchError) || (opts.maxRediscoveryRetries ?? 1) <= 0) {
        throw err;
      }

      const livePrice = await this.rediscoveredPrice(serviceId, err.currentPriceUsdc, opts);
      if (!livePrice || livePrice <= 0) throw err;

      return this.invoke(serviceId, payload, {
        ...opts,
        costUsdc: livePrice,
        maxRediscoveryRetries: undefined,
      } as InvokeOptions);
    }
  }

  /** Poll invocation receipt until it reaches a terminal status. */
  async waitForInvocation(
    invocationId: string,
    opts: { pollTimeoutMs?: number; pollIntervalMs?: number } = {}
  ): Promise<InvocationResult> {
    const timeoutMs = opts.pollTimeoutMs ?? 90_000;
    const intervalMs = opts.pollIntervalMs ?? 1_500;
    const deadline = Date.now() + timeoutMs;

    while (Date.now() < deadline) {
      const receipt = await this.getInvocation(invocationId);
      if (TERMINAL_STATUSES.has(receipt.status)) return receipt;
      await _sleep(intervalMs);
    }
    throw new TimeoutError(`Invocation ${invocationId} still pending after ${timeoutMs}ms`);
  }

  /** Fetch an invocation receipt by ID. */
  async getInvocation(invocationId: string): Promise<InvocationResult> {
    const resp = await this._fetch<Record<string, unknown>>(
      `${this.gatewayUrl}/api/v1/agent/invocations/${encodeURIComponent(invocationId)}`
    );
    return this._parseInvocationResponse(resp);
  }

  /** Alias for getInvocation(). */
  async getInvocationReceipt(invocationId: string): Promise<InvocationResult> {
    return this.getInvocation(invocationId);
  }

  // ── Internal helpers ───────────────────────────────────────────────────────

  private _parseInvocationResponse(resp: Record<string, unknown>): InvocationResult {
    return parseInvocationResponse(resp);
  }

  private async _fetch<T>(
    url: string,
    init: {
      method?: string;
      body?: string;
      extraHeaders?: Record<string, string>;
    } = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Credential": this.credential,
      ...(init.extraHeaders ?? {}),
    };
    return fetchJson<T>(
      url,
      { method: init.method, body: init.body, headers, timeoutMs: this.timeoutMs },
      clientHttpError
    );
  }

  private async rediscoveredPrice(
    serviceId: string,
    fallbackPrice: number | null,
    opts: InvokeOptions & { query?: string; tags?: string[] }
  ): Promise<number | null> {
    const services = await this.search(opts.query ?? serviceId, { limit: 10, tags: opts.tags });
    const matched = services.find((service) => serviceKey(service) === serviceId);
    return matched ? (extractServicePrice(matched) ?? fallbackPrice) : fallbackPrice;
  }

  private completeInvocation(
    resp: Record<string, unknown>,
    opts: { pollTimeoutMs?: number; pollIntervalMs?: number }
  ): Promise<InvocationResult> | InvocationResult {
    const result = this._parseInvocationResponse(resp);
    if (TERMINAL_STATUSES.has(result.status)) return result;
    if (opts.pollTimeoutMs === 0) return result;
    return this.waitForInvocation(result.invocationId, opts);
  }
}

function _sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function discoveryServices(
  resp: { services?: ServiceRecord[]; results?: ServiceRecord[] } | ServiceRecord[]
): ServiceRecord[] {
  if (Array.isArray(resp)) return resp;
  return resp.services ?? resp.results ?? [];
}

function discoveryRequest(query: string, opts: DiscoverOptions) {
  const pageSize = Math.max(1, opts.limit ?? 20);
  const offset = Math.max(0, opts.offset ?? 0);
  return {
    method: "POST",
    body: JSON.stringify({
      query: query.trim() || undefined,
      tags: opts.tags ?? [],
      page: Math.floor(offset / pageSize) + 1,
      pageSize,
      sort: opts.sort ?? "best_match",
    }),
  };
}

function discoveryError(err: unknown): DiscoveryError {
  return new DiscoveryError(String(err instanceof Error ? err.message : err));
}

function invokeRequest(serviceId: string, payload: Record<string, unknown>, opts: InvokeOptions) {
  const body: Record<string, unknown> = {
    serviceId,
    idempotencyKey: opts.idempotencyKey ?? uuidv4(),
    payload: { body: payload },
    responseMode: opts.responseMode ?? "sync",
  };
  body["costUsdc"] = opts.costUsdc;
  return {
    method: "POST",
    extraHeaders: requestHeaders(opts.requestId),
    body: JSON.stringify(body),
  };
}

function llmInvokeRequest(serviceId: string, payload: Record<string, unknown>, opts: LlmInvokeOptions) {
  const body: Record<string, unknown> = {
    serviceId,
    idempotencyKey: opts.idempotencyKey ?? uuidv4(),
    payload: { body: payload },
    responseMode: "sync",
  };
  if (opts.maxCostUsdc !== undefined) body["maxCostUsdc"] = opts.maxCostUsdc;
  return {
    method: "POST",
    extraHeaders: requestHeaders(opts.requestId),
    body: JSON.stringify(body),
  };
}

function assertLlmSyncPayload(payload: Record<string, unknown>, opts: LlmInvokeOptions): void {
  if (opts.responseMode && opts.responseMode !== "sync") {
    throw new InvokeError("LLM_STREAMING_NOT_SUPPORTED: LLM services only support sync responses in Synapse V1.");
  }
  if (payload["stream"] === true) {
    throw new InvokeError("LLM_STREAMING_NOT_SUPPORTED: stream=true is not supported for token-metered LLM billing.");
  }
}

function requestHeaders(requestId: string | undefined): Record<string, string> {
  return requestId ? { "X-Request-Id": requestId } : {};
}

function isInvokePassthroughError(err: unknown): boolean {
  return (
    err instanceof AuthenticationError || err instanceof InsufficientFundsError || err instanceof PriceMismatchError
  );
}

function invokeError(err: unknown): Error {
  return isInvokePassthroughError(err)
    ? (err as Error)
    : new InvokeError(String(err instanceof Error ? err.message : err));
}

function serviceKey(service: ServiceRecord): string | undefined {
  return service.serviceId ?? service.id;
}

function extractServicePrice(service: ServiceRecord): number | null {
  const pricing = service.pricing;
  if (typeof pricing === "string" || typeof pricing === "number") return finiteNumber(pricing);
  if (pricing && typeof pricing === "object") return finiteNumber((pricing as { amount?: unknown }).amount);
  return null;
}

function finiteNumber(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseInvocationResponse(resp: Record<string, unknown>): InvocationResult {
  return {
    invocationId: firstString([resp["invocationId"], resp["id"], resp["invocation_id"]]) ?? "",
    status: (firstString([resp["status"]]) ?? "PENDING") as InvocationStatus,
    chargedUsdc: Number(firstPresent([resp["chargedUsdc"], resp["charged_usdc"], 0])),
    result: firstPresent([resp["result"], null]),
    error: firstPresent([resp["error"], null]) as Record<string, unknown> | null,
    receipt: firstPresent([resp["receipt"], null]) as Record<string, unknown> | null,
    quoteId: firstString([resp["quoteId"]]) ?? undefined,
    ...resp,
  };
}

function firstString(values: unknown[]): string | null {
  const found = values.find((value) => typeof value === "string" && value.length > 0);
  return (found as string | undefined) ?? null;
}

function firstPresent(values: unknown[]): unknown {
  const found = values.find((value) => value !== null && value !== undefined);
  return found === undefined ? values.at(-1) : found;
}

function clientHttpError(context: HttpErrorContext): Error | null {
  if (context.status === 401) return new AuthenticationError(`401: ${context.message}`);
  if (context.status === 402) return new InsufficientFundsError(`402: ${context.message}`);
  if (isPriceMismatchContext(context)) return priceMismatchError(context);
  return null;
}

function isPriceMismatchContext(context: HttpErrorContext): boolean {
  return context.status === 422 && detailObject(context.detail)?.["code"] === "PRICE_MISMATCH";
}

function priceMismatchError(context: HttpErrorContext): PriceMismatchError {
  const detail = detailObject(context.detail) ?? {};
  return new PriceMismatchError(
    String(detail["message"] ?? context.message),
    Number(detail["expectedPriceUsdc"] ?? 0),
    Number(detail["currentPriceUsdc"] ?? 0)
  );
}

function detailObject(detail: unknown): Record<string, unknown> | null {
  return typeof detail === "object" && detail !== null ? (detail as Record<string, unknown>) : null;
}
