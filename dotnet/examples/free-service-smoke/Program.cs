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
var services = await client.SearchAsync("free", new SearchOptions { Limit = 10 });
if (services.Count == 0)
{
    throw new InvalidOperationException("no services found");
}

var service = services[0];
var price = "0";
if (service.Pricing.HasValue && service.Pricing.Value.TryGetProperty("amount", out var amount))
{
    price = amount.GetString() ?? "0";
}
var result = await client.InvokeAsync(
    service.ServiceId ?? service.Id ?? throw new InvalidOperationException("service id missing"),
    new Dictionary<string, object?> { ["prompt"] = "hello" },
    new InvokeOptions { CostUsdc = price });
Console.WriteLine($"{result.InvocationId} {result.Status} {result.ChargedUsdc}");
