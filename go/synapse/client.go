package synapse

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const (
	DefaultEnvironment = "staging"
	StagingGatewayURL = "https://api-staging.synapse-network.ai"
	ProdGatewayURL    = "https://api.synapse-network.ai"
)

type Client struct {
	credential string
	gatewayURL string
	timeout    time.Duration
	httpClient *http.Client
}

type Options struct {
	Credential  string
	Environment string
	GatewayURL  string
	Timeout     time.Duration
	HTTPClient  *http.Client
}

type SearchOptions struct {
	Limit     int
	Offset    int
	Tags      []string
	Sort      string
	RequestID string
}

type InvokeOptions struct {
	CostUSDC       string
	IdempotencyKey string
	ResponseMode   string
	RequestID      string
}

type LLMInvokeOptions struct {
	MaxCostUSDC    string
	IdempotencyKey string
	RequestID      string
}

type ServiceRecord struct {
	ServiceID   string         `json:"serviceId,omitempty"`
	ID          string         `json:"id,omitempty"`
	ServiceName string         `json:"serviceName,omitempty"`
	Status      string         `json:"status,omitempty"`
	ServiceKind string         `json:"serviceKind,omitempty"`
	PriceModel  string         `json:"priceModel,omitempty"`
	Pricing     map[string]any `json:"pricing,omitempty"`
	Summary     string         `json:"summary,omitempty"`
	Tags        []string       `json:"tags,omitempty"`
}

type InvocationResult struct {
	InvocationID string         `json:"invocationId,omitempty"`
	Status       string         `json:"status,omitempty"`
	ChargedUSDC  string         `json:"chargedUsdc,omitempty"`
	Result       map[string]any `json:"result,omitempty"`
	Usage        map[string]any `json:"usage,omitempty"`
	Synapse      map[string]any `json:"synapse,omitempty"`
	Error        map[string]any `json:"error,omitempty"`
	Receipt      map[string]any `json:"receipt,omitempty"`
}

type APIError struct {
	StatusCode int
	Code       string
	Message    string
}

func (e APIError) Error() string {
	if e.Code == "" {
		return e.Message
	}
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

type AuthenticationError struct{ APIError }
type BudgetError struct{ APIError }
type DiscoveryError struct{ APIError }
type InvokeError struct{ APIError }

type PriceMismatchError struct {
	APIError
	ExpectedPriceUSDC string
	CurrentPriceUSDC  string
}

func NewClient(opts Options) (*Client, error) {
	credential := strings.TrimSpace(opts.Credential)
	if credential == "" {
		return nil, errors.New("credential is required")
	}
	gatewayURL, err := ResolveGatewayURL(opts.Environment, opts.GatewayURL)
	if err != nil {
		return nil, err
	}
	timeout := opts.Timeout
	if timeout == 0 {
		timeout = 30 * time.Second
	}
	httpClient := opts.HTTPClient
	if httpClient == nil {
		httpClient = &http.Client{Timeout: timeout}
	}
	return &Client{credential: credential, gatewayURL: gatewayURL, timeout: timeout, httpClient: httpClient}, nil
}

func ResolveGatewayURL(environment, gatewayURL string) (string, error) {
	if trimmed := strings.TrimRight(strings.TrimSpace(gatewayURL), "/"); trimmed != "" {
		return trimmed, nil
	}
	switch strings.ToLower(strings.TrimSpace(defaultString(environment, DefaultEnvironment))) {
	case "staging":
		return StagingGatewayURL, nil
	case "prod":
		return ProdGatewayURL, nil
	default:
		return "", fmt.Errorf("unsupported Synapse environment %q", environment)
	}
}

func (c *Client) Search(ctx context.Context, query string, opts SearchOptions) ([]ServiceRecord, error) {
	pageSize := maxInt(1, defaultInt(opts.Limit, 20))
	tags := opts.Tags
	if tags == nil {
		tags = []string{}
	}
	body := map[string]any{
		"tags":     tags,
		"page":     (maxInt(0, opts.Offset) / pageSize) + 1,
		"pageSize": pageSize,
		"sort":     defaultString(opts.Sort, "best_match"),
	}
	if strings.TrimSpace(query) != "" {
		body["query"] = strings.TrimSpace(query)
	}
	var response struct {
		Services []ServiceRecord `json:"services"`
		Results  []ServiceRecord `json:"results"`
	}
	if err := c.post(ctx, "/api/v1/agent/discovery/search", body, opts.RequestID, &response); err != nil {
		return nil, mapDiscoveryError(err)
	}
	if response.Results != nil {
		return response.Results, nil
	}
	return response.Services, nil
}

func (c *Client) Discover(ctx context.Context, opts SearchOptions) ([]ServiceRecord, error) {
	return c.Search(ctx, "", opts)
}

func (c *Client) Invoke(ctx context.Context, serviceID string, payload map[string]any, opts InvokeOptions) (*InvocationResult, error) {
	if strings.TrimSpace(serviceID) == "" {
		return nil, errors.New("serviceID is required")
	}
	if strings.TrimSpace(opts.CostUSDC) == "" {
		return nil, errors.New("costUSDC is required for fixed-price API services; use InvokeLLM for LLM services")
	}
	body := invocationBody(serviceID, payload, defaultString(opts.ResponseMode, "sync"), opts.IdempotencyKey)
	body["costUsdc"] = opts.CostUSDC
	return c.invoke(ctx, body, opts.RequestID)
}

func (c *Client) InvokeLLM(ctx context.Context, serviceID string, payload map[string]any, opts LLMInvokeOptions) (*InvocationResult, error) {
	if payload != nil {
		if stream, ok := payload["stream"].(bool); ok && stream {
			return nil, InvokeError{APIError{Code: "LLM_STREAMING_NOT_SUPPORTED", Message: "stream=true is not supported"}}
		}
	}
	body := invocationBody(serviceID, payload, "sync", opts.IdempotencyKey)
	if strings.TrimSpace(opts.MaxCostUSDC) != "" {
		body["maxCostUsdc"] = opts.MaxCostUSDC
	}
	return c.invoke(ctx, body, opts.RequestID)
}

func (c *Client) GetInvocation(ctx context.Context, invocationID string) (*InvocationResult, error) {
	if strings.TrimSpace(invocationID) == "" {
		return nil, errors.New("invocationID is required")
	}
	var result InvocationResult
	err := c.get(ctx, "/api/v1/agent/invocations/"+url.PathEscape(strings.TrimSpace(invocationID)), &result)
	return &result, err
}

func (c *Client) CheckGatewayHealth(ctx context.Context) (map[string]any, error) {
	var result map[string]any
	err := c.get(ctx, "/health", &result)
	return result, err
}

func (c *Client) invoke(ctx context.Context, body map[string]any, requestID string) (*InvocationResult, error) {
	var result InvocationResult
	if err := c.post(ctx, "/api/v1/agent/invoke", body, requestID, &result); err != nil {
		return nil, mapInvokeError(err)
	}
	return &result, nil
}

func invocationBody(serviceID string, payload map[string]any, responseMode, idempotencyKey string) map[string]any {
	if payload == nil {
		payload = map[string]any{}
	}
	if strings.TrimSpace(idempotencyKey) == "" {
		idempotencyKey = fmt.Sprintf("go-%d", time.Now().UnixNano())
	}
	return map[string]any{
		"serviceId":      strings.TrimSpace(serviceID),
		"idempotencyKey": idempotencyKey,
		"payload":        map[string]any{"body": payload},
		"responseMode":   responseMode,
	}
}

func (c *Client) post(ctx context.Context, path string, body map[string]any, requestID string, target any) error {
	raw, err := json.Marshal(body)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.gatewayURL+path, bytes.NewReader(raw))
	if err != nil {
		return err
	}
	return c.do(req, requestID, target)
}

func (c *Client) get(ctx context.Context, path string, target any) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.gatewayURL+path, nil)
	if err != nil {
		return err
	}
	return c.do(req, "", target)
}

func (c *Client) do(req *http.Request, requestID string, target any) error {
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Credential", c.credential)
	if requestID != "" {
		req.Header.Set("X-Request-Id", requestID)
	}
	resp, err := c.httpClient.Do(req)
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

func parseAPIError(status int, raw []byte) error {
	var payload struct {
		Detail map[string]any `json:"detail"`
	}
	_ = json.Unmarshal(raw, &payload)
	code := stringValue(payload.Detail["code"])
	message := defaultString(stringValue(payload.Detail["message"]), string(raw))
	base := APIError{StatusCode: status, Code: code, Message: message}
	if status == http.StatusUnauthorized {
		return AuthenticationError{base}
	}
	if status == http.StatusPaymentRequired {
		return BudgetError{base}
	}
	if status == http.StatusUnprocessableEntity && code == "PRICE_MISMATCH" {
		return PriceMismatchError{
			APIError:          base,
			ExpectedPriceUSDC: stringValue(payload.Detail["expectedPriceUsdc"]),
			CurrentPriceUSDC:  stringValue(payload.Detail["currentPriceUsdc"]),
		}
	}
	return base
}

func mapDiscoveryError(err error) error {
	var auth AuthenticationError
	var budget BudgetError
	var price PriceMismatchError
	if errors.As(err, &auth) || errors.As(err, &budget) || errors.As(err, &price) {
		return err
	}
	return DiscoveryError{APIError{Message: err.Error()}}
}

func mapInvokeError(err error) error {
	var auth AuthenticationError
	var budget BudgetError
	var price PriceMismatchError
	if errors.As(err, &auth) || errors.As(err, &budget) || errors.As(err, &price) {
		return err
	}
	return InvokeError{APIError{Message: err.Error()}}
}

func defaultString(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func defaultInt(value, fallback int) int {
	if value == 0 {
		return fallback
	}
	return value
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func stringValue(value any) string {
	switch typed := value.(type) {
	case string:
		return typed
	case fmt.Stringer:
		return typed.String()
	case nil:
		return ""
	default:
		return fmt.Sprint(typed)
	}
}
