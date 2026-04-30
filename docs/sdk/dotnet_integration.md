# .NET SDK Integration Guide

The .NET SDK is a Wave 1 consumer runtime SDK targeting `net8.0`.

## Install

The preview package project lives in `dotnet/src/SynapseNetwork.Sdk` and is intended for NuGet publication as `SynapseNetwork.Sdk`.

```xml
<PackageReference Include="SynapseNetwork.Sdk" Version="0.1.0-preview" />
```

## Fixed-Price API Invoke

```csharp
using SynapseNetwork.Sdk;

var client = new SynapseClient(new SynapseClientOptions
{
    Credential = Environment.GetEnvironmentVariable("SYNAPSE_AGENT_KEY")!,
    Environment = "staging",
});

var services = await client.SearchAsync("free", new SearchOptions { Limit = 10 });
var service = services[0];
var price = service.Pricing?.GetProperty("amount").GetString() ?? "0";

var result = await client.InvokeAsync(
    service.ServiceId ?? service.Id!,
    new Dictionary<string, object?> { ["prompt"] = "hello" },
    new InvokeOptions { CostUsdc = price });

Console.WriteLine($"{result.InvocationId} {result.Status} {result.ChargedUsdc}");
```

## Token-Metered LLM Invoke

```csharp
var result = await client.InvokeLlmAsync(
    "svc_deepseek_chat",
    new Dictionary<string, object?>
    {
        ["messages"] = new[] { new Dictionary<string, object?> { ["role"] = "user", ["content"] = "hello" } },
    },
    new LlmInvokeOptions { MaxCostUsdc = "0.010000" });
```

Do not pass fixed-price `CostUsdc` to LLM services. Use `MaxCostUsdc` as an optional cap or omit it to let the Gateway compute the hold.

## Verification

```bash
bash scripts/ci/dotnet_checks.sh
dotnet test dotnet/tests/SynapseNetwork.Sdk.Tests/SynapseNetwork.Sdk.Tests.csproj
SYNAPSE_AGENT_KEY=agt_xxx dotnet run --project dotnet/examples/free-service-smoke/free-service-smoke.csproj
SYNAPSE_AGENT_KEY=agt_xxx dotnet run --project dotnet/examples/llm-smoke/llm-smoke.csproj
SYNAPSE_AGENT_KEY=agt_xxx dotnet run --project dotnet/examples/e2e/e2e.csproj
```
