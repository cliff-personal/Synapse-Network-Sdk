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
import { SynapseProvider } from "./provider";
import { AuthCredentialContext, issueCredential } from "./auth_credentials";
import { fetchJson } from "./http";
import {
  AuthProviderControlContext,
  createProviderWithdrawalIntent,
  deleteProviderSecret,
  deleteProviderService,
  getProviderEarningsSummary,
  getProviderService,
  getProviderServiceHealthHistory,
  getProviderServiceStatus,
  getProviderWithdrawalCapability,
  getRegistrationGuide,
  issueProviderSecret,
  listProviderServices,
  listProviderSecrets,
  listProviderWithdrawals,
  parseCurlToServiceManifest,
  pingProviderService,
  registerProviderService,
  updateProviderService,
} from "./auth_provider_control";

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

  /** Return a provider publishing facade scoped to this authenticated owner. */
  provider(): SynapseProvider {
    return new SynapseProvider(this);
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

  /** Clear the gateway session token and local cache. */
  async logout(): Promise<Record<string, unknown>> {
    const token = await this.getToken();
    const resp = await this._fetch<Record<string, unknown>>(`${this.gatewayUrl}/api/v1/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    this._token = null;
    this._tokenExpiresAt = 0;
    return resp;
  }

  /** Return the authenticated owner profile. */
  async getOwnerProfile(): Promise<Record<string, unknown>> {
    const token = await this.getToken();
    return this._fetch<Record<string, unknown>>(`${this.gatewayUrl}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  /** Issue a new agent credential and return its token + metadata. */
  async issueCredential(opts: IssueCredentialOptions = {}): Promise<IssueCredentialResult> {
    return issueCredential(this.credentialContext(), opts);
  }

  /** Issue a provider control-plane secret for the current owner wallet. */
  async issueProviderSecret(opts: IssueCredentialOptions = {}): Promise<IssueProviderSecretResult> {
    return issueProviderSecret(this.providerControlContext(), opts);
  }

  /** List provider control-plane secrets for the current wallet. */
  async listProviderSecrets(): Promise<ProviderSecret[]> {
    return listProviderSecrets(this.providerControlContext());
  }

  /** Delete a provider control-plane secret. */
  async deleteProviderSecret(secretId: string): Promise<Record<string, unknown>> {
    return deleteProviderSecret(this.providerControlContext(), secretId);
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

  /** Check whether a credential is still valid and usable. */
  async checkCredentialStatus(credentialId: string): Promise<Record<string, unknown>> {
    const token = await this.getToken();
    const id = this.requireValue(credentialId, "credentialId");
    return this._fetch<Record<string, unknown>>(
      `${this.gatewayUrl}/api/v1/credentials/agent/${encodeURIComponent(id)}/status`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
  }

  /** Alias for checkCredentialStatus(). */
  async getCredentialStatus(credentialId: string): Promise<Record<string, unknown>> {
    return this.checkCredentialStatus(credentialId);
  }

  /** Revoke an agent credential without deleting its audit trail. */
  async revokeCredential(credentialId: string): Promise<Record<string, unknown>> {
    const token = await this.getToken();
    const id = this.requireValue(credentialId, "credentialId");
    return this._fetch<Record<string, unknown>>(
      `${this.gatewayUrl}/api/v1/credentials/agent/${encodeURIComponent(id)}/revoke`,
      { method: "POST", headers: { Authorization: `Bearer ${token}` } }
    );
  }

  /** Rotate an agent credential and return the gateway response containing the new token. */
  async rotateCredential(credentialId: string): Promise<Record<string, unknown>> {
    const token = await this.getToken();
    const id = this.requireValue(credentialId, "credentialId");
    return this._fetch<Record<string, unknown>>(
      `${this.gatewayUrl}/api/v1/credentials/agent/${encodeURIComponent(id)}/rotate`,
      { method: "POST", headers: { Authorization: `Bearer ${token}` } }
    );
  }

  /** Delete an agent credential. Use revokeCredential for emergency shutoff. */
  async deleteCredential(credentialId: string): Promise<Record<string, unknown>> {
    const token = await this.getToken();
    const id = this.requireValue(credentialId, "credentialId");
    return this._fetch<Record<string, unknown>>(
      `${this.gatewayUrl}/api/v1/credentials/agent/${encodeURIComponent(id)}`,
      { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }
    );
  }

  /** Update spend/call/rate quota fields for an agent credential. */
  async updateCredentialQuota(
    credentialId: string,
    opts: {
      maxCalls?: number;
      rpm?: number;
      creditLimit?: number;
      resetInterval?: string;
      expiresAt?: string | number;
      expiration?: number;
    } = {}
  ): Promise<Record<string, unknown>> {
    const token = await this.getToken();
    const id = this.requireValue(credentialId, "credentialId");
    return this._fetch<Record<string, unknown>>(
      `${this.gatewayUrl}/api/v1/credentials/agent/${encodeURIComponent(id)}/quota`,
      {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify(opts),
      }
    );
  }

  /** Fetch credential lifecycle audit logs for the authenticated owner. */
  async getCredentialAuditLogs(opts: { limit?: number } = {}): Promise<Record<string, unknown>> {
    const token = await this.getToken();
    const url = this.withQuery(`${this.gatewayUrl}/api/v1/credentials/agent/audit-logs`, {
      limit: opts.limit ?? 100,
    });
    return this._fetch<Record<string, unknown>>(url, { headers: { Authorization: `Bearer ${token}` } });
  }

  /** Get balance summary for this wallet. */
  async getBalance(): Promise<BalanceSummary> {
    const token = await this.getToken();
    const resp = await this._fetch<{ balance?: BalanceSummary }>(`${this.gatewayUrl}/api/v1/balance`, {
      headers: { Authorization: `Bearer ${token}` },
    });
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
    const resp = await this._fetch<DepositIntentResult>(`${this.gatewayUrl}/api/v1/balance/deposit/intent`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Idempotency-Key": idemKey,
      },
      body: JSON.stringify({ txHash, amountUsdc }),
    });
    return resp;
  }

  /** Confirm a previously registered deposit intent. */
  async confirmDeposit(intentId: string, eventKey: string): Promise<{ status: string }> {
    const token = await this.getToken();
    return this._fetch<{ status: string }>(`${this.gatewayUrl}/api/v1/balance/deposit/intents/${intentId}/confirm`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ eventKey, confirmations: 1 }),
    });
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
        usdc === null ? { allowUnlimited: true } : { spendingLimitUsdc: usdc, allowUnlimited: false }
      ),
    });
  }

  /** Redeem a voucher into the authenticated owner balance. */
  async redeemVoucher(voucherCode: string, idempotencyKey?: string): Promise<Record<string, unknown>> {
    const token = await this.getToken();
    const code = this.requireValue(voucherCode, "voucherCode");
    return this._fetch<Record<string, unknown>>(`${this.gatewayUrl}/api/v1/balance/vouchers/redeem`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Idempotency-Key": idempotencyKey ?? `voucher-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      },
      body: JSON.stringify({ voucherCode: code }),
    });
  }

  /** Fetch owner usage logs for observability and billing review. */
  async getUsageLogs(opts: { limit?: number } = {}): Promise<Record<string, unknown>> {
    const token = await this.getToken();
    const url = this.withQuery(`${this.gatewayUrl}/api/v1/usage/logs`, { limit: opts.limit ?? 100 });
    return this._fetch<Record<string, unknown>>(url, { headers: { Authorization: `Bearer ${token}` } });
  }

  /** Fetch finance audit logs. High-impact finance actions remain explicit. */
  async getFinanceAuditLogs(opts: { limit?: number } = {}): Promise<Record<string, unknown>> {
    const token = await this.getToken();
    const url = this.withQuery(`${this.gatewayUrl}/api/v1/finance/audit-logs`, { limit: opts.limit ?? 100 });
    return this._fetch<Record<string, unknown>>(url, { headers: { Authorization: `Bearer ${token}` } });
  }

  /** Return the owner finance risk overview. */
  async getRiskOverview(): Promise<Record<string, unknown>> {
    const token = await this.getToken();
    return this._fetch<Record<string, unknown>>(`${this.gatewayUrl}/api/v1/finance/risk-overview`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  /** Register a provider service using the minimum-contract onboarding shape. */
  async registerProviderService(opts: RegisterProviderServiceOptions): Promise<RegisterProviderServiceResult> {
    return registerProviderService(this.providerControlContext(), opts);
  }

  /** List provider-owned services from the control plane. */
  async listProviderServices(): Promise<ProviderServiceRecord[]> {
    return listProviderServices(this.providerControlContext());
  }

  /** Fetch the provider registration guide from the gateway control plane. */
  async getRegistrationGuide(): Promise<Record<string, unknown>> {
    return getRegistrationGuide(this.providerControlContext());
  }

  /** Convert a curl command into a provider service manifest draft. */
  async parseCurlToServiceManifest(curlCommand: string): Promise<Record<string, unknown>> {
    return parseCurlToServiceManifest(this.providerControlContext(), curlCommand);
  }

  /** Patch a provider service registration by gateway record ID. */
  async updateProviderService(
    serviceRecordId: string,
    patch: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    return updateProviderService(this.providerControlContext(), serviceRecordId, patch);
  }

  /** Delete a provider service registration by gateway record ID. */
  async deleteProviderService(serviceRecordId: string): Promise<Record<string, unknown>> {
    return deleteProviderService(this.providerControlContext(), serviceRecordId);
  }

  /** Force a provider service health ping. */
  async pingProviderService(serviceRecordId: string): Promise<Record<string, unknown>> {
    return pingProviderService(this.providerControlContext(), serviceRecordId);
  }

  /** Fetch health history for a provider service. */
  async getProviderServiceHealthHistory(
    serviceRecordId: string,
    opts: { limitPerTarget?: number } = {}
  ): Promise<Record<string, unknown>> {
    return getProviderServiceHealthHistory(this.providerControlContext(), serviceRecordId, opts);
  }

  /** Return provider earnings summary for the authenticated owner. */
  async getProviderEarningsSummary(): Promise<Record<string, unknown>> {
    return getProviderEarningsSummary(this.providerControlContext());
  }

  /** Return whether provider withdrawals are currently available. */
  async getProviderWithdrawalCapability(): Promise<Record<string, unknown>> {
    return getProviderWithdrawalCapability(this.providerControlContext());
  }

  /** Create a provider withdrawal intent. This does not auto-submit funds on-chain. */
  async createProviderWithdrawalIntent(
    amountUsdc: number,
    opts: { idempotencyKey?: string; destinationAddress?: string } = {}
  ): Promise<Record<string, unknown>> {
    return createProviderWithdrawalIntent(this.providerControlContext(), amountUsdc, opts);
  }

  /** List provider withdrawal records. */
  async listProviderWithdrawals(opts: { limit?: number } = {}): Promise<Record<string, unknown>> {
    return listProviderWithdrawals(this.providerControlContext(), opts);
  }

  /** Return one provider-owned service by serviceId. */
  async getProviderService(serviceId: string): Promise<ProviderServiceRecord> {
    return getProviderService(this.providerControlContext(), serviceId);
  }

  /** Read lifecycle + runtime status for a provider-owned service. */
  async getProviderServiceStatus(serviceId: string): Promise<ProviderServiceStatus> {
    return getProviderServiceStatus(this.providerControlContext(), serviceId);
  }

  // ── Internal helpers ───────────────────────────────────────────────────────

  private credentialContext(): AuthCredentialContext {
    return {
      gatewayUrl: this.gatewayUrl,
      getToken: () => this.getToken(),
      fetchJson: <T>(url: string, init?: { method?: string; body?: string; headers?: Record<string, string> }) =>
        this._fetch<T>(url, init),
    };
  }

  private providerControlContext(): AuthProviderControlContext {
    return {
      gatewayUrl: this.gatewayUrl,
      walletAddress: this.walletAddress,
      getToken: () => this.getToken(),
      fetchJson: <T>(url: string, init?: { method?: string; body?: string; headers?: Record<string, string> }) =>
        this._fetch<T>(url, init),
      requireValue: (value: string, name: string) => this.requireValue(value, name),
      withQuery: (url: string, params: Record<string, string | number | boolean | null | undefined>) =>
        this.withQuery(url, params),
    };
  }

  private requireValue(value: string, name: string): string {
    const resolved = String(value ?? "").trim();
    if (!resolved) throw new Error(`${name} is required`);
    return resolved;
  }

  private withQuery(url: string, params: Record<string, string | number | boolean | null | undefined>): string {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== null && value !== undefined) search.set(key, String(value));
    }
    const query = search.toString();
    return query ? `${url}?${query}` : url;
  }

  private async _fetch<T>(
    url: string,
    init: { method?: string; body?: string; headers?: Record<string, string> } = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...Object.fromEntries(Object.entries(init.headers ?? {})),
    };
    return fetchJson<T>(url, { method: init.method, body: init.body, headers, timeoutMs: this.timeoutMs });
  }
}
