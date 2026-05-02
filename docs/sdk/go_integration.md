# Go SDK Integration Guide

The Go SDK supports the full public Synapse SDK surface: `SynapseClient` agent runtime, `Auth` owner wallet auth, credential and finance helpers, and `Provider` publishing/withdrawal helpers.

## Install

The preview module lives in this monorepo:

```bash
go get github.com/SynapseNetworkAI/Synapse-Network-Sdk/go
```

## Fixed-Price API Invoke

```go
package main

import (
    "context"
    "fmt"
    "os"

    synapse "github.com/SynapseNetworkAI/Synapse-Network-Sdk/go/synapse"
)

func main() {
    client, err := synapse.NewClient(synapse.Options{
        Credential:  os.Getenv("SYNAPSE_AGENT_KEY"),
        Environment: "staging",
    })
    if err != nil {
        panic(err)
    }

    services, err := client.Search(context.Background(), "svc_synapse_echo", synapse.SearchOptions{Limit: 10})
    if err != nil {
        panic(err)
    }
    service := services[0]

    result, err := client.Invoke(
        context.Background(),
        service.ServiceID,
        map[string]any{
            "message": "hello from Synapse SDK smoke",
            "metadata": map[string]any{"scenario": "quickstart"},
        },
        synapse.InvokeOptions{CostUSDC: fmt.Sprint(service.Pricing["amount"])},
    )
    if err != nil {
        panic(err)
    }
    fmt.Println(result.InvocationID, result.Status, result.ChargedUSDC)
}
```

## Token-Metered LLM Invoke

```go
result, err := client.InvokeLLM(
    context.Background(),
    "svc_deepseek_chat",
    map[string]any{"messages": []map[string]string{{"role": "user", "content": "hello"}}},
    synapse.LLMInvokeOptions{MaxCostUSDC: "0.010000"},
)
```

Do not pass fixed-price `CostUSDC` to LLM services. Use `MaxCostUSDC` as an optional cap or omit it to let the Gateway compute the hold.

## Owner Auth and Provider Control

Use owner auth only in backend or operator tooling. Agent runtime code should keep using `SynapseClient` with `SYNAPSE_AGENT_KEY`.

```go
auth, err := synapse.NewAuthFromPrivateKey(os.Getenv("SYNAPSE_OWNER_PRIVATE_KEY"), synapse.AuthOptions{
    Environment: "staging",
})
if err != nil {
    panic(err)
}

token, err := auth.GetToken(context.Background())
credential, err := auth.IssueCredential(context.Background(), synapse.CredentialOptions{
    Name: "agent-runtime",
    MaxCalls: 100,
    RPM: 60,
    ExpiresInSec: 3600,
})
balance, err := auth.GetBalance(context.Background())
guide, err := auth.Provider().GetRegistrationGuide(context.Background())

fmt.Println(token != "", credential.Token, balance.OwnerBalance, len(guide.Steps))
```

Public owner/provider methods return named Go structs. Do not expose `map[string]any` as a top-level public result; reserve maps for request payloads, schemas, patches, and dynamic nested fields.

## Verification

```bash
bash scripts/ci/go_checks.sh
SYNAPSE_AGENT_KEY=agt_xxx go -C go run ./examples/free_service_smoke
SYNAPSE_AGENT_KEY=agt_xxx go -C go run ./examples/llm_smoke
SYNAPSE_AGENT_KEY=agt_xxx go -C go run ./examples/e2e
SYNAPSE_OWNER_PRIVATE_KEY=0x... bash scripts/e2e/sdk_parity_e2e.sh --languages go --env staging
```
