/**
 * SynapseAuth — Wallet-based authentication + credential management.
 *
 * Requires `ethers` (v6) as a peer dependency for EIP-191 signing.
 * Alternatively pass a custom `signer` function if you bring your own stack.
 */
import {
  SynapseAuthOptions,
  ChallengeResponse,
  TokenResponse,
  IssueCredentialOptions,
  IssueCredentialResult,
  AgentCredential,
  BalanceSummary,
  DepositIntentResult,
  ProviderSecret,
  IssueProviderSecretResult,
  RegisterProviderServiceOptions,
  RegisterProviderServiceResult,
  ProviderServiceRecord,
  ProviderServiceStatus,
} from "./types";
import { AuthenticationError } from "./errors";
import { resolveGatewayUrl } from "./config";

type SignerFn = (message: string) => Promise<string>;

export interface SynapseAuthConstructorOptions extends SynapseAuthOptions {
  /** EIP-191 signer function. Called with the challenge string, returns hex signature. */
  signer: SignerFn;
  /** Wallet address (lowercase hex). */
  walletAddress: string;
}

export class SynapseAuth {
  private readonly gatewayUrl: string;
  private readonly timeoutMs: number;
  private readonly signer: SignerFn;
  private readonly walletAddress: string;
  private _token: string | null = null;
  private _tokenExpiresAt: number = 0;

  constructor(opts: SynapseAuthConstructorOptions) {
    this.gatewayUrl = resolveGatewayUrl({ environment: opts.environment, gatewayUrl: opts.gatewayUrl });
    this.timeoutMs = opts.timeoutMs ?? 30_000;
    this.signer = opts.signer;
    this.walletAddress = opts.walletAddress.toLowerCase();
  }

  private defaultServiceId(serviceName: string): string {
    const normalized = serviceName
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "_");
    const sanitized = normalized
      .replace(/[^a-z0-9_-]+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_+|_+$/g, "");
    return sanitized || `service_${Date.now().toString(36)}`;
  }

  /**
   * Create a SynapseAuth instance from an ethers.js Wallet (v6 or v5).
   */
  static fromWallet(
    wallet: { signMessage: (msg: string) => Promise<string>; address: string },
    opts: SynapseAuthOptions = {}
  ): SynapseAuth {
    return new SynapseAuth({
      ...opts,
      signer: (msg) => wallet.signMessage(msg),
      walletAddress: wallet.address,
    });
  }

  /** Perform challenge → sign → verify and return a JWT. Caches for TTL. */
  async authenticate(): Promise<string> {
    const now = Date.now();
    if (this._token && now < this._tokenExpiresAt - 30_000) {
      return this._token;
    }

    const url = `${this.gatewayUrl}/api/v1/auth/challenge?address=${encodeURIComponent(this.walletAddress)}`;
    const challengeResp = await this._fetch<ChallengeResponse>(url, { method: "GET" });
    if (!challengeResp.success) {
      throw new AuthenticationError(`Challenge failed: ${JSON.stringify(challengeResp)}`);
    }

    const message = challengeResp.challenge;
    const signature = await this.signer(message);

    const tokenResp = await this._fetch<TokenResponse>(`${this.gatewayUrl}/api/v1/auth/verify`, {
      method: "POST",
      body: JSON.stringify({
        wallet_address: this.walletAddress,
        message,
        signature,
      }),
    });
    if (!tokenResp.success) {
      throw new AuthenticationError(`Auth verify failed: ${JSON.stringify(tokenResp)}`);
    }

    this._token = tokenResp.access_token;
    this._tokenExpiresAt = now + tokenResp.expires_in * 1_000;
    return this._token;
  }

  /** Returns the current JWT (auto-authenticates if needed). */
  async getToken(): Promise<string> {
    return this.authenticate();
  }

  /** Issue a new agent credential and return its token + metadata. */
  async issueCredential(opts: IssueCredentialOptions = {}): Promise<IssueCredentialResult> {
    const token = await this.getToken();
    const body: Record<string, unknown> = {};
    if (opts.name) body["name"] = opts.name;
    if (opts.maxCalls != null) body["maxCalls"] = opts.maxCalls;
    if (opts.creditLimit != null) body["creditLimit"] = opts.creditLimit;
    if (opts.resetInterval != null) body["resetInterval"] = opts.resetInterval;
    if (opts.rpm != null) body["rpm"] = opts.rpm;
    if (opts.expiresInSec != null) body["expiresInSec"] = opts.expiresInSec;

    const resp = await this._fetch<Record<string, unknown>>(
      `${this.gatewayUrl}/api/v1/credentials/agent/issue`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      }
    );

    const credToken =
      (resp["token"] as string) ||
      ((resp["credential"] as Record<string, unknown>)?.["token"] as string) ||
      (resp["credential_token"] as string);
    const credId =
      (resp["credential_id"] as string) ||
      (resp["id"] as string) ||
      ((resp["credential"] as Record<string, unknown>)?.["id"] as string) ||
      ((resp["credential"] as Record<string, unknown>)?.["credential_id"] as string);

    if (!credToken) throw new AuthenticationError(`Credential token missing: ${JSON.stringify(resp)}`);
    if (!credId) throw new AuthenticationError(`Credential ID missing: ${JSON.stringify(resp)}`);

    const credential: AgentCredential = {
      id: credId,
      credential_id: credId,
      token: credToken,
      name: opts.name,
      status: "active",
      ...((resp["credential"] as Record<string, unknown>) ?? {}),
    };

    return { credential, token: credToken };
  }

  /** Issue a provider control-plane secret for the current owner wallet. */
  async issueProviderSecret(opts: IssueCredentialOptions = {}): Promise<IssueProviderSecretResult> {
    const token = await this.getToken();
    const body: Record<string, unknown> = {};
    if (opts.name) body["name"] = opts.name;
    if (opts.maxCalls != null) body["maxCalls"] = opts.maxCalls;
    if (opts.creditLimit != null) body["creditLimit"] = opts.creditLimit;
    if (opts.resetInterval != null) body["resetInterval"] = opts.resetInterval;
    if (opts.rpm != null) body["rpm"] = opts.rpm;
    if (opts.expiresInSec != null) body["expiresInSec"] = opts.expiresInSec;

    const resp = await this._fetch<Record<string, unknown>>(
      `${this.gatewayUrl}/api/v1/secrets/provider/issue`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      }
    );
    const secret = (resp["secret"] as ProviderSecret | undefined) ?? undefined;
    if (!secret?.id) {
      throw new AuthenticationError(`Provider secret payload missing: ${JSON.stringify(resp)}`);
    }
    return { status: resp["status"] as string | undefined, secret };
  }

  /** List provider control-plane secrets for the current wallet. */
  async listProviderSecrets(): Promise<ProviderSecret[]> {
    const token = await this.getToken();
    const resp = await this._fetch<{ secrets?: ProviderSecret[] }>(
      `${this.gatewayUrl}/api/v1/secrets/provider/list`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return resp.secrets ?? [];
  }

  /** List all agent credentials for this wallet. */
  async listCredentials(): Promise<AgentCredential[]> {
    const token = await this.getToken();
    const resp = await this._fetch<{ credentials?: AgentCredential[] }>(
      `${this.gatewayUrl}/api/v1/credentials/agent/list`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return resp.credentials ?? [];
  }

  /** Get balance summary for this wallet. */
  async getBalance(): Promise<BalanceSummary> {
    const token = await this.getToken();
    const resp = await this._fetch<{ balance?: BalanceSummary }>(
      `${this.gatewayUrl}/api/v1/balance`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return resp.balance ?? ({} as BalanceSummary);
  }

  /**
   * Register a deposit intent with the gateway after an on-chain deposit tx.
   * Requires X-Idempotency-Key header (auto-generated if not provided).
   */
  async registerDepositIntent(
    txHash: string,
    amountUsdc: number,
    idempotencyKey?: string
  ): Promise<DepositIntentResult> {
    const token = await this.getToken();
    const idemKey = idempotencyKey ?? `deposit-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const resp = await this._fetch<DepositIntentResult>(
      `${this.gatewayUrl}/api/v1/balance/deposit/intent`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Idempotency-Key": idemKey,
        },
        body: JSON.stringify({ txHash, amountUsdc }),
      }
    );
    return resp;
  }

  /** Confirm a previously registered deposit intent. */
  async confirmDeposit(intentId: string, eventKey: string): Promise<{ status: string }> {
    const token = await this.getToken();
    return this._fetch<{ status: string }>(
      `${this.gatewayUrl}/api/v1/balance/deposit/intents/${intentId}/confirm`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ eventKey, confirmations: 1 }),
      }
    );
  }

  /**
   * Set the owner-level monthly billing cap.
   * Pass `null` (or omit) to remove the cap (unlimited until balance = 0).
   */
  async setSpendingLimit(usdc: number | null): Promise<void> {
    const token = await this.getToken();
    await this._fetch(`${this.gatewayUrl}/api/v1/balance/spending-limit`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(
        usdc === null
          ? { allowUnlimited: true }
          : { spendingLimitUsdc: usdc, allowUnlimited: false }
      ),
    });
  }

  /** Register a provider service using the minimum-contract onboarding shape. */
  async registerProviderService(
    opts: RegisterProviderServiceOptions
  ): Promise<RegisterProviderServiceResult> {
    const token = await this.getToken();
    const serviceName = opts.serviceName?.trim();
    const endpointUrl = opts.endpointUrl?.trim();
    const description = opts.descriptionForModel?.trim();
    if (!serviceName) throw new Error("serviceName is required");
    if (!endpointUrl) throw new Error("endpointUrl is required");
    if (!description) throw new Error("descriptionForModel is required");

    const serviceId = opts.serviceId?.trim() || this.defaultServiceId(serviceName);
    const body = {
      serviceId,
      agentToolName: serviceId,
      serviceName,
      role: "Provider",
      status: opts.status ?? "active",
      isActive: opts.isActive ?? true,
      pricing: {
        amount: String(opts.basePriceUsdc),
        currency: "USDC",
      },
      summary: description,
      tags: opts.tags ?? [],
      auth: { type: "gateway_signed" },
      invoke: {
        method: opts.endpointMethod ?? "POST",
        targets: [{ url: endpointUrl }],
        timeoutMs: opts.requestTimeoutMs ?? 15_000,
        request: {
          body: opts.inputSchema ?? { type: "object", properties: {}, required: [] },
        },
        response: {
          body: opts.outputSchema ?? { type: "object", properties: {} },
        },
      },
      healthCheck: {
        path: opts.healthPath ?? "/health",
        method: opts.healthMethod ?? "GET",
        timeoutMs: opts.healthTimeoutMs ?? 3_000,
        successCodes: [200],
        healthyThreshold: 1,
        unhealthyThreshold: 3,
      },
      providerProfile: {
        displayName: opts.providerDisplayName?.trim() || serviceName,
      },
      payoutAccount: {
        payoutAddress: opts.payoutAddress?.trim() || this.walletAddress,
        chainId: opts.chainId ?? 31337,
        settlementCurrency: opts.settlementCurrency ?? "USDC",
      },
      governance: {
        termsAccepted: true,
        riskAcknowledged: true,
        note: opts.governanceNote ?? null,
      },
    };

    const resp = await this._fetch<Record<string, unknown>>(
      `${this.gatewayUrl}/api/v1/services`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      }
    );

    const service =
      (resp["service"] as ProviderServiceRecord | undefined) ??
      ({ serviceId } as ProviderServiceRecord);
    const responseServiceId =
      (resp["serviceId"] as string | undefined) ??
      service.serviceId ??
      service.id ??
      serviceId;
    return {
      status: resp["status"] as string | undefined,
      serviceId: responseServiceId,
      service,
    };
  }

  /** List provider-owned services from the control plane. */
  async listProviderServices(): Promise<ProviderServiceRecord[]> {
    const token = await this.getToken();
    const resp = await this._fetch<{ services?: ProviderServiceRecord[] }>(
      `${this.gatewayUrl}/api/v1/services`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return resp.services ?? [];
  }

  /** Return one provider-owned service by serviceId. */
  async getProviderService(serviceId: string): Promise<ProviderServiceRecord> {
    const resolvedServiceId = serviceId?.trim();
    if (!resolvedServiceId) throw new Error("serviceId is required");
    const services = await this.listProviderServices();
    const found = services.find((service) => service.serviceId === resolvedServiceId);
    if (!found) {
      throw new AuthenticationError(`Provider service not found: ${resolvedServiceId}`);
    }
    return found;
  }

  /** Read lifecycle + runtime status for a provider-owned service. */
  async getProviderServiceStatus(serviceId: string): Promise<ProviderServiceStatus> {
    const service = await this.getProviderService(serviceId);
    return {
      serviceId: service.serviceId ?? service.id ?? serviceId,
      lifecycleStatus: service.status ?? "unknown",
      runtimeAvailable: Boolean(service.runtimeAvailable),
      health: (service.health ?? {}) as ProviderServiceStatus["health"],
    };
  }

  // ── Internal helpers ───────────────────────────────────────────────────────

  private async _fetch<T>(url: string, init: { method?: string; body?: string; headers?: Record<string, string> } = {}): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...Object.fromEntries(Object.entries(init.headers ?? {})),
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
        const detail = (data as Record<string, unknown>)?.["detail"];
        const msg = typeof detail === "string" ? detail : typeof detail === "object" && detail !== null
          ? JSON.stringify(detail) : text;
        throw new Error(`HTTP ${resp.status}: ${msg}`);
      }
      return data as T;
    } finally {
      clearTimeout(timer);
    }
  }
}
