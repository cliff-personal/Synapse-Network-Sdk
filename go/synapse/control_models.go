package synapse

type ChallengeResponse struct {
	Success   bool   `json:"success,omitempty"`
	Challenge string `json:"challenge,omitempty"`
	Domain    string `json:"domain,omitempty"`
}

type TokenResponse struct {
	Success     bool   `json:"success,omitempty"`
	AccessToken string `json:"access_token,omitempty"`
	TokenType   string `json:"token_type,omitempty"`
	ExpiresIn   int    `json:"expires_in,omitempty"`
}

type AuthLogoutResult struct {
	Status  string `json:"status,omitempty"`
	Success bool   `json:"success,omitempty"`
}

type OwnerProfile struct {
	OwnerAddress  string         `json:"ownerAddress,omitempty"`
	WalletAddress string         `json:"walletAddress,omitempty"`
	Profile       map[string]any `json:"profile,omitempty"`
}

type CredentialOptions struct {
	Name          string
	MaxCalls      int
	CreditLimit   string
	ResetInterval string
	RPM           int
	ExpiresInSec  int
	Expiration    int
}

type CredentialQuotaOptions struct {
	MaxCalls      int
	RPM           int
	CreditLimit   string
	ResetInterval string
	ExpiresAt     string
	Expiration    int
}

type AgentCredential struct {
	ID            string `json:"id,omitempty"`
	CredentialID  string `json:"credential_id,omitempty"`
	Token         string `json:"token,omitempty"`
	Name          string `json:"name,omitempty"`
	MaxCalls      int    `json:"maxCalls,omitempty"`
	RPM           int    `json:"rpm,omitempty"`
	CreditLimit   string `json:"creditLimit,omitempty"`
	ResetInterval string `json:"resetInterval,omitempty"`
	ExpiresAt     any    `json:"expiresAt,omitempty"`
	Status        string `json:"status,omitempty"`
	CreatedAt     any    `json:"createdAt,omitempty"`
}

type IssueCredentialResult struct {
	Credential AgentCredential `json:"credential"`
	Token      string          `json:"token,omitempty"`
}

type CredentialStatusResult struct {
	Status           string `json:"status,omitempty"`
	CredentialID     string `json:"credentialId,omitempty"`
	Valid            bool   `json:"valid,omitempty"`
	CredentialStatus string `json:"credentialStatus,omitempty"`
	IsExpired        bool   `json:"isExpired,omitempty"`
	CallsExhausted   bool   `json:"callsExhausted,omitempty"`
}

type CredentialRevokeResult struct {
	Status       string          `json:"status,omitempty"`
	CredentialID string          `json:"credentialId,omitempty"`
	Credential   AgentCredential `json:"credential,omitempty"`
}

type CredentialRotateResult struct {
	Status       string          `json:"status,omitempty"`
	CredentialID string          `json:"credentialId,omitempty"`
	Token        string          `json:"token,omitempty"`
	Credential   AgentCredential `json:"credential,omitempty"`
}

type CredentialDeleteResult struct {
	Status       string `json:"status,omitempty"`
	CredentialID string `json:"credentialId,omitempty"`
}

type CredentialQuotaUpdateResult struct {
	Status       string          `json:"status,omitempty"`
	CredentialID string          `json:"credentialId,omitempty"`
	Credential   AgentCredential `json:"credential,omitempty"`
}

type CredentialAuditLogList struct {
	Logs []map[string]any `json:"logs,omitempty"`
}

type BalanceSummary struct {
	OwnerBalance             any `json:"ownerBalance,omitempty"`
	ConsumerAvailableBalance any `json:"consumerAvailableBalance,omitempty"`
	ProviderReceivable       any `json:"providerReceivable,omitempty"`
	PlatformFeeAccrued       any `json:"platformFeeAccrued,omitempty"`
}

type DepositIntentResult struct {
	Status string              `json:"status,omitempty"`
	TxHash string              `json:"tx_hash,omitempty"`
	Intent DepositIntentRecord `json:"intent,omitempty"`
}

type DepositConfirmResult struct {
	Status string              `json:"status,omitempty"`
	Intent DepositIntentRecord `json:"intent,omitempty"`
}

type DepositIntentRecord struct {
	ID              string `json:"id,omitempty"`
	IntentID        string `json:"intentId,omitempty"`
	DepositIntentID string `json:"depositIntentId,omitempty"`
	EventKey        string `json:"eventKey,omitempty"`
	TxHash          string `json:"txHash,omitempty"`
}

type VoucherRedeemResult struct {
	Status      string `json:"status,omitempty"`
	VoucherCode string `json:"voucherCode,omitempty"`
}

type UsageLogList struct {
	Logs []map[string]any `json:"logs,omitempty"`
}

type FinanceAuditLogList struct {
	Logs []map[string]any `json:"logs,omitempty"`
}

type RiskOverview struct {
	Risk map[string]any `json:"risk,omitempty"`
}

type ProviderSecret struct {
	ID            string `json:"id,omitempty"`
	Name          string `json:"name,omitempty"`
	OwnerAddress  string `json:"ownerAddress,omitempty"`
	SecretKey     string `json:"secretKey,omitempty"`
	MaskedKey     string `json:"maskedKey,omitempty"`
	Status        string `json:"status,omitempty"`
	RPM           int    `json:"rpm,omitempty"`
	CreditLimit   string `json:"creditLimit,omitempty"`
	ResetInterval string `json:"resetInterval,omitempty"`
	Expiration    int    `json:"expiration,omitempty"`
}

type IssueProviderSecretResult struct {
	Status string         `json:"status,omitempty"`
	Secret ProviderSecret `json:"secret"`
}

type ProviderSecretDeleteResult struct {
	Status   string `json:"status,omitempty"`
	SecretID string `json:"secretId,omitempty"`
}

type RegisterProviderServiceOptions struct {
	ServiceName                string
	EndpointURL                string
	BasePriceUSDC              string
	DescriptionForModel        string
	ServiceKind                string
	PriceModel                 string
	InputPricePer1MTokensUSDC  string
	OutputPricePer1MTokensUSDC string
	DefaultMaxOutputTokens     int
	HoldBufferMultiplier       string
	MaxAutoHoldUSDC            string
	ServiceID                  string
	ProviderDisplayName        string
	PayoutAddress              string
	ChainID                    int
	SettlementCurrency         string
	Tags                       []string
	Status                     string
	IsActive                   *bool
	InputSchema                map[string]any
	OutputSchema               map[string]any
	EndpointMethod             string
	HealthPath                 string
	HealthMethod               string
	HealthTimeoutMS            int
	RequestTimeoutMS           int
	GovernanceNote             string
}

type RegisterProviderServiceResult struct {
	Status    string                `json:"status,omitempty"`
	ServiceID string                `json:"serviceId,omitempty"`
	Service   ProviderServiceRecord `json:"service"`
}

type ProviderServiceRecord struct {
	ServiceRecord
	OwnerAddress     string         `json:"ownerAddress,omitempty"`
	IsActive         bool           `json:"isActive,omitempty"`
	Auth             map[string]any `json:"auth,omitempty"`
	RuntimeAvailable bool           `json:"runtimeAvailable,omitempty"`
	Health           map[string]any `json:"health,omitempty"`
	Invoke           map[string]any `json:"invoke,omitempty"`
}

type ProviderServiceStatus struct {
	ServiceID        string         `json:"serviceId,omitempty"`
	LifecycleStatus  string         `json:"lifecycleStatus,omitempty"`
	RuntimeAvailable bool           `json:"runtimeAvailable,omitempty"`
	Health           map[string]any `json:"health,omitempty"`
}

type ProviderRegistrationGuide struct {
	Steps        []any          `json:"steps,omitempty"`
	Requirements map[string]any `json:"requirements,omitempty"`
}

type ServiceManifestDraft struct {
	Data     map[string]any `json:"data,omitempty"`
	Manifest map[string]any `json:"manifest,omitempty"`
}

type ProviderServiceUpdateResult struct {
	Status  string                `json:"status,omitempty"`
	Service ProviderServiceRecord `json:"service,omitempty"`
}

type ProviderServiceDeleteResult struct {
	Status    string `json:"status,omitempty"`
	ServiceID string `json:"serviceId,omitempty"`
}

type ProviderServicePingResult struct {
	Status string         `json:"status,omitempty"`
	Health map[string]any `json:"health,omitempty"`
}

type ProviderServiceHealthHistory struct {
	History []map[string]any `json:"history,omitempty"`
}

type ProviderEarningsSummary struct {
	Total any `json:"total,omitempty"`
}

type ProviderWithdrawalCapability struct {
	Available bool `json:"available,omitempty"`
}

type ProviderWithdrawalIntentResult struct {
	Status     string         `json:"status,omitempty"`
	IntentID   string         `json:"intentId,omitempty"`
	AmountUSDC any            `json:"amountUsdc,omitempty"`
	Intent     map[string]any `json:"intent,omitempty"`
}

type ProviderWithdrawalList struct {
	Withdrawals []map[string]any `json:"withdrawals,omitempty"`
}
