package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"os"
	"strings"
	"time"

	synapse "github.com/cliff-personal/Synapse-Network-Sdk/go/synapse"
)

const (
	defaultFixedPayload = `{"prompt":"hello"}`
	defaultLLMPayload   = `{"messages":[{"role":"user","content":"hello"}]}`
)

type e2eEvent struct {
	Language      string `json:"language"`
	Scenario      string `json:"scenario"`
	InvocationID  string `json:"invocationId,omitempty"`
	Status        string `json:"status,omitempty"`
	ChargedUSDC   string `json:"chargedUsdc,omitempty"`
	ReceiptStatus string `json:"receiptStatus,omitempty"`
	ServiceID     string `json:"serviceId,omitempty"`
}

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	credential := requireEnv("SYNAPSE_AGENT_KEY")
	client, err := synapse.NewClient(synapse.Options{
		Credential: credential,
		GatewayURL: os.Getenv("SYNAPSE_GATEWAY_URL"),
	})
	must(err)

	mustLocalValidation(ctx, client)
	must(client.CheckGatewayHealth(ctx))
	emit(e2eEvent{Language: "go", Scenario: "health", Status: "ok"})

	if !envBool("SYNAPSE_E2E_SKIP_AUTH_NEGATIVE") {
		mustAuthNegative(ctx)
	}

	fixedServiceID, fixedCost, fixedPayload := fixedService(ctx, client)
	fixedResult, err := client.Invoke(
		ctx,
		fixedServiceID,
		fixedPayload,
		synapse.InvokeOptions{CostUSDC: fixedCost, IdempotencyKey: idempotencyKey("go", "fixed")},
	)
	must(err)
	fixedReceipt := awaitReceipt(ctx, client, fixedResult.InvocationID)
	emit(e2eEvent{
		Language:      "go",
		Scenario:      "fixed-price",
		InvocationID:  fixedResult.InvocationID,
		Status:        fixedResult.Status,
		ChargedUSDC:   fixedReceipt.ChargedUSDC,
		ReceiptStatus: fixedReceipt.Status,
		ServiceID:     fixedServiceID,
	})

	if envBool("SYNAPSE_E2E_FREE_ONLY") {
		return
	}

	llmServiceID := envDefault("SYNAPSE_E2E_LLM_SERVICE_ID", "svc_deepseek_chat")
	llmPayload := parsePayload(envDefault("SYNAPSE_E2E_LLM_PAYLOAD_JSON", defaultLLMPayload))
	maxCost := envDefault("SYNAPSE_E2E_LLM_MAX_COST_USDC", "0.010000")
	llmResult, err := client.InvokeLLM(
		ctx,
		llmServiceID,
		llmPayload,
		synapse.LLMInvokeOptions{MaxCostUSDC: maxCost, IdempotencyKey: idempotencyKey("go", "llm")},
	)
	must(err)
	llmReceipt := awaitReceipt(ctx, client, llmResult.InvocationID)
	charged := firstNonEmpty(llmReceipt.ChargedUSDC, llmResult.ChargedUSDC)
	if charged == "" {
		fail("llm invoke did not report chargedUsdc")
	}
	if decimalGreater(charged, maxCost) {
		fail("llm chargedUsdc %s exceeds maxCostUsdc %s", charged, maxCost)
	}
	emit(e2eEvent{
		Language:      "go",
		Scenario:      "llm",
		InvocationID:  llmResult.InvocationID,
		Status:        llmResult.Status,
		ChargedUSDC:   charged,
		ReceiptStatus: llmReceipt.Status,
		ServiceID:     llmServiceID,
	})
}

func mustLocalValidation(ctx context.Context, client *synapse.Client) {
	if _, err := client.Invoke(ctx, "svc_local", nil, synapse.InvokeOptions{}); err == nil {
		fail("fixed-price invoke without costUSDC should fail locally")
	}
	if _, err := client.InvokeLLM(ctx, "svc_llm", map[string]any{"stream": true}, synapse.LLMInvokeOptions{}); err == nil {
		fail("LLM stream=true should fail locally")
	}
	emit(e2eEvent{Language: "go", Scenario: "local-negative", Status: "ok"})
}

func mustAuthNegative(ctx context.Context) {
	client, err := synapse.NewClient(synapse.Options{
		Credential: "agt_invalid",
		GatewayURL: os.Getenv("SYNAPSE_GATEWAY_URL"),
	})
	must(err)
	_, err = client.Invoke(
		ctx,
		"svc_invalid_auth_probe",
		map[string]any{},
		synapse.InvokeOptions{CostUSDC: "0"},
	)
	var authErr synapse.AuthenticationError
	if !errors.As(err, &authErr) {
		fail("invalid credential should return AuthenticationError, got %T: %v", err, err)
	}
	emit(e2eEvent{Language: "go", Scenario: "auth-negative", Status: "ok"})
}

func fixedService(ctx context.Context, client *synapse.Client) (string, string, map[string]any) {
	payload := parsePayload(envDefault("SYNAPSE_E2E_FIXED_PAYLOAD_JSON", defaultFixedPayload))
	if serviceID := strings.TrimSpace(os.Getenv("SYNAPSE_E2E_FIXED_SERVICE_ID")); serviceID != "" {
		cost := strings.TrimSpace(os.Getenv("SYNAPSE_E2E_FIXED_COST_USDC"))
		if cost == "" {
			fail("SYNAPSE_E2E_FIXED_COST_USDC is required when SYNAPSE_E2E_FIXED_SERVICE_ID is set")
		}
		return serviceID, cost, payload
	}

	services, err := client.Search(ctx, "free", synapse.SearchOptions{Limit: 25})
	must(err)
	for _, service := range services {
		amount := moneyString(service.Pricing["amount"])
		if strings.TrimSpace(service.ServiceID) != "" &&
			strings.EqualFold(service.ServiceKind, "api") &&
			strings.EqualFold(service.PriceModel, "fixed") &&
			decimalEqual(amount, "0") {
			return service.ServiceID, amount, payload
		}
	}
	fail("no free fixed-price API service found; set SYNAPSE_E2E_FIXED_SERVICE_ID, SYNAPSE_E2E_FIXED_COST_USDC, and SYNAPSE_E2E_FIXED_PAYLOAD_JSON")
	return "", "", nil
}

func awaitReceipt(ctx context.Context, client *synapse.Client, invocationID string) *synapse.InvocationResult {
	if strings.TrimSpace(invocationID) == "" {
		fail("invoke returned empty invocationId")
	}
	deadline := time.Now().Add(time.Duration(envInt("SYNAPSE_E2E_RECEIPT_TIMEOUT_S", 60)) * time.Second)
	for {
		receipt, err := client.GetInvocation(ctx, invocationID)
		must(err)
		if receipt.InvocationID != "" && receipt.InvocationID != invocationID {
			fail("receipt invocationId mismatch: got %s want %s", receipt.InvocationID, invocationID)
		}
		if terminal(receipt.Status) {
			return receipt
		}
		if time.Now().After(deadline) {
			fail("receipt %s did not reach a terminal status, last status=%s", invocationID, receipt.Status)
		}
		time.Sleep(2 * time.Second)
	}
}

func parsePayload(raw string) map[string]any {
	var payload map[string]any
	if err := json.Unmarshal([]byte(raw), &payload); err != nil {
		fail("invalid payload JSON: %v", err)
	}
	return payload
}

func terminal(status string) bool {
	switch strings.ToUpper(strings.TrimSpace(status)) {
	case "SUCCEEDED", "SETTLED":
		return true
	default:
		return false
	}
}

func moneyString(value any) string {
	switch typed := value.(type) {
	case string:
		return typed
	case json.Number:
		return typed.String()
	case nil:
		return ""
	default:
		return fmt.Sprint(typed)
	}
}

func decimalEqual(left, right string) bool {
	l, ok := new(big.Rat).SetString(strings.TrimSpace(left))
	if !ok {
		return false
	}
	r, ok := new(big.Rat).SetString(strings.TrimSpace(right))
	return ok && l.Cmp(r) == 0
}

func decimalGreater(left, right string) bool {
	l, ok := new(big.Rat).SetString(strings.TrimSpace(left))
	if !ok {
		fail("invalid decimal %q", left)
	}
	r, ok := new(big.Rat).SetString(strings.TrimSpace(right))
	if !ok {
		fail("invalid decimal %q", right)
	}
	return l.Cmp(r) > 0
}

func emit(event e2eEvent) {
	raw, err := json.Marshal(event)
	must(err)
	fmt.Println(string(raw))
}

func requireEnv(name string) string {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		fail("%s is required", name)
	}
	return value
}

func envDefault(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func envBool(name string) bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv(name))) {
	case "1", "true", "yes", "y":
		return true
	default:
		return false
	}
}

func envInt(name string, fallback int) int {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}
	value := fallback
	if _, err := fmt.Sscanf(raw, "%d", &value); err != nil || value <= 0 {
		return fallback
	}
	return value
}

func idempotencyKey(language, scenario string) string {
	prefix := language + "-e2e"
	if runID := strings.TrimSpace(os.Getenv("E2E_RUN_ID")); runID != "" {
		prefix = runID + "-" + prefix
	}
	return prefix + "-" + scenario + "-" + time.Now().Format("20060102150405000000000")
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func must(values ...any) {
	for _, value := range values {
		if err, ok := value.(error); ok && err != nil {
			fail("%v", err)
		}
	}
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "go e2e failed: "+format+"\n", args...)
	os.Exit(1)
}
