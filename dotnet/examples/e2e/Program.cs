using System.Globalization;
using System.Text.Json;
using SynapseNetwork.Sdk;

const string SynapseEchoServiceId = "svc_synapse_echo";
const string DefaultFixedPayload = "{\"message\":\"hello from Synapse SDK smoke\",\"metadata\":{\"scenario\":\"fixed-price\"}}";
const string DefaultLlmPayload = "{\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}]}";

var credential = RequireEnv("SYNAPSE_AGENT_KEY");
var client = Client(credential);
var cancellationToken = new CancellationTokenSource(TimeSpan.FromMinutes(2)).Token;

await LocalNegative(client, cancellationToken);
await client.HealthAsync(cancellationToken);
Emit("health", status: "ok");

if (!EnvBool("SYNAPSE_E2E_SKIP_AUTH_NEGATIVE"))
{
    await AuthNegative(cancellationToken);
}

var fixedTarget = await FixedTarget(client, cancellationToken);
var fixedResult = await client.InvokeAsync(
    fixedTarget.ServiceId,
    fixedTarget.Payload,
    new InvokeOptions
    {
        CostUsdc = fixedTarget.CostUsdc,
        IdempotencyKey = IdempotencyKey("fixed"),
    },
    cancellationToken);
var fixedReceipt = await AwaitReceipt(client, fixedResult.InvocationId, cancellationToken);
Emit(
    "fixed-price",
    fixedResult.Status,
    fixedResult.InvocationId,
    fixedReceipt.ChargedUsdc,
    fixedReceipt.Status,
    fixedTarget.ServiceId);

if (!EnvBool("SYNAPSE_E2E_FREE_ONLY"))
{
    var llmServiceId = EnvDefault("SYNAPSE_E2E_LLM_SERVICE_ID", "svc_deepseek_chat");
    var maxCost = EnvDefault("SYNAPSE_E2E_LLM_MAX_COST_USDC", "0.010000");
    var llmResult = await client.InvokeLlmAsync(
        llmServiceId,
        Payload(EnvDefault("SYNAPSE_E2E_LLM_PAYLOAD_JSON", DefaultLlmPayload)),
        new LlmInvokeOptions
        {
            MaxCostUsdc = maxCost,
            IdempotencyKey = IdempotencyKey("llm"),
        },
        cancellationToken);
    var llmReceipt = await AwaitReceipt(client, llmResult.InvocationId, cancellationToken);
    var charged = FirstNonBlank(llmReceipt.ChargedUsdc, llmResult.ChargedUsdc);
    if (string.IsNullOrWhiteSpace(charged))
    {
        Fail("llm invoke did not report chargedUsdc");
    }
    if (decimal.Parse(charged, CultureInfo.InvariantCulture) > decimal.Parse(maxCost, CultureInfo.InvariantCulture))
    {
        Fail($"llm chargedUsdc {charged} exceeds maxCostUsdc {maxCost}");
    }
    Emit("llm", llmResult.Status, llmResult.InvocationId, charged, llmReceipt.Status, llmServiceId);
}

static SynapseClient Client(string credential)
{
    var gatewayUrl = Environment.GetEnvironmentVariable("SYNAPSE_GATEWAY_URL");
    return new SynapseClient(new SynapseClientOptions
    {
        Credential = credential,
        Environment = string.IsNullOrWhiteSpace(gatewayUrl) ? "staging" : null,
        GatewayUrl = gatewayUrl,
    });
}

static async Task LocalNegative(SynapseClient client, CancellationToken cancellationToken)
{
    await ExpectFailure<ArgumentException>(() =>
        client.InvokeAsync("svc_local", null, new InvokeOptions { CostUsdc = "" }, cancellationToken));
    await ExpectFailure<InvokeException>(() =>
        client.InvokeLlmAsync("svc_llm", new Dictionary<string, object?> { ["stream"] = true }, null, cancellationToken));
    Emit("local-negative", status: "ok");
}

static async Task AuthNegative(CancellationToken cancellationToken)
{
    var invalidClient = Client("agt_invalid");
    await ExpectFailure<AuthenticationException>(() =>
        invalidClient.InvokeAsync(
            "svc_invalid_auth_probe",
            new Dictionary<string, object?>(),
            new InvokeOptions { CostUsdc = "0" },
            cancellationToken));
    Emit("auth-negative", status: "ok");
}

static async Task<FixedServiceTarget> FixedTarget(SynapseClient client, CancellationToken cancellationToken)
{
    var payload = Payload(EnvDefault("SYNAPSE_E2E_FIXED_PAYLOAD_JSON", DefaultFixedPayload));
    var configuredServiceId = Environment.GetEnvironmentVariable("SYNAPSE_E2E_FIXED_SERVICE_ID");
    if (!string.IsNullOrWhiteSpace(configuredServiceId))
    {
        var cost = Environment.GetEnvironmentVariable("SYNAPSE_E2E_FIXED_COST_USDC");
        if (string.IsNullOrWhiteSpace(cost))
        {
            Fail("SYNAPSE_E2E_FIXED_COST_USDC is required when SYNAPSE_E2E_FIXED_SERVICE_ID is set");
            throw new InvalidOperationException("unreachable");
        }
        return new FixedServiceTarget(configuredServiceId.Trim(), cost.Trim(), payload);
    }

    var echoServices = await client.SearchAsync(SynapseEchoServiceId, new SearchOptions { Limit = 10 }, cancellationToken);
    foreach (var service in echoServices)
    {
        var amount = PricingAmount(service);
        if (string.Equals(service.ServiceId, SynapseEchoServiceId, StringComparison.Ordinal)
            && IsFreeFixedApiService(service, amount))
        {
            return new FixedServiceTarget(service.ServiceId, amount, payload);
        }
    }

    var services = await client.SearchAsync("free", new SearchOptions { Limit = 25 }, cancellationToken);
    foreach (var service in services)
    {
        var amount = PricingAmount(service);
        if (IsFreeFixedApiService(service, amount))
        {
            return new FixedServiceTarget(service.ServiceId, amount, payload);
        }
    }
    Fail("no free fixed-price API service found; set SYNAPSE_E2E_FIXED_SERVICE_ID, SYNAPSE_E2E_FIXED_COST_USDC, and SYNAPSE_E2E_FIXED_PAYLOAD_JSON");
    throw new InvalidOperationException("unreachable");
}

static bool IsFreeFixedApiService(ServiceRecord service, string amount)
{
    return !string.IsNullOrWhiteSpace(service.ServiceId)
        && string.Equals(service.ServiceKind, "api", StringComparison.OrdinalIgnoreCase)
        && string.Equals(service.PriceModel, "fixed", StringComparison.OrdinalIgnoreCase)
        && DecimalEquals(amount, "0");
}

static async Task<InvocationResult> AwaitReceipt(SynapseClient client, string? invocationId, CancellationToken cancellationToken)
{
    if (string.IsNullOrWhiteSpace(invocationId))
    {
        Fail("invoke returned empty invocationId");
        throw new InvalidOperationException("unreachable");
    }
    var safeInvocationId = invocationId.Trim();
    var deadline = DateTimeOffset.UtcNow.AddSeconds(EnvInt("SYNAPSE_E2E_RECEIPT_TIMEOUT_S", 60));
    while (true)
    {
        var receipt = await client.GetInvocationAsync(safeInvocationId, cancellationToken);
        if (!string.IsNullOrWhiteSpace(receipt.InvocationId) && receipt.InvocationId != safeInvocationId)
        {
            Fail($"receipt invocationId mismatch: got {receipt.InvocationId} want {safeInvocationId}");
        }
        if (Terminal(receipt.Status))
        {
            return receipt;
        }
        if (DateTimeOffset.UtcNow > deadline)
        {
            Fail($"receipt {safeInvocationId} did not reach a terminal status, last status={receipt.Status}");
        }
        await Task.Delay(TimeSpan.FromSeconds(2), cancellationToken);
    }
}

static Dictionary<string, object?> Payload(string raw)
{
    return JsonSerializer.Deserialize<Dictionary<string, object?>>(raw)
        ?? throw new InvalidOperationException("payload JSON must be an object");
}

static string PricingAmount(ServiceRecord service)
{
    return service.Pricing.HasValue && service.Pricing.Value.TryGetProperty("amount", out var amount)
        ? amount.GetString() ?? ""
        : "";
}

static bool Terminal(string? status)
{
    return string.Equals(status, "SUCCEEDED", StringComparison.OrdinalIgnoreCase)
        || string.Equals(status, "SETTLED", StringComparison.OrdinalIgnoreCase);
}

static bool DecimalEquals(string left, string right)
{
    return decimal.TryParse(left, NumberStyles.Number, CultureInfo.InvariantCulture, out var leftValue)
        && decimal.TryParse(right, NumberStyles.Number, CultureInfo.InvariantCulture, out var rightValue)
        && leftValue == rightValue;
}

static async Task ExpectFailure<TException>(Func<Task> action)
    where TException : Exception
{
    try
    {
        await action();
    }
    catch (TException)
    {
        return;
    }
    catch (Exception ex)
    {
        Fail($"expected {typeof(TException).Name}, got {ex.GetType().Name}: {ex.Message}");
    }
    Fail($"expected {typeof(TException).Name}");
}

static void Emit(
    string scenario,
    string? status = null,
    string? invocationId = null,
    string? chargedUsdc = null,
    string? receiptStatus = null,
    string? serviceId = null)
{
    var payload = new Dictionary<string, string?>
    {
        ["language"] = "dotnet",
        ["scenario"] = scenario,
        ["invocationId"] = invocationId,
        ["status"] = status,
        ["chargedUsdc"] = chargedUsdc,
        ["receiptStatus"] = receiptStatus,
        ["serviceId"] = serviceId,
    }.Where(item => !string.IsNullOrWhiteSpace(item.Value)).ToDictionary(item => item.Key, item => item.Value);
    Console.WriteLine(JsonSerializer.Serialize(payload));
}

static string RequireEnv(string name)
{
    var value = Environment.GetEnvironmentVariable(name);
    if (string.IsNullOrWhiteSpace(value))
    {
        Fail($"{name} is required");
        throw new InvalidOperationException("unreachable");
    }
    return value.Trim();
}

static string EnvDefault(string name, string fallback)
{
    var value = Environment.GetEnvironmentVariable(name);
    return string.IsNullOrWhiteSpace(value) ? fallback : value;
}

static int EnvInt(string name, int fallback)
{
    var value = Environment.GetEnvironmentVariable(name);
    return int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed) && parsed > 0
        ? parsed
        : fallback;
}

static bool EnvBool(string name)
{
    var value = Environment.GetEnvironmentVariable(name)?.Trim();
    return value is "1" or "true" or "TRUE" or "yes" or "YES" or "y" or "Y";
}

static string IdempotencyKey(string scenario)
{
    var runId = Environment.GetEnvironmentVariable("E2E_RUN_ID")?.Trim();
    var prefix = string.IsNullOrWhiteSpace(runId) ? "dotnet-e2e" : $"{runId}-dotnet-e2e";
    return $"{prefix}-{scenario}-{DateTimeOffset.UtcNow.ToUnixTimeMilliseconds().ToString(CultureInfo.InvariantCulture)}";
}

static string FirstNonBlank(params string?[] values)
{
    foreach (var value in values)
    {
        if (!string.IsNullOrWhiteSpace(value))
        {
            return value.Trim();
        }
    }
    return "";
}

static void Fail(string message)
{
    Console.Error.WriteLine("dotnet e2e failed: " + message);
    Environment.Exit(1);
}

internal sealed record FixedServiceTarget(string ServiceId, string CostUsdc, Dictionary<string, object?> Payload);
