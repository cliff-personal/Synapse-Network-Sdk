using SynapseNetwork.Sdk;

var agentKey = Environment.GetEnvironmentVariable("SYNAPSE_AGENT_KEY");
if (string.IsNullOrWhiteSpace(agentKey))
{
    throw new InvalidOperationException("SYNAPSE_AGENT_KEY is required");
}

var client = new SynapseClient(new SynapseClientOptions
{
    Credential = agentKey,
    Environment = "staging",
});
var result = await client.InvokeLlmAsync(
    "svc_deepseek_chat",
    new Dictionary<string, object?>
    {
        ["messages"] = new[] { new Dictionary<string, object?> { ["role"] = "user", ["content"] = "hello" } },
    },
    new LlmInvokeOptions { MaxCostUsdc = "0.010000" });
Console.WriteLine($"{result.InvocationId} {result.Status} {result.ChargedUsdc}");
