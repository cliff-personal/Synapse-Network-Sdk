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
	result, err := client.InvokeLLM(
		context.Background(),
		"svc_deepseek_chat",
		map[string]any{"messages": []map[string]string{{"role": "user", "content": "hello"}}},
		synapse.LLMInvokeOptions{MaxCostUSDC: "0.010000"},
	)
	if err != nil {
		panic(err)
	}
	fmt.Println(result.InvocationID, result.Status, result.ChargedUSDC)
}
