# .NET SDK Integration Guide

The .NET SDK targets `net8.0`. It supports the full public Synapse SDK surface: `SynapseClient` agent runtime, `SynapseAuth` owner wallet auth, credential and finance helpers, and `SynapseProvider` publishing/withdrawal helpers.

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

var services = await client.SearchAsync("svc_synapse_echo", new SearchOptions { Limit = 10 });
var service = services[0];
var price = service.Pricing?.GetProperty("amount").GetString() ?? "0";

var result = await client.InvokeAsync(
    service.ServiceId ?? service.Id!,
    new Dictionary<string, object?>
    {
        ["message"] = "hello from Synapse SDK smoke",
        ["metadata"] = new Dictionary<string, object?> { ["scenario"] = "quickstart" },
    },
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

## Owner Auth and Provider Control

Use owner auth only in backend or operator tooling. Agent runtime code should keep using `SynapseClient` with `SYNAPSE_AGENT_KEY`.

```csharp
var auth = SynapseAuth.FromPrivateKey(
    Environment.GetEnvironmentVariable("SYNAPSE_OWNER_PRIVATE_KEY")!,
    new SynapseAuthOptions { Environment = "staging" });

var token = await auth.GetTokenAsync();
var credential = await auth.IssueCredentialAsync(new CredentialOptions
{
    Name = "agent-runtime",
    MaxCalls = 100,
    Rpm = 60,
    ExpiresInSec = 3600,
});
var balance = await auth.GetBalanceAsync();
var guide = await auth.Provider().GetRegistrationGuideAsync();

Console.WriteLine($"{token.Length} {credential.Token} {guide.Steps?.Count ?? 0}");
```

Public owner/provider methods return named .NET records. Do not expose `JsonElement` or `Dictionary` as a top-level public result; reserve them for request payloads, schemas, patches, and dynamic nested fields.

## Verification

```bash
bash scripts/ci/dotnet_checks.sh
dotnet test dotnet/tests/SynapseNetwork.Sdk.Tests/SynapseNetwork.Sdk.Tests.csproj
SYNAPSE_AGENT_KEY=agt_xxx dotnet run --project dotnet/examples/free-service-smoke/free-service-smoke.csproj
SYNAPSE_AGENT_KEY=agt_xxx dotnet run --project dotnet/examples/llm-smoke/llm-smoke.csproj
SYNAPSE_AGENT_KEY=agt_xxx dotnet run --project dotnet/examples/e2e/e2e.csproj
SYNAPSE_OWNER_PRIVATE_KEY=0x... bash scripts/e2e/sdk_parity_e2e.sh --languages dotnet --env staging
```
