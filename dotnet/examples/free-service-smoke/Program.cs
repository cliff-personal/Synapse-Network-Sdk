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
var service = await FindFixedSmokeService(client);
var price = PricingAmount(service);
var result = await client.InvokeAsync(
    service.ServiceId ?? service.Id ?? throw new InvalidOperationException("service id missing"),
    new Dictionary<string, object?>
    {
        ["message"] = "hello from Synapse SDK smoke",
        ["metadata"] = new Dictionary<string, object?> { ["scenario"] = "free-service-smoke" },
    },
    new InvokeOptions { CostUsdc = price });
Console.WriteLine($"{result.InvocationId} {result.Status} {result.ChargedUsdc}");

static async Task<ServiceRecord> FindFixedSmokeService(SynapseClient client)
{
    const string synapseEchoServiceId = "svc_synapse_echo";
    var echoServices = await client.SearchAsync(synapseEchoServiceId, new SearchOptions { Limit = 10 });
    foreach (var service in echoServices)
    {
        if (service.ServiceId == synapseEchoServiceId && IsFreeFixedApiService(service))
        {
            return service;
        }
    }

    var services = await client.SearchAsync("free", new SearchOptions { Limit = 10 });
    foreach (var service in services)
    {
        if (IsFreeFixedApiService(service))
        {
            return service;
        }
    }
    throw new InvalidOperationException("no free fixed-price API service found; set SYNAPSE_E2E_FIXED_SERVICE_ID and SYNAPSE_E2E_FIXED_COST_USDC for paid smoke tests");
}

static string PricingAmount(ServiceRecord service)
{
    return service.Pricing.HasValue && service.Pricing.Value.TryGetProperty("amount", out var amount)
        ? amount.GetString() ?? ""
        : "";
}

static bool IsFreeFixedApiService(ServiceRecord service)
{
    return !string.IsNullOrWhiteSpace(service.ServiceId)
        && string.Equals(service.ServiceKind, "api", StringComparison.OrdinalIgnoreCase)
        && string.Equals(service.PriceModel, "fixed", StringComparison.OrdinalIgnoreCase)
        && decimal.TryParse(PricingAmount(service), out var amount)
        && amount == 0;
}
