package synapse

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	secpEcdsa "github.com/decred/dcrd/dcrec/secp256k1/v4/ecdsa"
)

const testPrivateKey = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

func TestAuthFromPrivateKeySignsChallengeAndCachesToken(t *testing.T) {
	challengeCalls := 0
	verifyCalls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/v1/auth/challenge":
			challengeCalls++
			if r.URL.Query().Get("address") != "0xfcad0b19bb29d4674531d6f115237e16afce377c" {
				t.Fatalf("unexpected address query: %s", r.URL.RawQuery)
			}
			writeJSON(t, w, map[string]any{"success": true, "challenge": "sign me", "domain": "synapse"})
		case "/api/v1/auth/verify":
			verifyCalls++
			var body map[string]string
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if !validTestSignature(body["signature"], body["message"]) {
				t.Fatalf("signature did not recover expected address: %#v", body)
			}
			writeJSON(t, w, map[string]any{"success": true, "access_token": "jwt_owner", "token_type": "bearer", "expires_in": 3600})
		case "/api/v1/auth/me":
			if r.Header.Get("Authorization") != "Bearer jwt_owner" {
				t.Fatalf("missing bearer token")
			}
			writeJSON(t, w, map[string]any{"ownerAddress": "0xowner"})
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	auth, err := NewAuthFromPrivateKey(testPrivateKey, AuthOptions{GatewayURL: server.URL})
	if err != nil {
		t.Fatal(err)
	}
	if token, err := auth.GetToken(context.Background()); err != nil || token != "jwt_owner" {
		t.Fatalf("unexpected token %q err=%v", token, err)
	}
	if token, err := auth.GetToken(context.Background()); err != nil || token != "jwt_owner" {
		t.Fatalf("unexpected cached token %q err=%v", token, err)
	}
	if challengeCalls != 1 || verifyCalls != 1 {
		t.Fatalf("token was not cached challenge=%d verify=%d", challengeCalls, verifyCalls)
	}
	profile, err := auth.GetOwnerProfile(context.Background())
	if err != nil || profile.OwnerAddress != "0xowner" {
		t.Fatalf("unexpected profile %#v err=%v", profile, err)
	}
}

func TestAuthCredentialFinanceAndProviderRoutes(t *testing.T) {
	var seen []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = append(seen, r.Method+" "+r.URL.Path)
		if strings.HasPrefix(r.URL.Path, "/api/v1/auth/") {
			authFixture(t, w, r)
			return
		}
		if r.Header.Get("Authorization") != "Bearer jwt_owner" {
			t.Fatalf("missing Authorization for %s", r.URL.Path)
		}
		switch r.URL.Path {
		case "/api/v1/credentials/agent/issue":
			writeJSON(t, w, map[string]any{"credential": map[string]any{"id": "cred_1", "token": "agt_1", "status": "active"}, "token": "agt_1"})
		case "/api/v1/credentials/agent/list":
			writeJSON(t, w, map[string]any{"credentials": []any{map[string]any{"id": "cred_1", "name": "agent", "status": "active"}}})
		case "/api/v1/credentials/agent/cred_1/quota":
			writeJSON(t, w, map[string]any{"status": "success", "credentialId": "cred_1"})
		case "/api/v1/credentials/agent/audit-logs":
			writeJSON(t, w, map[string]any{"logs": []any{map[string]any{"action": "issue"}}})
		case "/api/v1/balance":
			writeJSON(t, w, map[string]any{"balance": map[string]any{"ownerBalance": "1.00"}})
		case "/api/v1/usage/logs":
			writeJSON(t, w, map[string]any{"logs": []any{map[string]any{"id": "usage_1"}}})
		case "/api/v1/services/registration-guide":
			writeJSON(t, w, map[string]any{"steps": []any{"register"}})
		case "/api/v1/services":
			if r.Method == http.MethodPost {
				writeJSON(t, w, map[string]any{"status": "success", "serviceId": "svc_weather", "service": map[string]any{"serviceId": "svc_weather"}})
			} else {
				writeJSON(t, w, map[string]any{"services": []any{map[string]any{"serviceId": "svc_weather", "status": "active", "runtimeAvailable": true}}})
			}
		case "/api/v1/services/rec_1":
			writeJSON(t, w, map[string]any{"status": "success"})
		case "/api/v1/providers/withdrawals/intent":
			writeJSON(t, w, map[string]any{"status": "success", "intentId": "wd_1"})
		default:
			writeJSON(t, w, map[string]any{"status": "success"})
		}
	}))
	defer server.Close()
	auth, err := NewAuthFromPrivateKey(testPrivateKey, AuthOptions{GatewayURL: server.URL})
	if err != nil {
		t.Fatal(err)
	}
	issued, err := auth.IssueCredential(context.Background(), CredentialOptions{Name: "agent"})
	if err != nil || issued.Token != "agt_1" {
		t.Fatalf("unexpected issued %#v err=%v", issued, err)
	}
	if _, err = auth.ListCredentials(context.Background()); err != nil {
		t.Fatal(err)
	}
	if _, err = auth.UpdateCredentialQuota(context.Background(), "cred_1", CredentialQuotaOptions{CreditLimit: "1.00"}); err != nil {
		t.Fatal(err)
	}
	if _, err = auth.GetCredentialAuditLogs(context.Background(), 10); err != nil {
		t.Fatal(err)
	}
	if balance, err := auth.GetBalance(context.Background()); err != nil || balance.OwnerBalance != "1.00" {
		t.Fatalf("unexpected balance %#v err=%v", balance, err)
	}
	if _, err = auth.GetUsageLogs(context.Background(), 5); err != nil {
		t.Fatal(err)
	}
	provider := auth.Provider()
	if _, err = provider.GetRegistrationGuide(context.Background()); err != nil {
		t.Fatal(err)
	}
	if _, err = provider.RegisterService(context.Background(), RegisterProviderServiceOptions{ServiceName: "Weather", EndpointURL: "https://provider.example.com/invoke", BasePriceUSDC: "0.01", DescriptionForModel: "Weather"}); err != nil {
		t.Fatal(err)
	}
	if status, err := provider.GetServiceStatus(context.Background(), "svc_weather"); err != nil || !status.RuntimeAvailable {
		t.Fatalf("unexpected status %#v err=%v", status, err)
	}
	if _, err = provider.UpdateService(context.Background(), "rec_1", map[string]any{"status": "active"}); err != nil {
		t.Fatal(err)
	}
	if _, err = provider.CreateWithdrawalIntent(context.Background(), "0.10", "idem", "0xabc"); err != nil {
		t.Fatal(err)
	}
	assertSeen(t, seen, "POST /api/v1/credentials/agent/issue", "GET /api/v1/balance", "POST /api/v1/services", "POST /api/v1/providers/withdrawals/intent")
}

func authFixture(t *testing.T, w http.ResponseWriter, r *http.Request) {
	t.Helper()
	if r.URL.Path == "/api/v1/auth/challenge" {
		writeJSON(t, w, map[string]any{"success": true, "challenge": "sign me"})
		return
	}
	writeJSON(t, w, map[string]any{"success": true, "access_token": "jwt_owner", "expires_in": 3600})
}

func validTestSignature(signatureHex, message string) bool {
	raw, err := decodeHex(signatureHex)
	if err != nil || len(raw) != 65 {
		return false
	}
	compact := append([]byte{raw[64]}, raw[:64]...)
	pub, _, err := secpEcdsa.RecoverCompact(compact, ethereumMessageHash(message))
	return err == nil && ethereumAddress(pub.SerializeUncompressed()) == "0xfcad0b19bb29d4674531d6f115237e16afce377c"
}

func writeJSON(t *testing.T, w http.ResponseWriter, value any) {
	t.Helper()
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(value); err != nil {
		t.Fatal(err)
	}
}

func assertSeen(t *testing.T, seen []string, expected ...string) {
	t.Helper()
	joined := strings.Join(seen, "\n")
	for _, item := range expected {
		if !strings.Contains(joined, item) {
			t.Fatalf("missing route %s in:\n%s", item, joined)
		}
	}
}
