package main

import (
	"context"
	"fmt"
	"os"

	synapse "github.com/cliff-personal/Synapse-Network-Sdk/go/synapse"
)

func main() {
	agentKey := os.Getenv("SYNAPSE_AGENT_KEY")
	if agentKey == "" {
		panic("SYNAPSE_AGENT_KEY is required")
	}
	client, err := synapse.NewClient(synapse.Options{Credential: agentKey, Environment: "staging"})
	if err != nil {
		panic(err)
	}
	services, err := client.Search(context.Background(), "free", synapse.SearchOptions{Limit: 10})
	if err != nil {
		panic(err)
	}
	if len(services) == 0 {
		panic("no services found")
	}
	result, err := client.Invoke(
		context.Background(),
		services[0].ServiceID,
		map[string]any{"prompt": "hello"},
		synapse.InvokeOptions{CostUSDC: fmt.Sprint(services[0].Pricing["amount"])},
	)
	if err != nil {
		panic(err)
	}
	fmt.Println(result.InvocationID, result.Status, result.ChargedUSDC)
}
