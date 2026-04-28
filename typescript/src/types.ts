// ── Auth ────────────────────────────────────────────────────────────────────

export type SynapseEnvironment = "local" | "staging" | "prod";

export interface SynapseAuthOptions {
  /** Gateway environment preset. Default: staging public preview. */
  environment?: SynapseEnvironment;
  /** Gateway base URL. Overrides environment when provided. */
  gatewayUrl?: string;
  /** Timeout per request in milliseconds. Default: 30000 */
  timeoutMs?: number;
}

export interface ChallengeResponse {
  success: boolean;
  challenge: string;
  domain: string;
}

export interface TokenResponse {
  success: boolean;
  access_token: string;
  token_type: string;
  expires_in: number;
}

// ── Credentials ─────────────────────────────────────────────────────────────

export interface IssueCredentialOptions {
  name?: string;
  maxCalls?: number;
  /** Per-window USDC budget. Window size is controlled by resetInterval (default: "daily"). */
  creditLimit?: number;
  /** Budget reset cadence: "hourly" | "daily" | "weekly" | "monthly" | "never" */
  resetInterval?: "hourly" | "daily" | "weekly" | "monthly" | "never";
  rpm?: number;
  expiresInSec?: number;
}

export interface AgentCredential {
  id: string;
  credential_id: string;
  token: string;
  name?: string;
  maxCalls?: number;
  rpm?: number;
  creditLimit?: number;
  status: string;
  createdAt?: string | number;
}

export interface IssueCredentialResult {
  credential: AgentCredential;
  /** The agent token used as X-Credential header value */
  token: string;
}

export interface ProviderSecret {
  id: string;
  name?: string;
  ownerAddress?: string;
  secretKey?: string;
  maskedKey?: string;
  status?: string;
  rpm?: number;
  creditLimit?: number;
  resetInterval?: string;
  expiration?: number;
  createdAt?: string | number;
  updatedAt?: string | number;
  revokedAt?: string | number | null;
  [key: string]: unknown;
}

export interface IssueProviderSecretResult {
  status?: string;
  secret: ProviderSecret;
}

// ── Balance ──────────────────────────────────────────────────────────────────

export interface BalanceSummary {
  ownerBalance: string | number;
  consumerAvailableBalance: string | number;
  providerReceivable: string | number;
  platformFeeAccrued: string | number;
  [key: string]: unknown;
}

// ── Deposit ──────────────────────────────────────────────────────────────────

export interface DepositIntentResult {
  status: string;
  tx_hash: string;
  intent: {
    id?: string;
    intentId?: string;
    depositIntentId?: string;
    eventKey?: string;
    event_key?: string;
    txHash?: string;
    [key: string]: unknown;
  };
}

// ── Services ─────────────────────────────────────────────────────────────────

export interface ServiceRecord {
  serviceId?: string;
  id?: string;
  agentToolName?: string;
  serviceName?: string;
  status?: string;
  pricing?: { amount?: string; currency?: string } | string;
  summary?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface ProviderProfileRecord {
  displayName: string;
}

export interface ProviderPayoutAccountRecord {
  payoutAddress: string;
  chainId: number;
  settlementCurrency: string;
  status?: string;
}

export interface ProviderGovernanceRecord {
  termsAccepted: boolean;
  riskAcknowledged: boolean;
  note?: string | null;
}

export interface ServiceHealthRecord {
  overallStatus?: string;
  healthyTargets?: number;
  totalTargets?: number;
  lastCheckedAt?: number;
  runtimeAvailable?: boolean;
  [key: string]: unknown;
}

export interface ProviderServiceRecord extends ServiceRecord {
  ownerAddress?: string;
  isActive?: boolean;
  auth?: Record<string, unknown>;
  providerProfile?: ProviderProfileRecord;
  payoutAccount?: ProviderPayoutAccountRecord;
  governance?: ProviderGovernanceRecord;
  health?: ServiceHealthRecord;
  runtimeAvailable?: boolean;
  invoke?: Record<string, unknown>;
  createdAt?: string | number;
  updatedAt?: string | number;
}

export interface RegisterProviderServiceOptions {
  serviceName: string;
  endpointUrl: string;
  basePriceUsdc: string | number;
  descriptionForModel: string;
  serviceId?: string;
  providerDisplayName?: string;
  payoutAddress?: string;
  chainId?: number;
  settlementCurrency?: string;
  tags?: string[];
  status?: string;
  isActive?: boolean;
  inputSchema?: Record<string, unknown>;
  outputSchema?: Record<string, unknown>;
  endpointMethod?: "POST" | "GET" | "PUT" | "PATCH" | "DELETE";
  healthPath?: string;
  healthMethod?: "GET" | "POST" | "HEAD";
  healthTimeoutMs?: number;
  requestTimeoutMs?: number;
  governanceNote?: string;
}

export interface RegisterProviderServiceResult {
  status?: string;
  serviceId: string;
  service: ProviderServiceRecord;
}

export interface ProviderServiceStatus {
  serviceId: string;
  lifecycleStatus: string;
  runtimeAvailable: boolean;
  health: ServiceHealthRecord;
}

export interface DiscoverOptions {
  limit?: number;
  offset?: number;
  tags?: string[];
  sort?: "best_match" | "lowest_price" | "fastest" | "highest_reliability";
}

// ── Invocation ───────────────────────────────────────────────────────────────

export type InvocationStatus = "PENDING" | "PROCESSING" | "SUCCEEDED" | "SETTLED" | "FAILED_RETRYABLE" | "FAILED_FINAL";

export const TERMINAL_STATUSES = new Set<InvocationStatus>([
  "SUCCEEDED",
  "SETTLED",
  "FAILED_RETRYABLE",
  "FAILED_FINAL",
]);

export interface InvokeOptions {
  idempotencyKey?: string;
  responseMode?: "sync" | "async" | "stream";
  requestId?: string;
  pollTimeoutMs?: number;
  pollIntervalMs?: number;
  /**
   * The service price the agent saw during discovery (from ServiceRecord.pricing).
   * Pass this value from discover() results to enable price-assertion invoke.
   * Gateway returns 422 PRICE_MISMATCH if the live price has changed.
   */
  costUsdc: number;
}

export interface InvocationResult {
  invocationId: string;
  status: InvocationStatus;
  chargedUsdc: number;
  result?: unknown;
  error?: { message?: string; code?: string } | null;
  receipt?: Record<string, unknown> | null;
  quoteId?: string;
  [key: string]: unknown;
}

// ── Client constructor ────────────────────────────────────────────────────────

export interface SynapseClientOptions {
  /** Agent credential token (X-Credential header). Required. */
  credential: string;
  /** Gateway environment preset. Default: staging public preview. */
  environment?: SynapseEnvironment;
  /** Gateway base URL. Overrides environment when provided. */
  gatewayUrl?: string;
  /** Timeout per request in ms. Default: 30000 */
  timeoutMs?: number;
}
