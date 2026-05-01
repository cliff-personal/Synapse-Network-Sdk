package synapse

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"
)

func (a *Auth) IssueProviderSecret(ctx context.Context, opts CredentialOptions) (*IssueProviderSecretResult, error) {
	var result IssueProviderSecretResult
	err := a.ownerRequest(ctx, http.MethodPost, "/api/v1/secrets/provider/issue", credentialBody(opts), &result)
	if err == nil && result.Secret.ID == "" {
		err = AuthenticationError{APIError{Message: "provider secret payload missing"}}
	}
	return &result, err
}

func (a *Auth) ListProviderSecrets(ctx context.Context) ([]ProviderSecret, error) {
	var raw struct {
		Secrets []ProviderSecret `json:"secrets"`
	}
	err := a.ownerRequest(ctx, http.MethodGet, "/api/v1/secrets/provider/list", nil, &raw)
	return raw.Secrets, err
}

func (a *Auth) DeleteProviderSecret(ctx context.Context, secretID string) (*ProviderSecretDeleteResult, error) {
	var result ProviderSecretDeleteResult
	err := a.ownerRequest(ctx, http.MethodDelete, "/api/v1/secrets/provider/"+escapeRequired(secretID, "secretID"), nil, &result)
	return &result, err
}

func (a *Auth) RegisterProviderService(ctx context.Context, opts RegisterProviderServiceOptions) (*RegisterProviderServiceResult, error) {
	body, err := providerServiceBody(a.walletAddress, opts)
	if err != nil {
		return nil, err
	}
	var raw RegisterProviderServiceResult
	if err := a.ownerRequest(ctx, http.MethodPost, "/api/v1/services", body, &raw); err != nil {
		return nil, err
	}
	if raw.ServiceID == "" {
		raw.ServiceID = firstNonEmpty(raw.Service.ServiceID, body["serviceId"].(string))
	}
	if raw.Service.ServiceID == "" {
		raw.Service.ServiceID = raw.ServiceID
	}
	return &raw, nil
}

func (a *Auth) RegisterLLMService(ctx context.Context, opts RegisterProviderServiceOptions) (*RegisterProviderServiceResult, error) {
	opts.ServiceKind = "llm"
	opts.PriceModel = "token_metered"
	return a.RegisterProviderService(ctx, opts)
}

func (a *Auth) ListProviderServices(ctx context.Context) ([]ProviderServiceRecord, error) {
	var raw struct {
		Services []ProviderServiceRecord `json:"services"`
	}
	err := a.ownerRequest(ctx, http.MethodGet, "/api/v1/services", nil, &raw)
	return raw.Services, err
}

func (a *Auth) GetRegistrationGuide(ctx context.Context) (*ProviderRegistrationGuide, error) {
	var result ProviderRegistrationGuide
	err := a.ownerRequest(ctx, http.MethodGet, "/api/v1/services/registration-guide", nil, &result)
	return &result, err
}

func (a *Auth) ParseCurlToServiceManifest(ctx context.Context, curlCommand string) (*ServiceManifestDraft, error) {
	var result ServiceManifestDraft
	err := a.ownerRequest(ctx, http.MethodPost, "/api/v1/services/parse-curl", map[string]any{"curlCommand": requireValue(curlCommand, "curlCommand")}, &result)
	return &result, err
}

func (a *Auth) UpdateProviderService(ctx context.Context, serviceRecordID string, patch map[string]any) (*ProviderServiceUpdateResult, error) {
	var result ProviderServiceUpdateResult
	err := a.ownerRequest(ctx, http.MethodPut, "/api/v1/services/"+escapeRequired(serviceRecordID, "serviceRecordID"), patch, &result)
	return &result, err
}

func (a *Auth) DeleteProviderService(ctx context.Context, serviceRecordID string) (*ProviderServiceDeleteResult, error) {
	var result ProviderServiceDeleteResult
	err := a.ownerRequest(ctx, http.MethodDelete, "/api/v1/services/"+escapeRequired(serviceRecordID, "serviceRecordID"), nil, &result)
	return &result, err
}

func (a *Auth) PingProviderService(ctx context.Context, serviceRecordID string) (*ProviderServicePingResult, error) {
	var result ProviderServicePingResult
	err := a.ownerRequest(ctx, http.MethodPost, "/api/v1/services/"+escapeRequired(serviceRecordID, "serviceRecordID")+"/ping", nil, &result)
	return &result, err
}

func (a *Auth) GetProviderServiceHealthHistory(ctx context.Context, serviceRecordID string, limit int) (*ProviderServiceHealthHistory, error) {
	var result ProviderServiceHealthHistory
	path := queryPath("/api/v1/services/"+escapeRequired(serviceRecordID, "serviceRecordID")+"/health/history", map[string]any{"limitPerTarget": defaultInt(limit, 100)})
	err := a.ownerRequest(ctx, http.MethodGet, path, nil, &result)
	return &result, err
}

func (a *Auth) GetProviderEarningsSummary(ctx context.Context) (*ProviderEarningsSummary, error) {
	var result ProviderEarningsSummary
	err := a.ownerRequest(ctx, http.MethodGet, "/api/v1/providers/earnings/summary", nil, &result)
	return &result, err
}

func (a *Auth) GetProviderWithdrawalCapability(ctx context.Context) (*ProviderWithdrawalCapability, error) {
	var result ProviderWithdrawalCapability
	err := a.ownerRequest(ctx, http.MethodGet, "/api/v1/providers/withdrawals/capability", nil, &result)
	return &result, err
}

func (a *Auth) CreateProviderWithdrawalIntent(ctx context.Context, amountUSDC, idempotencyKey, destinationAddress string) (*ProviderWithdrawalIntentResult, error) {
	body := map[string]any{"amountUsdc": requireValue(amountUSDC, "amountUSDC")}
	if strings.TrimSpace(destinationAddress) != "" {
		body["destinationAddress"] = strings.TrimSpace(destinationAddress)
	}
	var result ProviderWithdrawalIntentResult
	err := a.ownerRequestWithIdempotency(ctx, http.MethodPost, "/api/v1/providers/withdrawals/intent", body, idempotencyKey, &result)
	return &result, err
}

func (a *Auth) ListProviderWithdrawals(ctx context.Context, limit int) (*ProviderWithdrawalList, error) {
	var result ProviderWithdrawalList
	err := a.ownerRequest(ctx, http.MethodGet, queryPath("/api/v1/providers/withdrawals", map[string]any{"limit": defaultInt(limit, 100)}), nil, &result)
	return &result, err
}

func (a *Auth) GetProviderService(ctx context.Context, serviceID string) (*ProviderServiceRecord, error) {
	resolved := requireValue(serviceID, "serviceID")
	services, err := a.ListProviderServices(ctx)
	if err != nil {
		return nil, err
	}
	for _, service := range services {
		if service.ServiceID == resolved {
			return &service, nil
		}
	}
	return nil, AuthenticationError{APIError{Message: "provider service not found: " + resolved}}
}

func (a *Auth) GetProviderServiceStatus(ctx context.Context, serviceID string) (*ProviderServiceStatus, error) {
	service, err := a.GetProviderService(ctx, serviceID)
	if err != nil {
		return nil, err
	}
	return &ProviderServiceStatus{
		ServiceID:        firstNonEmpty(service.ServiceID, service.ID),
		LifecycleStatus:  defaultString(service.Status, "unknown"),
		RuntimeAvailable: service.RuntimeAvailable,
		Health:           service.Health,
	}, nil
}

func providerServiceBody(walletAddress string, opts RegisterProviderServiceOptions) (map[string]any, error) {
	name := requireValue(opts.ServiceName, "serviceName")
	endpoint := requireValue(opts.EndpointURL, "endpointURL")
	summary := requireValue(opts.DescriptionForModel, "descriptionForModel")
	serviceID := defaultString(opts.ServiceID, defaultServiceID(name))
	kind := defaultString(opts.ServiceKind, "api")
	priceModel := defaultString(opts.PriceModel, map[bool]string{true: "token_metered", false: "fixed"}[kind == "llm"])
	pricing, err := providerPricing(opts, priceModel)
	if err != nil {
		return nil, err
	}
	active := true
	if opts.IsActive != nil {
		active = *opts.IsActive
	}
	return map[string]any{
		"serviceId":       serviceID,
		"agentToolName":   serviceID,
		"serviceName":     name,
		"serviceKind":     kind,
		"priceModel":      priceModel,
		"role":            "Provider",
		"status":          defaultString(opts.Status, "active"),
		"isActive":        active,
		"pricing":         pricing,
		"summary":         summary,
		"tags":            opts.Tags,
		"auth":            map[string]any{"type": "gateway_signed"},
		"invoke":          providerInvoke(endpoint, opts),
		"healthCheck":     providerHealth(opts),
		"providerProfile": map[string]any{"displayName": defaultString(opts.ProviderDisplayName, name)},
		"payoutAccount": map[string]any{
			"payoutAddress":      defaultString(opts.PayoutAddress, walletAddress),
			"chainId":            defaultInt(opts.ChainID, 31337),
			"settlementCurrency": defaultString(opts.SettlementCurrency, "USDC"),
		},
		"governance": map[string]any{"termsAccepted": true, "riskAcknowledged": true, "note": opts.GovernanceNote},
	}, nil
}

func providerPricing(opts RegisterProviderServiceOptions, priceModel string) (map[string]any, error) {
	if priceModel == "token_metered" {
		if strings.TrimSpace(opts.InputPricePer1MTokensUSDC) == "" || strings.TrimSpace(opts.OutputPricePer1MTokensUSDC) == "" {
			return nil, errors.New("input and output token prices are required")
		}
		pricing := map[string]any{"priceModel": "token_metered", "inputPricePer1MTokensUsdc": opts.InputPricePer1MTokensUSDC, "outputPricePer1MTokensUsdc": opts.OutputPricePer1MTokensUSDC, "currency": "USDC"}
		if opts.DefaultMaxOutputTokens != 0 {
			pricing["defaultMaxOutputTokens"] = opts.DefaultMaxOutputTokens
		}
		if opts.HoldBufferMultiplier != "" {
			pricing["holdBufferMultiplier"] = opts.HoldBufferMultiplier
		}
		if opts.MaxAutoHoldUSDC != "" {
			pricing["maxAutoHoldUsdc"] = opts.MaxAutoHoldUSDC
		}
		return pricing, nil
	}
	if strings.TrimSpace(opts.BasePriceUSDC) == "" {
		return nil, errors.New("basePriceUSDC is required")
	}
	return map[string]any{"amount": opts.BasePriceUSDC, "currency": "USDC"}, nil
}

func providerInvoke(endpoint string, opts RegisterProviderServiceOptions) map[string]any {
	input := opts.InputSchema
	if input == nil {
		input = map[string]any{"type": "object", "properties": map[string]any{}, "required": []any{}}
	}
	output := opts.OutputSchema
	if output == nil {
		output = map[string]any{"type": "object", "properties": map[string]any{}}
	}
	return map[string]any{"method": defaultString(opts.EndpointMethod, "POST"), "targets": []map[string]any{{"url": endpoint}}, "timeoutMs": defaultInt(opts.RequestTimeoutMS, 15000), "request": map[string]any{"body": input}, "response": map[string]any{"body": output}}
}

func providerHealth(opts RegisterProviderServiceOptions) map[string]any {
	return map[string]any{"path": defaultString(opts.HealthPath, "/health"), "method": defaultString(opts.HealthMethod, "GET"), "timeoutMs": defaultInt(opts.HealthTimeoutMS, 3000), "successCodes": []int{200}, "healthyThreshold": 1, "unhealthyThreshold": 3}
}

func defaultServiceID(name string) string {
	cleaned := strings.Trim(strings.Map(func(r rune) rune {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '_' || r == '-' {
			return r
		}
		if r >= 'A' && r <= 'Z' {
			return r + 32
		}
		return '_'
	}, strings.TrimSpace(name)), "_")
	if cleaned == "" {
		return fmt.Sprintf("service_%d", time.Now().UnixNano())
	}
	return cleaned
}

func credentialBody(opts CredentialOptions) map[string]any {
	body := map[string]any{}
	setIf(body, "name", opts.Name)
	setIf(body, "maxCalls", opts.MaxCalls)
	setIf(body, "creditLimit", opts.CreditLimit)
	setIf(body, "resetInterval", opts.ResetInterval)
	setIf(body, "rpm", opts.RPM)
	setIf(body, "expiresInSec", opts.ExpiresInSec)
	setIf(body, "expiration", opts.Expiration)
	return body
}

func quotaBody(opts CredentialQuotaOptions) map[string]any {
	body := map[string]any{}
	setIf(body, "maxCalls", opts.MaxCalls)
	setIf(body, "rpm", opts.RPM)
	setIf(body, "creditLimit", opts.CreditLimit)
	setIf(body, "resetInterval", opts.ResetInterval)
	setIf(body, "expiresAt", opts.ExpiresAt)
	setIf(body, "expiration", opts.Expiration)
	return body
}

func issuedCredentialResult(raw map[string]any, fallbackName string) IssueCredentialResult {
	credentialPayload, _ := raw["credential"].(map[string]any)
	credential := AgentCredential{}
	rawCredential, _ := json.Marshal(credentialPayload)
	_ = json.Unmarshal(rawCredential, &credential)
	token := firstNonEmpty(stringValue(raw["token"]), credential.Token, stringValue(raw["credential_token"]))
	id := firstNonEmpty(stringValue(raw["credential_id"]), stringValue(raw["id"]), credential.ID, credential.CredentialID)
	credential.ID = firstNonEmpty(credential.ID, id)
	credential.CredentialID = firstNonEmpty(credential.CredentialID, id)
	credential.Token = firstNonEmpty(credential.Token, token)
	credential.Name = firstNonEmpty(credential.Name, fallbackName)
	return IssueCredentialResult{Credential: credential, Token: token}
}

func setIf(body map[string]any, key string, value any) {
	if stringValue(value) != "" && stringValue(value) != "0" {
		body[key] = value
	}
}

func escapeRequired(value, name string) string {
	return url.PathEscape(requireValue(value, name))
}

func requireValue(value, name string) string {
	resolved := strings.TrimSpace(value)
	if resolved == "" {
		panic(name + " is required")
	}
	return resolved
}

func queryPath(path string, params map[string]any) string {
	values := url.Values{}
	for key, value := range params {
		if stringValue(value) != "" {
			values.Set(key, stringValue(value))
		}
	}
	if len(values) == 0 {
		return path
	}
	return path + "?" + values.Encode()
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func mustSlice[T any](values []T, err error) []T {
	if err != nil {
		return nil
	}
	return values
}
