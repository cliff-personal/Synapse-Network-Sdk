package synapse

import (
	"bytes"
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/decred/dcrd/dcrec/secp256k1/v4"
	secpEcdsa "github.com/decred/dcrd/dcrec/secp256k1/v4/ecdsa"
	"golang.org/x/crypto/sha3"
)

type SignerFunc func(message string) (string, error)

type Auth struct {
	walletAddress  string
	gatewayURL     string
	timeout        time.Duration
	httpClient     *http.Client
	signer         SignerFunc
	token          string
	tokenExpiresAt time.Time
}

type AuthOptions struct {
	WalletAddress string
	Signer        SignerFunc
	Environment   string
	GatewayURL    string
	Timeout       time.Duration
	HTTPClient    *http.Client
}

func NewAuth(opts AuthOptions) (*Auth, error) {
	address := strings.ToLower(strings.TrimSpace(opts.WalletAddress))
	if address == "" {
		return nil, errors.New("walletAddress is required")
	}
	if opts.Signer == nil {
		return nil, errors.New("signer is required")
	}
	gatewayURL, err := ResolveGatewayURL(opts.Environment, opts.GatewayURL)
	if err != nil {
		return nil, err
	}
	timeout := opts.Timeout
	if timeout == 0 {
		timeout = 30 * time.Second
	}
	client := opts.HTTPClient
	if client == nil {
		client = &http.Client{Timeout: timeout}
	}
	return &Auth{walletAddress: address, gatewayURL: gatewayURL, timeout: timeout, httpClient: client, signer: opts.Signer}, nil
}

func NewAuthFromPrivateKey(privateKey string, opts AuthOptions) (*Auth, error) {
	raw, err := decodeHex(privateKey)
	if err != nil {
		return nil, err
	}
	key := secp256k1.PrivKeyFromBytes(raw)
	opts.WalletAddress = ethereumAddress(key.PubKey().SerializeUncompressed())
	opts.Signer = privateKeySigner(key)
	return NewAuth(opts)
}

func privateKeySigner(key *secp256k1.PrivateKey) SignerFunc {
	return func(message string) (string, error) {
		signature := secpEcdsa.SignCompact(key, ethereumMessageHash(message), false)
		// SignCompact returns header || R || S. Ethereum expects R || S || V.
		return "0x" + encodeHex(append(signature[1:], signature[0])), nil
	}
}

func ethereumMessageHash(message string) []byte {
	prefix := fmt.Sprintf("\x19Ethereum Signed Message:\n%d", len(message))
	hash := sha3.NewLegacyKeccak256()
	_, _ = hash.Write([]byte(prefix))
	_, _ = hash.Write([]byte(message))
	return hash.Sum(nil)
}

func ethereumAddress(uncompressedPubkey []byte) string {
	hash := sha3.NewLegacyKeccak256()
	_, _ = hash.Write(uncompressedPubkey[1:])
	sum := hash.Sum(nil)
	return "0x" + encodeHex(sum[len(sum)-20:])
}

func decodeHex(value string) ([]byte, error) {
	decoded, err := hex.DecodeString(strings.TrimPrefix(strings.TrimSpace(value), "0x"))
	if err != nil {
		return nil, err
	}
	return decoded, nil
}

func encodeHex(value []byte) string {
	return hex.EncodeToString(value)
}

func (a *Auth) Provider() *Provider {
	return &Provider{auth: a}
}

func (a *Auth) Authenticate(ctx context.Context, forceRefresh ...bool) (string, error) {
	refresh := len(forceRefresh) > 0 && forceRefresh[0]
	if !refresh && a.token != "" && time.Now().Before(a.tokenExpiresAt.Add(-30*time.Second)) {
		return a.token, nil
	}
	var challenge ChallengeResponse
	if err := a.authGet(ctx, "/api/v1/auth/challenge?address="+url.QueryEscape(a.walletAddress), "", &challenge); err != nil {
		return "", err
	}
	if !challenge.Success || strings.TrimSpace(challenge.Challenge) == "" {
		return "", AuthenticationError{APIError{Message: "challenge request did not return a usable challenge"}}
	}
	signature, err := a.signer(challenge.Challenge)
	if err != nil {
		return "", err
	}
	var token TokenResponse
	err = a.authRequest(ctx, http.MethodPost, "/api/v1/auth/verify", "", map[string]any{
		"wallet_address": a.walletAddress,
		"message":        challenge.Challenge,
		"signature":      signature,
	}, &token)
	if err != nil {
		return "", err
	}
	if !token.Success || strings.TrimSpace(token.AccessToken) == "" {
		return "", AuthenticationError{APIError{Message: "auth verify did not return an access token"}}
	}
	a.token = token.AccessToken
	a.tokenExpiresAt = time.Now().Add(time.Duration(maxInt(token.ExpiresIn, 0)) * time.Second)
	return a.token, nil
}

func (a *Auth) GetToken(ctx context.Context) (string, error) {
	return a.Authenticate(ctx)
}

func (a *Auth) Logout(ctx context.Context) (*AuthLogoutResult, error) {
	var result AuthLogoutResult
	if err := a.ownerRequest(ctx, http.MethodPost, "/api/v1/auth/logout", nil, &result); err != nil {
		return nil, err
	}
	a.token = ""
	a.tokenExpiresAt = time.Time{}
	return &result, nil
}

func (a *Auth) GetOwnerProfile(ctx context.Context) (*OwnerProfile, error) {
	var result OwnerProfile
	err := a.ownerRequest(ctx, http.MethodGet, "/api/v1/auth/me", nil, &result)
	return &result, err
}

func (a *Auth) IssueCredential(ctx context.Context, opts CredentialOptions) (*IssueCredentialResult, error) {
	var raw map[string]any
	if err := a.ownerRequest(ctx, http.MethodPost, "/api/v1/credentials/agent/issue", credentialBody(opts), &raw); err != nil {
		return nil, err
	}
	result := issuedCredentialResult(raw, opts.Name)
	if result.Token == "" || result.Credential.ID == "" {
		return nil, AuthenticationError{APIError{Message: fmt.Sprintf("credential payload missing: %v", raw)}}
	}
	return &result, nil
}

func (a *Auth) ListCredentials(ctx context.Context) ([]AgentCredential, error) {
	return a.listCredentials(ctx, "/api/v1/credentials/agent/list")
}

func (a *Auth) ListActiveCredentials(ctx context.Context) ([]AgentCredential, error) {
	return a.listCredentials(ctx, "/api/v1/credentials/agent/list?active_only=true")
}

func (a *Auth) GetCredentialStatus(ctx context.Context, credentialID string) (*CredentialStatusResult, error) {
	var result CredentialStatusResult
	err := a.ownerRequest(ctx, http.MethodGet, "/api/v1/credentials/agent/"+escapeRequired(credentialID, "credentialID")+"/status", nil, &result)
	return &result, err
}

func (a *Auth) CheckCredentialStatus(ctx context.Context, credentialID string) (*CredentialStatusResult, error) {
	return a.GetCredentialStatus(ctx, credentialID)
}

func (a *Auth) RevokeCredential(ctx context.Context, credentialID string) (*CredentialRevokeResult, error) {
	var result CredentialRevokeResult
	err := a.ownerRequest(ctx, http.MethodPost, "/api/v1/credentials/agent/"+escapeRequired(credentialID, "credentialID")+"/revoke", nil, &result)
	return &result, err
}

func (a *Auth) RotateCredential(ctx context.Context, credentialID string) (*CredentialRotateResult, error) {
	var result CredentialRotateResult
	err := a.ownerRequest(ctx, http.MethodPost, "/api/v1/credentials/agent/"+escapeRequired(credentialID, "credentialID")+"/rotate", nil, &result)
	return &result, err
}

func (a *Auth) DeleteCredential(ctx context.Context, credentialID string) (*CredentialDeleteResult, error) {
	var result CredentialDeleteResult
	err := a.ownerRequest(ctx, http.MethodDelete, "/api/v1/credentials/agent/"+escapeRequired(credentialID, "credentialID"), nil, &result)
	return &result, err
}

func (a *Auth) UpdateCredentialQuota(ctx context.Context, credentialID string, opts CredentialQuotaOptions) (*CredentialQuotaUpdateResult, error) {
	var result CredentialQuotaUpdateResult
	err := a.ownerRequest(ctx, http.MethodPatch, "/api/v1/credentials/agent/"+escapeRequired(credentialID, "credentialID")+"/quota", quotaBody(opts), &result)
	return &result, err
}

func (a *Auth) GetCredentialAuditLogs(ctx context.Context, limit int) (*CredentialAuditLogList, error) {
	var result CredentialAuditLogList
	err := a.ownerRequest(ctx, http.MethodGet, queryPath("/api/v1/credentials/agent/audit-logs", map[string]any{"limit": defaultInt(limit, 100)}), nil, &result)
	return &result, err
}

func (a *Auth) EnsureCredential(ctx context.Context, name string, opts CredentialOptions) (string, error) {
	for _, credential := range mustSlice(a.ListActiveCredentials(ctx)) {
		if strings.TrimSpace(credential.Name) == strings.TrimSpace(name) {
			if credential.Token != "" {
				return credential.Token, nil
			}
			rotated, err := a.RotateCredential(ctx, firstNonEmpty(credential.CredentialID, credential.ID))
			if err != nil {
				return "", err
			}
			return firstNonEmpty(rotated.Token, rotated.Credential.Token), nil
		}
	}
	opts.Name = name
	issued, err := a.IssueCredential(ctx, opts)
	if err != nil {
		return "", err
	}
	return issued.Token, nil
}

func (a *Auth) GetBalance(ctx context.Context) (*BalanceSummary, error) {
	var raw struct {
		Balance *BalanceSummary `json:"balance"`
	}
	if err := a.ownerRequest(ctx, http.MethodGet, "/api/v1/balance", nil, &raw); err != nil {
		return nil, err
	}
	if raw.Balance == nil {
		return &BalanceSummary{}, nil
	}
	return raw.Balance, nil
}

func (a *Auth) RegisterDepositIntent(ctx context.Context, txHash, amountUSDC, idempotencyKey string) (*DepositIntentResult, error) {
	var result DepositIntentResult
	err := a.ownerRequestWithIdempotency(ctx, http.MethodPost, "/api/v1/balance/deposit/intent", map[string]any{"txHash": txHash, "amountUsdc": amountUSDC}, idempotencyKey, &result)
	return &result, err
}

func (a *Auth) ConfirmDeposit(ctx context.Context, intentID, eventKey string, confirmations int) (*DepositConfirmResult, error) {
	var result DepositConfirmResult
	err := a.ownerRequest(ctx, http.MethodPost, "/api/v1/balance/deposit/intents/"+escapeRequired(intentID, "intentID")+"/confirm", map[string]any{"eventKey": eventKey, "confirmations": defaultInt(confirmations, 1)}, &result)
	return &result, err
}

func (a *Auth) SetSpendingLimit(ctx context.Context, spendingLimitUSDC *string) error {
	body := map[string]any{"allowUnlimited": true}
	if spendingLimitUSDC != nil {
		body = map[string]any{"spendingLimitUsdc": *spendingLimitUSDC, "allowUnlimited": false}
	}
	var ignored map[string]any
	return a.ownerRequest(ctx, http.MethodPut, "/api/v1/balance/spending-limit", body, &ignored)
}

func (a *Auth) RedeemVoucher(ctx context.Context, voucherCode, idempotencyKey string) (*VoucherRedeemResult, error) {
	var result VoucherRedeemResult
	err := a.ownerRequestWithIdempotency(ctx, http.MethodPost, "/api/v1/balance/vouchers/redeem", map[string]any{"voucherCode": requireValue(voucherCode, "voucherCode")}, idempotencyKey, &result)
	return &result, err
}

func (a *Auth) GetUsageLogs(ctx context.Context, limit int) (*UsageLogList, error) {
	var result UsageLogList
	err := a.ownerRequest(ctx, http.MethodGet, queryPath("/api/v1/usage/logs", map[string]any{"limit": defaultInt(limit, 100)}), nil, &result)
	return &result, err
}

func (a *Auth) GetFinanceAuditLogs(ctx context.Context, limit int) (*FinanceAuditLogList, error) {
	var result FinanceAuditLogList
	err := a.ownerRequest(ctx, http.MethodGet, queryPath("/api/v1/finance/audit-logs", map[string]any{"limit": defaultInt(limit, 100)}), nil, &result)
	return &result, err
}

func (a *Auth) GetRiskOverview(ctx context.Context) (*RiskOverview, error) {
	var result RiskOverview
	err := a.ownerRequest(ctx, http.MethodGet, "/api/v1/finance/risk-overview", nil, &result)
	return &result, err
}

func (a *Auth) authGet(ctx context.Context, path, bearer string, target any) error {
	return a.authRequest(ctx, http.MethodGet, path, bearer, nil, target)
}

func (a *Auth) ownerRequest(ctx context.Context, method, path string, body map[string]any, target any) error {
	token, err := a.GetToken(ctx)
	if err != nil {
		return err
	}
	return a.authRequest(ctx, method, path, "Bearer "+token, body, target)
}

func (a *Auth) ownerRequestWithIdempotency(ctx context.Context, method, path string, body map[string]any, idem string, target any) error {
	token, err := a.GetToken(ctx)
	if err != nil {
		return err
	}
	return a.authRequestWithHeaders(ctx, method, path, map[string]string{"Authorization": "Bearer " + token, "X-Idempotency-Key": defaultString(idem, "go-"+fmt.Sprint(time.Now().UnixNano()))}, body, target)
}

func (a *Auth) authRequest(ctx context.Context, method, path, bearer string, body map[string]any, target any) error {
	headers := map[string]string{}
	if bearer != "" {
		headers["Authorization"] = bearer
	}
	return a.authRequestWithHeaders(ctx, method, path, headers, body, target)
}

func (a *Auth) authRequestWithHeaders(ctx context.Context, method, path string, headers map[string]string, body map[string]any, target any) error {
	var reader io.Reader
	if body != nil {
		raw, err := json.Marshal(body)
		if err != nil {
			return err
		}
		reader = bytes.NewReader(raw)
	}
	req, err := http.NewRequestWithContext(ctx, method, a.gatewayURL+path, reader)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	for key, value := range headers {
		req.Header.Set(key, value)
	}
	resp, err := a.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return parseAPIError(resp.StatusCode, raw)
	}
	if len(raw) == 0 {
		return nil
	}
	return json.Unmarshal(raw, target)
}

func (a *Auth) listCredentials(ctx context.Context, path string) ([]AgentCredential, error) {
	var raw struct {
		Credentials []AgentCredential `json:"credentials"`
	}
	err := a.ownerRequest(ctx, http.MethodGet, path, nil, &raw)
	return raw.Credentials, err
}

type Provider struct{ auth *Auth }

func (p *Provider) IssueSecret(ctx context.Context, opts CredentialOptions) (*IssueProviderSecretResult, error) {
	return p.auth.IssueProviderSecret(ctx, opts)
}

func (p *Provider) ListSecrets(ctx context.Context) ([]ProviderSecret, error) {
	return p.auth.ListProviderSecrets(ctx)
}

func (p *Provider) DeleteSecret(ctx context.Context, secretID string) (*ProviderSecretDeleteResult, error) {
	return p.auth.DeleteProviderSecret(ctx, secretID)
}

func (p *Provider) GetRegistrationGuide(ctx context.Context) (*ProviderRegistrationGuide, error) {
	return p.auth.GetRegistrationGuide(ctx)
}

func (p *Provider) ParseCurlToServiceManifest(ctx context.Context, curlCommand string) (*ServiceManifestDraft, error) {
	return p.auth.ParseCurlToServiceManifest(ctx, curlCommand)
}

func (p *Provider) RegisterService(ctx context.Context, opts RegisterProviderServiceOptions) (*RegisterProviderServiceResult, error) {
	return p.auth.RegisterProviderService(ctx, opts)
}

func (p *Provider) RegisterLLMService(ctx context.Context, opts RegisterProviderServiceOptions) (*RegisterProviderServiceResult, error) {
	opts.ServiceKind = "llm"
	opts.PriceModel = "token_metered"
	return p.auth.RegisterProviderService(ctx, opts)
}

func (p *Provider) ListServices(ctx context.Context) ([]ProviderServiceRecord, error) {
	return p.auth.ListProviderServices(ctx)
}

func (p *Provider) GetService(ctx context.Context, serviceID string) (*ProviderServiceRecord, error) {
	return p.auth.GetProviderService(ctx, serviceID)
}

func (p *Provider) GetServiceStatus(ctx context.Context, serviceID string) (*ProviderServiceStatus, error) {
	return p.auth.GetProviderServiceStatus(ctx, serviceID)
}

func (p *Provider) UpdateService(ctx context.Context, serviceRecordID string, patch map[string]any) (*ProviderServiceUpdateResult, error) {
	return p.auth.UpdateProviderService(ctx, serviceRecordID, patch)
}

func (p *Provider) DeleteService(ctx context.Context, serviceRecordID string) (*ProviderServiceDeleteResult, error) {
	return p.auth.DeleteProviderService(ctx, serviceRecordID)
}

func (p *Provider) PingService(ctx context.Context, serviceRecordID string) (*ProviderServicePingResult, error) {
	return p.auth.PingProviderService(ctx, serviceRecordID)
}

func (p *Provider) GetServiceHealthHistory(ctx context.Context, serviceRecordID string, limit int) (*ProviderServiceHealthHistory, error) {
	return p.auth.GetProviderServiceHealthHistory(ctx, serviceRecordID, limit)
}

func (p *Provider) GetEarningsSummary(ctx context.Context) (*ProviderEarningsSummary, error) {
	return p.auth.GetProviderEarningsSummary(ctx)
}

func (p *Provider) GetWithdrawalCapability(ctx context.Context) (*ProviderWithdrawalCapability, error) {
	return p.auth.GetProviderWithdrawalCapability(ctx)
}

func (p *Provider) CreateWithdrawalIntent(ctx context.Context, amountUSDC, idempotencyKey, destinationAddress string) (*ProviderWithdrawalIntentResult, error) {
	return p.auth.CreateProviderWithdrawalIntent(ctx, amountUSDC, idempotencyKey, destinationAddress)
}

func (p *Provider) ListWithdrawals(ctx context.Context, limit int) (*ProviderWithdrawalList, error) {
	return p.auth.ListProviderWithdrawals(ctx, limit)
}
