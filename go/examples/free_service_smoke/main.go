package main

import (
	"context"
	"fmt"
	"math/big"
	"os"
	"strings"

	synapse "github.com/SynapseNetworkAI/Synapse-Network-Sdk/go/synapse"
)

const synapseEchoServiceID = "svc_synapse_echo"

func main() {
	agentKey := os.Getenv("SYNAPSE_AGENT_KEY")
	if agentKey == "" {
		panic("SYNAPSE_AGENT_KEY is required")
	}
	client, err := synapse.NewClient(synapse.Options{Credential: agentKey, Environment: "staging"})
	if err != nil {
		panic(err)
	}
	ctx := context.Background()
	service := findFixedSmokeService(ctx, client)
	result, err := client.Invoke(
		ctx,
		service.ServiceID,
		map[string]any{
			"message": "hello from Synapse SDK smoke",
			"metadata": map[string]any{"scenario": "free-service-smoke"},
		},
		synapse.InvokeOptions{CostUSDC: fmt.Sprint(service.Pricing["amount"])},
	)
	if err != nil {
		panic(err)
	}
	fmt.Println(result.InvocationID, result.Status, result.ChargedUSDC)
}

func findFixedSmokeService(ctx context.Context, client *synapse.Client) synapse.ServiceRecord {
	services, err := client.Search(ctx, synapseEchoServiceID, synapse.SearchOptions{Limit: 10})
	if err != nil {
		panic(err)
	}
	for _, service := range services {
		if service.ServiceID == synapseEchoServiceID && isFreeFixedAPIService(service) {
			return service
		}
	}

	services, err = client.Search(ctx, "free", synapse.SearchOptions{Limit: 10})
	if err != nil {
		panic(err)
	}
	for _, service := range services {
		if isFreeFixedAPIService(service) {
			return service
		}
	}
	panic("no free fixed-price API service found; set SYNAPSE_E2E_FIXED_SERVICE_ID and SYNAPSE_E2E_FIXED_COST_USDC for paid smoke tests")
}

func isFreeFixedAPIService(service synapse.ServiceRecord) bool {
	amount := fmt.Sprint(service.Pricing["amount"])
	left, ok := new(big.Rat).SetString(amount)
	if !ok {
		return false
	}
	return strings.TrimSpace(service.ServiceID) != "" &&
		strings.EqualFold(service.ServiceKind, "api") &&
		strings.EqualFold(service.PriceModel, "fixed") &&
		left.Sign() == 0
}
