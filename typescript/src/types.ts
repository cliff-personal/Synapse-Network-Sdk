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

export interface AuthLogoutResult {
  status?: string;
  success?: boolean;
  [key: string]: unknown;
}

export interface OwnerProfile {
  profile?: Record<string, unknown>;
  ownerAddress?: string;
  walletAddress?: string;
  [key: string]: unknown;
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

export interface CredentialRevokeResult {
  status?: string;
  credentialId?: string;
  credential?: AgentCredential;
  [key: string]: unknown;
}

export interface CredentialRotateResult {
  status?: string;
  credentialId?: string;
  token?: string;
  credential?: AgentCredential;
  [key: string]: unknown;
}

export interface CredentialDeleteResult {
  status?: string;
  credentialId?: string;
  [key: string]: unknown;
}

export interface CredentialQuotaUpdateResult {
  status?: string;
  credentialId?: string;
  credential?: AgentCredential;
  [key: string]: unknown;
}

export interface CredentialStatusResult {
  status?: string;
  credentialId?: string;
  valid?: boolean;
  credentialStatus?: string;
  isExpired?: boolean;
  callsExhausted?: boolean;
  expiresAt?: number;
  callsUsed?: number;
  maxCalls?: number;
  creditLimit?: number;
  [key: string]: unknown;
}

export interface CredentialAuditLogList {
  logs?: Array<Record<string, unknown>>;
  [key: string]: unknown;
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

export interface DepositConfirmResult {
  status: string;
  intent?: {
    id?: string;
    intentId?: string;
    depositIntentId?: string;
    eventKey?: string;
    event_key?: string;
    txHash?: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface VoucherRedeemResult {
  status?: string;
  voucherCode?: string;
  [key: string]: unknown;
}

export interface UsageLogList {
  logs?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface FinanceAuditLogList {
  logs?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface RiskOverview {
  risk?: unknown;
  [key: string]: unknown;
}

// ── Services ─────────────────────────────────────────────────────────────────

export type ServiceKind = "api" | "llm";

export type PriceModel = "fixed" | "per_call" | "per_success_call" | "token_metered";

export interface FixedPricing {
  amount?: string;
  currency?: string;
}

export interface LlmPricing {
  priceModel: "token_metered";
  inputPricePer1MTokensUsdc: string;
  outputPricePer1MTokensUsdc: string;
  defaultMaxOutputTokens?: number;
  holdBufferMultiplier?: string | number;
  maxAutoHoldUsdc?: string;
}

export interface ServiceRecord {
  serviceId?: string;
  id?: string;
  agentToolName?: string;
  serviceName?: string;
  status?: string;
  serviceKind?: ServiceKind | string;
  priceModel?: PriceModel | string;
  pricing?: FixedPricing | LlmPricing | string;
  inputPricePer1MTokensUsdc?: string;
  outputPricePer1MTokensUsdc?: string;
  defaultMaxOutputTokens?: number;
  holdBufferMultiplier?: string | number;
  maxAutoHoldUsdc?: string;
  summary?: string;
  tags?: string[];
  [key: string]: unknown;
}

export interface GatewayHealthResult {
  status: string;
  version?: string;
  [key: string]: unknown;
}

export interface DiscoveryEmptyExplanation {
  query: string;
  tags: string[];
  possibleReasons: string[];
  suggestions: string[];
}

export interface TokenMeteredServiceRecord extends ServiceRecord {
  serviceKind: "llm";
  priceModel: "token_metered";
  pricing?: LlmPricing;
  inputPricePer1MTokensUsdc: string;
  outputPricePer1MTokensUsdc: string;
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
  basePriceUsdc?: string | number;
  descriptionForModel: string;
  serviceKind?: ServiceKind;
  priceModel?: PriceModel;
  inputPricePer1MTokensUsdc?: string | number;
  outputPricePer1MTokensUsdc?: string | number;
  defaultMaxOutputTokens?: number;
  holdBufferMultiplier?: string | number;
  maxAutoHoldUsdc?: string | number;
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

export interface ProviderSecretDeleteResult {
  status?: string;
  secretId?: string;
  [key: string]: unknown;
}

export interface ProviderRegistrationGuide {
  steps?: unknown[];
  requirements?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ServiceManifestDraft {
  data?: Record<string, unknown>;
  manifest?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ProviderServiceUpdateResult {
  status?: string;
  service?: ProviderServiceRecord;
  [key: string]: unknown;
}

export interface ProviderServiceDeleteResult {
  status?: string;
  serviceId?: string;
  [key: string]: unknown;
}

export interface ProviderServicePingResult {
  status?: string;
  health?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ProviderServiceHealthHistory {
  history?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface ProviderEarningsSummary {
  total?: string | number;
  [key: string]: unknown;
}

export interface ProviderWithdrawalCapability {
  available?: boolean;
  [key: string]: unknown;
}

export interface ProviderWithdrawalIntentResult {
  status?: string;
  intentId?: string;
  amountUsdc?: string | number;
  intent?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ProviderWithdrawalList {
  withdrawals?: Array<Record<string, unknown>>;
  [key: string]: unknown;
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

export interface LlmInvokeOptions {
  idempotencyKey?: string;
  responseMode?: "sync";
  requestId?: string;
  pollTimeoutMs?: number;
  pollIntervalMs?: number;
  /**
   * Optional caller-side maximum spend cap. If omitted, Gateway performs
   * automatic pre-authorization based on prompt length and max_tokens.
   */
  maxCostUsdc?: number | string;
}

export interface LlmUsage {
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  [key: string]: unknown;
}

export interface SynapseBillingMetadata {
  priceModel?: "token_metered" | string;
  holdUsdc?: string;
  chargedUsdc?: string;
  releasedUsdc?: string;
  providerRevenueUsdc?: string;
  platformFeeUsdc?: string;
  preAuthMode?: "auto" | "explicit" | string;
  [key: string]: unknown;
}

export interface InvocationResult {
  invocationId: string;
  status: InvocationStatus;
  chargedUsdc: number;
  result?: unknown;
  usage?: LlmUsage;
  synapse?: SynapseBillingMetadata;
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
