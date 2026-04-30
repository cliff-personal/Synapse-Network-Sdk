package synapse

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestResolveGatewayURL(t *testing.T) {
	got, err := ResolveGatewayURL("", "https://gateway.example.com/")
	if err != nil || got != "https://gateway.example.com" {
		t.Fatalf("explicit gateway url should win, got=%q err=%v", got, err)
	}
	got, err = ResolveGatewayURL("", "")
	if err != nil || got != StagingGatewayURL {
		t.Fatalf("default environment should be staging, got=%q err=%v", got, err)
	}
	if _, err = ResolveGatewayURL("local", ""); err == nil {
		t.Fatal("unsupported environment should fail")
	}
}

func TestSearchInvokeLLMAndReceiptUseContractFixtures(t *testing.T) {
	var seenInvoke map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-Credential") != "agt_test" {
			t.Fatalf("missing X-Credential header")
		}
		switch r.URL.Path {
		case "/api/v1/agent/discovery/search":
			writeFixture(t, w, "discovery_search_response.json")
		case "/api/v1/agent/invoke":
			if err := json.NewDecoder(r.Body).Decode(&seenInvoke); err != nil {
				t.Fatal(err)
			}
			writeFixture(t, w, "llm_invoke_response.json")
		case "/api/v1/agent/invocations/inv_contract_llm":
			writeFixture(t, w, "receipt_response.json")
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	client, err := NewClient(Options{Credential: "agt_test", GatewayURL: server.URL})
	if err != nil {
		t.Fatal(err)
	}
	services, err := client.Search(context.Background(), "fixture", SearchOptions{Limit: 10})
	if err != nil {
		t.Fatal(err)
	}
	if len(services) != 1 || services[0].ServiceID != "svc_contract_weather" {
		t.Fatalf("unexpected services: %#v", services)
	}
	result, err := client.InvokeLLM(
		context.Background(),
		"svc_deepseek_chat",
		map[string]any{"messages": []any{map[string]any{"role": "user", "content": "hello"}}},
		LLMInvokeOptions{MaxCostUSDC: "0.010000", IdempotencyKey: "idem-llm"},
	)
	if err != nil {
		t.Fatal(err)
	}
	if result.InvocationID != "inv_contract_llm" || result.ChargedUSDC != "0.004200" {
		t.Fatalf("unexpected llm result: %#v", result)
	}
	if seenInvoke["costUsdc"] != nil || seenInvoke["maxCostUsdc"] != "0.010000" {
		t.Fatalf("unexpected llm invoke body: %#v", seenInvoke)
	}
	receipt, err := client.GetInvocation(context.Background(), "inv_contract_llm")
	if err != nil {
		t.Fatal(err)
	}
	if receipt.Status != "SETTLED" {
		t.Fatalf("unexpected receipt: %#v", receipt)
	}
}

func TestInvokeRequiresStringCostAndMapsPriceMismatch(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnprocessableEntity)
		writeFixture(t, w, "error_price_mismatch.json")
	}))
	defer server.Close()

	client, err := NewClient(Options{Credential: "agt_test", GatewayURL: server.URL})
	if err != nil {
		t.Fatal(err)
	}
	if _, err = client.Invoke(context.Background(), "svc", nil, InvokeOptions{}); err == nil {
		t.Fatal("missing cost should fail")
	}
	_, err = client.Invoke(context.Background(), "svc", nil, InvokeOptions{CostUSDC: "0.010000"})
	var priceErr PriceMismatchError
	if !errors.As(err, &priceErr) {
		t.Fatalf("expected PriceMismatchError, got %T %v", err, err)
	}
	if priceErr.CurrentPriceUSDC != "0.012000" {
		t.Fatalf("unexpected current price: %#v", priceErr)
	}
}

func writeFixture(t *testing.T, w http.ResponseWriter, name string) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("..", "..", "contracts", "sdk", "fixtures", name))
	if err != nil {
		t.Fatal(err)
	}
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write(raw)
}
