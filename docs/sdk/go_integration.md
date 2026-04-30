# Go SDK Integration Guide

The Go SDK is a Wave 1 consumer runtime SDK. It supports service discovery, fixed-price invoke, token-metered LLM invoke, invocation receipt lookup, and gateway health checks.

## Install

The preview module lives in this monorepo:

```bash
go get github.com/cliff-personal/Synapse-Network-Sdk/go
```

## Fixed-Price API Invoke

```go
package main

import (
    "context"
    "fmt"
    "os"

    synapse "github.com/cliff-personal/Synapse-Network-Sdk/go/synapse"
)

func main() {
    client, err := synapse.NewClient(synapse.Options{
        Credential:  os.Getenv("SYNAPSE_AGENT_KEY"),
        Environment: "staging",
    })
    if err != nil {
        panic(err)
    }

    services, err := client.Search(context.Background(), "free", synapse.SearchOptions{Limit: 10})
    if err != nil {
        panic(err)
    }
    service := services[0]

    result, err := client.Invoke(
        context.Background(),
        service.ServiceID,
        map[string]any{"prompt": "hello"},
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

## Verification

```bash
bash scripts/ci/go_checks.sh
SYNAPSE_AGENT_KEY=agt_xxx go -C go run ./examples/free_service_smoke
SYNAPSE_AGENT_KEY=agt_xxx go -C go run ./examples/llm_smoke
SYNAPSE_AGENT_KEY=agt_xxx go -C go run ./examples/e2e
```
