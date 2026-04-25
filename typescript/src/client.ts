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
    const pageSize = Math.max(1, opts.limit ?? 20);
    const offset = Math.max(0, opts.offset ?? 0);
    const page = Math.floor(offset / pageSize) + 1;
    try {
      const resp = await this._fetch<{ services?: ServiceRecord[]; results?: ServiceRecord[] }>(
        `${this.gatewayUrl}/api/v1/agent/discovery/search`,
        {
          method: "POST",
          body: JSON.stringify({
            query: query.trim() || undefined,
            tags: opts.tags ?? [],
            page,
            pageSize,
            sort: opts.sort ?? "best_match",
          }),
        }
      );
      return resp.services ?? resp.results ?? (Array.isArray(resp) ? resp : []);
    } catch (err) {
      throw new DiscoveryError(String(err instanceof Error ? err.message : err));
    }
  }

  /** Check the public gateway health endpoint without consuming agent budget. */
  async checkGatewayHealth(): Promise<Record<string, unknown>> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const resp = await fetch(`${this.gatewayUrl}/health`, { signal: controller.signal });
      const text = await resp.text();
      const data = text ? JSON.parse(text) as Record<string, unknown> : {};
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
    const idempotencyKey = opts.idempotencyKey ?? uuidv4();
    const requestHeaders: Record<string, string> = {};
    if (opts.requestId) requestHeaders["X-Request-Id"] = opts.requestId;

    let resp: Record<string, unknown>;
    try {
      resp = await this._fetch<Record<string, unknown>>(
        `${this.gatewayUrl}/api/v1/agent/invoke`,
        {
          method: "POST",
          extraHeaders: requestHeaders,
          body: JSON.stringify({
            serviceId,
            idempotencyKey,
            costUsdc: opts.costUsdc,
            payload: { body: payload },
            responseMode: opts.responseMode ?? "sync",
          }),
        }
      );
    } catch (err) {
      if (
        err instanceof AuthenticationError ||
        err instanceof InsufficientFundsError ||
        err instanceof PriceMismatchError
      ) throw err;
      throw new InvokeError(String(err instanceof Error ? err.message : err));
    }

    const result = this._parseInvocationResponse(resp);
    if (TERMINAL_STATUSES.has(result.status)) return result;
    if (opts.pollTimeoutMs === 0) return result;
    return this.waitForInvocation(result.invocationId, opts);
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

      let livePrice = err.currentPriceUsdc;
      const services = await this.search(opts.query ?? serviceId, { limit: 10, tags: opts.tags });
      const matched = services.find((service) => (service.serviceId ?? service.id) === serviceId);
      const discoveredPrice = matched ? this.extractServicePrice(matched) : null;
      if (discoveredPrice != null) livePrice = discoveredPrice;
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

  private extractServicePrice(service: ServiceRecord): number | null {
    const pricing = service.pricing;
    if (typeof pricing === "string" || typeof pricing === "number") {
      const parsed = Number(pricing);
      return Number.isFinite(parsed) ? parsed : null;
    }
    if (pricing && typeof pricing === "object") {
      const parsed = Number((pricing as { amount?: unknown }).amount);
      return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
  }

  private _parseInvocationResponse(resp: Record<string, unknown>): InvocationResult {
    const invocationId =
      (resp["invocationId"] as string) ||
      (resp["id"] as string) ||
      (resp["invocation_id"] as string) ||
      "";
    const status =
      ((resp["status"] as string) || "PENDING") as InvocationStatus;
    const chargedUsdc = Number(resp["chargedUsdc"] ?? resp["charged_usdc"] ?? 0);

    return {
      invocationId,
      status,
      chargedUsdc,
      result: resp["result"] ?? null,
      error: (resp["error"] as Record<string, unknown>) ?? null,
      receipt: (resp["receipt"] as Record<string, unknown>) ?? null,
      quoteId: (resp["quoteId"] as string) ?? undefined,
      ...resp,
    };
  }

  private async _fetch<T>(
    url: string,
    init: {
      method?: string;
      body?: string;
      extraHeaders?: Record<string, string>;
    } = {}
  ): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Credential": this.credential,
      ...(init.extraHeaders ?? {}),
    };

    try {
      const resp = await fetch(url, {
        method: init.method ?? "GET",
        body: init.body,
        headers,
        signal: controller.signal,
      });
      const text = await resp.text();
      let data: unknown;
      try { data = JSON.parse(text); } catch { data = { raw: text }; }

      if (!resp.ok) {
        const d = data as Record<string, unknown>;
        const detail = d?.["detail"];
        const msg = typeof detail === "string" ? detail
          : typeof detail === "object" && detail !== null ? JSON.stringify(detail)
          : text;
        const detailObj = typeof detail === "object" && detail !== null ? detail as Record<string, unknown> : null;

        if (resp.status === 401) throw new AuthenticationError(`401: ${msg}`);
        if (resp.status === 402) throw new InsufficientFundsError(`402: ${msg}`);
        if (resp.status === 422 && detailObj?.["code"] === "PRICE_MISMATCH") {
          throw new PriceMismatchError(
            String(detailObj["message"] ?? msg),
            Number(detailObj["expectedPriceUsdc"] ?? 0),
            Number(detailObj["currentPriceUsdc"] ?? 0)
          );
        }
        throw new Error(`HTTP ${resp.status}: ${msg}`);
      }
      return data as T;
    } finally {
      clearTimeout(timer);
    }
  }
}

function _sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
