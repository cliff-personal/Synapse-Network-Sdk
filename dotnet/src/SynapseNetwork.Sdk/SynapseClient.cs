using System.Globalization;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace SynapseNetwork.Sdk;

public sealed class SynapseClient
{
    public const string DefaultEnvironment = "staging";
    public const string StagingGatewayUrl = "https://api-staging.synapse-network.ai";
    public const string ProdGatewayUrl = "https://api.synapse-network.ai";

    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly string _credential;
    private readonly string _gatewayUrl;
    private readonly HttpClient _httpClient;

    public SynapseClient(SynapseClientOptions options)
    {
        _credential = Require(options.Credential, nameof(options.Credential));
        _gatewayUrl = ResolveGatewayUrl(options.Environment, options.GatewayUrl);
        _httpClient = options.HttpClient ?? new HttpClient { Timeout = options.Timeout ?? TimeSpan.FromSeconds(30) };
    }

    public static string ResolveGatewayUrl(string? environment = null, string? gatewayUrl = null)
    {
        if (!string.IsNullOrWhiteSpace(gatewayUrl))
        {
            return gatewayUrl.Trim().TrimEnd('/');
        }

        return (string.IsNullOrWhiteSpace(environment) ? DefaultEnvironment : environment.Trim().ToLowerInvariant()) switch
        {
            "staging" => StagingGatewayUrl,
            "prod" => ProdGatewayUrl,
            var value => throw new ArgumentException($"unsupported Synapse environment: {value}"),
        };
    }

    public async Task<IReadOnlyList<ServiceRecord>> SearchAsync(
        string query,
        SearchOptions? options = null,
        CancellationToken cancellationToken = default)
    {
        options ??= new SearchOptions();
        var pageSize = Math.Max(1, options.Limit ?? 20);
        var offset = Math.Max(0, options.Offset ?? 0);
        var body = new Dictionary<string, object?>
        {
            ["tags"] = options.Tags ?? Array.Empty<string>(),
            ["page"] = (offset / pageSize) + 1,
            ["pageSize"] = pageSize,
            ["sort"] = string.IsNullOrWhiteSpace(options.Sort) ? "best_match" : options.Sort,
        };
        if (!string.IsNullOrWhiteSpace(query))
        {
            body["query"] = query.Trim();
        }

        var response = await PostAsync<DiscoveryResponse>(
            "/api/v1/agent/discovery/search",
            body,
            options.RequestId,
            cancellationToken).ConfigureAwait(false);
        return response.Results ?? response.Services ?? Array.Empty<ServiceRecord>();
    }

    public Task<IReadOnlyList<ServiceRecord>> DiscoverAsync(SearchOptions? options = null, CancellationToken cancellationToken = default)
    {
        return SearchAsync("", options, cancellationToken);
    }

    public Task<InvocationResult> InvokeAsync(
        string serviceId,
        IReadOnlyDictionary<string, object?>? payload,
        InvokeOptions options,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(options.CostUsdc))
        {
            throw new ArgumentException("CostUsdc is required for fixed-price API services; use InvokeLlmAsync for LLM services.");
        }
        var body = InvocationBody(serviceId, payload, options.IdempotencyKey, options.ResponseMode);
        body["costUsdc"] = options.CostUsdc;
        return PostAsync<InvocationResult>("/api/v1/agent/invoke", body, options.RequestId, cancellationToken);
    }

    public Task<InvocationResult> InvokeLlmAsync(
        string serviceId,
        IReadOnlyDictionary<string, object?>? payload,
        LlmInvokeOptions? options = null,
        CancellationToken cancellationToken = default)
    {
        options ??= new LlmInvokeOptions();
        if (payload != null && payload.TryGetValue("stream", out var stream) && stream is true)
        {
            throw new InvokeException("LLM_STREAMING_NOT_SUPPORTED", "stream=true is not supported for token-metered billing.");
        }
        var body = InvocationBody(serviceId, payload, options.IdempotencyKey, "sync");
        if (!string.IsNullOrWhiteSpace(options.MaxCostUsdc))
        {
            body["maxCostUsdc"] = options.MaxCostUsdc;
        }
        return PostAsync<InvocationResult>("/api/v1/agent/invoke", body, options.RequestId, cancellationToken);
    }

    public Task<InvocationResult> GetInvocationAsync(string invocationId, CancellationToken cancellationToken = default)
    {
        return GetAsync<InvocationResult>(
            "/api/v1/agent/invocations/" + Uri.EscapeDataString(Require(invocationId, nameof(invocationId))),
            cancellationToken);
    }

    public Task<JsonElement> HealthAsync(CancellationToken cancellationToken = default)
    {
        return GetAsync<JsonElement>("/health", cancellationToken);
    }

    private Dictionary<string, object?> InvocationBody(
        string serviceId,
        IReadOnlyDictionary<string, object?>? payload,
        string? idempotencyKey,
        string? responseMode)
    {
        return new Dictionary<string, object?>
        {
            ["serviceId"] = Require(serviceId, nameof(serviceId)),
            ["idempotencyKey"] = string.IsNullOrWhiteSpace(idempotencyKey) ? Guid.NewGuid().ToString("N") : idempotencyKey,
            ["payload"] = new Dictionary<string, object?> { ["body"] = payload ?? new Dictionary<string, object?>() },
            ["responseMode"] = string.IsNullOrWhiteSpace(responseMode) ? "sync" : responseMode,
        };
    }

    private async Task<T> GetAsync<T>(string path, CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, _gatewayUrl + path);
        request.Headers.Add("X-Credential", _credential);
        return await SendAsync<T>(request, cancellationToken).ConfigureAwait(false);
    }

    private async Task<T> PostAsync<T>(
        string path,
        IReadOnlyDictionary<string, object?> body,
        string? requestId,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, _gatewayUrl + path);
        request.Headers.Add("X-Credential", _credential);
        if (!string.IsNullOrWhiteSpace(requestId))
        {
            request.Headers.Add("X-Request-Id", requestId);
        }
        request.Content = JsonContent.Create(body, options: JsonOptions);
        return await SendAsync<T>(request, cancellationToken).ConfigureAwait(false);
    }

    private async Task<T> SendAsync<T>(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        using var response = await _httpClient.SendAsync(request, cancellationToken).ConfigureAwait(false);
        var text = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
        if (!response.IsSuccessStatusCode)
        {
            throw MapError(response.StatusCode, text);
        }
        return JsonSerializer.Deserialize<T>(text, JsonOptions)
            ?? throw new SynapseException("EMPTY_RESPONSE", "Gateway returned an empty response.");
    }

    private static Exception MapError(HttpStatusCode statusCode, string text)
    {
        var detail = ErrorDetail(text);
        var code = GetStringProperty(detail, "code");
        var message = GetStringProperty(detail, "message");
        if (string.IsNullOrWhiteSpace(message))
        {
            message = text;
        }
        return statusCode switch
        {
            HttpStatusCode.Unauthorized => new AuthenticationException(code, message),
            HttpStatusCode.PaymentRequired => new BudgetException(code, message),
            HttpStatusCode.UnprocessableEntity when code == "PRICE_MISMATCH" => new PriceMismatchException(
                message,
                GetStringProperty(detail, "expectedPriceUsdc"),
                GetStringProperty(detail, "currentPriceUsdc")),
            _ => new InvokeException(code, message),
        };
    }

    private static JsonElement ErrorDetail(string text)
    {
        try
        {
            using var document = JsonDocument.Parse(string.IsNullOrWhiteSpace(text) ? "{}" : text);
            var root = document.RootElement;
            if (root.ValueKind == JsonValueKind.Object && root.TryGetProperty("detail", out var detail))
            {
                return detail.Clone();
            }
            return root.ValueKind == JsonValueKind.Object ? root.Clone() : EmptyObject();
        }
        catch (JsonException)
        {
            return EmptyObject();
        }
    }

    private static JsonElement EmptyObject()
    {
        using var document = JsonDocument.Parse("{}");
        return document.RootElement.Clone();
    }

    private static string GetStringProperty(JsonElement value, string name)
    {
        return value.ValueKind == JsonValueKind.Object && value.TryGetProperty(name, out var node)
            ? node.GetString() ?? ""
            : "";
    }

    private static string Require(string? value, string name)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new ArgumentException($"{name} is required");
        }
        return value.Trim();
    }
}

public sealed record SynapseClientOptions
{
    public required string Credential { get; init; }
    public string? Environment { get; init; }
    public string? GatewayUrl { get; init; }
    public TimeSpan? Timeout { get; init; }
    public HttpClient? HttpClient { get; init; }
}

public sealed record SearchOptions
{
    public int? Limit { get; init; }
    public int? Offset { get; init; }
    public IReadOnlyList<string>? Tags { get; init; }
    public string? Sort { get; init; }
    public string? RequestId { get; init; }
}

public sealed record InvokeOptions
{
    public required string CostUsdc { get; init; }
    public string? IdempotencyKey { get; init; }
    public string? ResponseMode { get; init; }
    public string? RequestId { get; init; }
}

public sealed record LlmInvokeOptions
{
    public string? MaxCostUsdc { get; init; }
    public string? IdempotencyKey { get; init; }
    public string? RequestId { get; init; }
}

public sealed record ServiceRecord
{
    public string? ServiceId { get; init; }
    public string? Id { get; init; }
    public string? ServiceName { get; init; }
    public string? Status { get; init; }
    public string? ServiceKind { get; init; }
    public string? PriceModel { get; init; }
    public JsonElement? Pricing { get; init; }
    public string? Summary { get; init; }
    public IReadOnlyList<string>? Tags { get; init; }
}

public sealed record InvocationResult
{
    public string? InvocationId { get; init; }
    public string? Status { get; init; }
    public string? ChargedUsdc { get; init; }
    public JsonElement? Result { get; init; }
    public JsonElement? Usage { get; init; }
    public JsonElement? Synapse { get; init; }
    public JsonElement? Error { get; init; }
    public JsonElement? Receipt { get; init; }
}

internal sealed record DiscoveryResponse
{
    public IReadOnlyList<ServiceRecord>? Services { get; init; }
    public IReadOnlyList<ServiceRecord>? Results { get; init; }
}

public class SynapseException(string code, string message) : Exception(message)
{
    public string Code { get; } = code;
}

public sealed class AuthenticationException(string code, string message) : SynapseException(code, message);

public sealed class BudgetException(string code, string message) : SynapseException(code, message);

public class InvokeException(string code, string message) : SynapseException(code, message);

public sealed class PriceMismatchException(string message, string expectedPriceUsdc, string currentPriceUsdc)
    : InvokeException("PRICE_MISMATCH", message)
{
    public decimal ExpectedPriceUsdc { get; } = string.IsNullOrWhiteSpace(expectedPriceUsdc)
        ? 0m
        : decimal.Parse(expectedPriceUsdc, CultureInfo.InvariantCulture);

    public decimal CurrentPriceUsdc { get; } = string.IsNullOrWhiteSpace(currentPriceUsdc)
        ? 0m
        : decimal.Parse(currentPriceUsdc, CultureInfo.InvariantCulture);
}
