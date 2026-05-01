using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using Nethereum.Signer;

namespace SynapseNetwork.Sdk;

public sealed class SynapseAuth
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private readonly string _walletAddress;
    private readonly string _gatewayUrl;
    private readonly HttpClient _httpClient;
    private readonly Func<string, string> _signer;
    private string? _token;
    private DateTimeOffset _tokenExpiresAt;

    public SynapseAuth(SynapseAuthOptions options)
    {
        _walletAddress = Require(options.WalletAddress, nameof(options.WalletAddress)).ToLowerInvariant();
        _gatewayUrl = SynapseClient.ResolveGatewayUrl(options.Environment, options.GatewayUrl);
        _httpClient = options.HttpClient ?? new HttpClient { Timeout = options.Timeout ?? TimeSpan.FromSeconds(30) };
        _signer = options.Signer ?? throw new ArgumentException("Signer is required");
    }

    public static SynapseAuth FromPrivateKey(string privateKey, SynapseAuthOptions? options = null)
    {
        var key = new EthECKey(privateKey);
        options ??= new SynapseAuthOptions();
        options.WalletAddress = key.GetPublicAddress();
        options.Signer = message => new EthereumMessageSigner().EncodeUTF8AndSign(message, key);
        return new SynapseAuth(options);
    }

    public SynapseProvider Provider() => new(this);

    public async Task<string> AuthenticateAsync(bool forceRefresh = false, CancellationToken cancellationToken = default)
    {
        if (!forceRefresh && !string.IsNullOrWhiteSpace(_token) && DateTimeOffset.UtcNow < _tokenExpiresAt.AddSeconds(-30))
        {
            return _token;
        }
        var challenge = await GetAsync<ChallengeResponse>("/api/v1/auth/challenge?address=" + Uri.EscapeDataString(_walletAddress), cancellationToken).ConfigureAwait(false);
        if (challenge.Success != true || string.IsNullOrWhiteSpace(challenge.Challenge))
        {
            throw new AuthenticationException("AUTH_CHALLENGE_FAILED", "Challenge request did not return a usable challenge.");
        }
        var token = await RequestAsync<TokenResponse>(
            HttpMethod.Post,
            "/api/v1/auth/verify",
            new Dictionary<string, object?> { ["wallet_address"] = _walletAddress, ["message"] = challenge.Challenge, ["signature"] = _signer(challenge.Challenge) },
            null,
            cancellationToken).ConfigureAwait(false);
        if (token.Success != true || string.IsNullOrWhiteSpace(token.AccessToken))
        {
            throw new AuthenticationException("AUTH_VERIFY_FAILED", "Auth verify did not return an access token.");
        }
        _token = token.AccessToken;
        _tokenExpiresAt = DateTimeOffset.UtcNow.AddSeconds(Math.Max(0, token.ExpiresIn));
        return _token;
    }

    public Task<string> GetTokenAsync(CancellationToken cancellationToken = default) => AuthenticateAsync(false, cancellationToken);

    public async Task<AuthLogoutResult> LogoutAsync(CancellationToken cancellationToken = default)
    {
        var result = await OwnerRequestAsync<AuthLogoutResult>(HttpMethod.Post, "/api/v1/auth/logout", null, cancellationToken).ConfigureAwait(false);
        _token = null;
        _tokenExpiresAt = default;
        return result;
    }

    public Task<OwnerProfile> GetOwnerProfileAsync(CancellationToken cancellationToken = default)
        => OwnerRequestAsync<OwnerProfile>(HttpMethod.Get, "/api/v1/auth/me", null, cancellationToken);

    public async Task<IssueCredentialResult> IssueCredentialAsync(CredentialOptions? options = null, CancellationToken cancellationToken = default)
    {
        var raw = await OwnerRequestAsync<JsonElement>(HttpMethod.Post, "/api/v1/credentials/agent/issue", CredentialBody(options), cancellationToken).ConfigureAwait(false);
        var credential = raw.TryGetProperty("credential", out var node) ? node.Deserialize<AgentCredential>(JsonOptions) ?? new AgentCredential() : new AgentCredential();
        var token = FirstText(GetString(raw, "token"), credential.Token, GetString(raw, "credential_token"));
        var id = FirstText(GetString(raw, "credential_id"), GetString(raw, "id"), credential.Id, credential.CredentialId);
        if (string.IsNullOrWhiteSpace(token) || string.IsNullOrWhiteSpace(id))
        {
            throw new AuthenticationException("CREDENTIAL_PAYLOAD_MISSING", raw.ToString());
        }
        return new IssueCredentialResult(credential with { Id = id, CredentialId = id, Token = token }, token);
    }

    public Task<IReadOnlyList<AgentCredential>> ListCredentialsAsync(CancellationToken cancellationToken = default)
        => CredentialListAsync("/api/v1/credentials/agent/list", cancellationToken);

    public Task<IReadOnlyList<AgentCredential>> ListActiveCredentialsAsync(CancellationToken cancellationToken = default)
        => CredentialListAsync("/api/v1/credentials/agent/list?active_only=true", cancellationToken);

    public Task<CredentialStatusResult> GetCredentialStatusAsync(string credentialId, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<CredentialStatusResult>(HttpMethod.Get, "/api/v1/credentials/agent/" + EscapeRequired(credentialId, "credentialId") + "/status", null, cancellationToken);

    public Task<CredentialStatusResult> CheckCredentialStatusAsync(string credentialId, CancellationToken cancellationToken = default)
        => GetCredentialStatusAsync(credentialId, cancellationToken);

    public Task<CredentialRevokeResult> RevokeCredentialAsync(string credentialId, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<CredentialRevokeResult>(HttpMethod.Post, "/api/v1/credentials/agent/" + EscapeRequired(credentialId, "credentialId") + "/revoke", null, cancellationToken);

    public Task<CredentialRotateResult> RotateCredentialAsync(string credentialId, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<CredentialRotateResult>(HttpMethod.Post, "/api/v1/credentials/agent/" + EscapeRequired(credentialId, "credentialId") + "/rotate", null, cancellationToken);

    public Task<CredentialDeleteResult> DeleteCredentialAsync(string credentialId, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<CredentialDeleteResult>(HttpMethod.Delete, "/api/v1/credentials/agent/" + EscapeRequired(credentialId, "credentialId"), null, cancellationToken);

    public Task<CredentialQuotaUpdateResult> UpdateCredentialQuotaAsync(string credentialId, CredentialQuotaOptions? options = null, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<CredentialQuotaUpdateResult>(HttpMethod.Patch, "/api/v1/credentials/agent/" + EscapeRequired(credentialId, "credentialId") + "/quota", QuotaBody(options), cancellationToken);

    public Task<CredentialAuditLogList> GetCredentialAuditLogsAsync(int limit = 100, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<CredentialAuditLogList>(HttpMethod.Get, QueryPath("/api/v1/credentials/agent/audit-logs", ("limit", Limit(limit))), null, cancellationToken);

    public async Task<string> EnsureCredentialAsync(string name, CredentialOptions? options = null, CancellationToken cancellationToken = default)
    {
        foreach (var credential in await ListActiveCredentialsAsync(cancellationToken).ConfigureAwait(false))
        {
            if (credential.Name == name)
            {
                if (!string.IsNullOrWhiteSpace(credential.Token)) return credential.Token;
                var rotated = await RotateCredentialAsync(FirstText(credential.CredentialId, credential.Id), cancellationToken).ConfigureAwait(false);
                return FirstText(rotated.Token, rotated.Credential?.Token);
            }
        }
        options ??= new CredentialOptions();
        options.Name = name;
        return (await IssueCredentialAsync(options, cancellationToken).ConfigureAwait(false)).Token;
    }

    public async Task<BalanceSummary> GetBalanceAsync(CancellationToken cancellationToken = default)
    {
        var raw = await OwnerRequestAsync<JsonElement>(HttpMethod.Get, "/api/v1/balance", null, cancellationToken).ConfigureAwait(false);
        var node = raw.TryGetProperty("balance", out var balance) ? balance : raw;
        return node.Deserialize<BalanceSummary>(JsonOptions) ?? new BalanceSummary();
    }

    public Task<DepositIntentResult> RegisterDepositIntentAsync(string txHash, string amountUsdc, string? idempotencyKey = null, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<DepositIntentResult>(HttpMethod.Post, "/api/v1/balance/deposit/intent", new Dictionary<string, object?> { ["txHash"] = txHash, ["amountUsdc"] = amountUsdc }, cancellationToken, Idempotency(idempotencyKey));

    public Task<DepositConfirmResult> ConfirmDepositAsync(string intentId, string eventKey, int confirmations = 1, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<DepositConfirmResult>(HttpMethod.Post, "/api/v1/balance/deposit/intents/" + EscapeRequired(intentId, "intentId") + "/confirm", new Dictionary<string, object?> { ["eventKey"] = eventKey, ["confirmations"] = confirmations }, cancellationToken);

    public Task SetSpendingLimitAsync(string? spendingLimitUsdc, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<JsonElement>(HttpMethod.Put, "/api/v1/balance/spending-limit", spendingLimitUsdc == null ? new Dictionary<string, object?> { ["allowUnlimited"] = true } : new Dictionary<string, object?> { ["spendingLimitUsdc"] = spendingLimitUsdc, ["allowUnlimited"] = false }, cancellationToken);

    public Task<VoucherRedeemResult> RedeemVoucherAsync(string voucherCode, string? idempotencyKey = null, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<VoucherRedeemResult>(HttpMethod.Post, "/api/v1/balance/vouchers/redeem", new Dictionary<string, object?> { ["voucherCode"] = Require(voucherCode, "voucherCode") }, cancellationToken, Idempotency(idempotencyKey));

    public Task<UsageLogList> GetUsageLogsAsync(int limit = 100, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<UsageLogList>(HttpMethod.Get, QueryPath("/api/v1/usage/logs", ("limit", Limit(limit))), null, cancellationToken);

    public Task<FinanceAuditLogList> GetFinanceAuditLogsAsync(int limit = 100, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<FinanceAuditLogList>(HttpMethod.Get, QueryPath("/api/v1/finance/audit-logs", ("limit", Limit(limit))), null, cancellationToken);

    public Task<RiskOverview> GetRiskOverviewAsync(CancellationToken cancellationToken = default)
        => OwnerRequestAsync<RiskOverview>(HttpMethod.Get, "/api/v1/finance/risk-overview", null, cancellationToken);

    public Task<IssueProviderSecretResult> IssueProviderSecretAsync(CredentialOptions? options = null, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<IssueProviderSecretResult>(HttpMethod.Post, "/api/v1/secrets/provider/issue", CredentialBody(options), cancellationToken);

    public async Task<IReadOnlyList<ProviderSecret>> ListProviderSecretsAsync(CancellationToken cancellationToken = default)
        => ReadList<ProviderSecret>(await OwnerRequestAsync<JsonElement>(HttpMethod.Get, "/api/v1/secrets/provider/list", null, cancellationToken).ConfigureAwait(false), "secrets");

    public Task<ProviderSecretDeleteResult> DeleteProviderSecretAsync(string secretId, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<ProviderSecretDeleteResult>(HttpMethod.Delete, "/api/v1/secrets/provider/" + EscapeRequired(secretId, "secretId"), null, cancellationToken);

    public Task<RegisterProviderServiceResult> RegisterProviderServiceAsync(RegisterProviderServiceOptions options, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<RegisterProviderServiceResult>(HttpMethod.Post, "/api/v1/services", ProviderServiceBody(options), cancellationToken);

    public async Task<IReadOnlyList<ProviderServiceRecord>> ListProviderServicesAsync(CancellationToken cancellationToken = default)
        => ReadList<ProviderServiceRecord>(await OwnerRequestAsync<JsonElement>(HttpMethod.Get, "/api/v1/services", null, cancellationToken).ConfigureAwait(false), "services");

    public Task<ProviderRegistrationGuide> GetRegistrationGuideAsync(CancellationToken cancellationToken = default)
        => OwnerRequestAsync<ProviderRegistrationGuide>(HttpMethod.Get, "/api/v1/services/registration-guide", null, cancellationToken);

    public Task<ServiceManifestDraft> ParseCurlToServiceManifestAsync(string curlCommand, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<ServiceManifestDraft>(HttpMethod.Post, "/api/v1/services/parse-curl", new Dictionary<string, object?> { ["curlCommand"] = Require(curlCommand, "curlCommand") }, cancellationToken);

    public Task<ProviderServiceUpdateResult> UpdateProviderServiceAsync(string serviceRecordId, IReadOnlyDictionary<string, object?> patch, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<ProviderServiceUpdateResult>(HttpMethod.Put, "/api/v1/services/" + EscapeRequired(serviceRecordId, "serviceRecordId"), patch, cancellationToken);

    public Task<ProviderServiceDeleteResult> DeleteProviderServiceAsync(string serviceRecordId, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<ProviderServiceDeleteResult>(HttpMethod.Delete, "/api/v1/services/" + EscapeRequired(serviceRecordId, "serviceRecordId"), null, cancellationToken);

    public Task<ProviderServicePingResult> PingProviderServiceAsync(string serviceRecordId, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<ProviderServicePingResult>(HttpMethod.Post, "/api/v1/services/" + EscapeRequired(serviceRecordId, "serviceRecordId") + "/ping", null, cancellationToken);

    public Task<ProviderServiceHealthHistory> GetProviderServiceHealthHistoryAsync(string serviceRecordId, int limit = 100, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<ProviderServiceHealthHistory>(HttpMethod.Get, QueryPath("/api/v1/services/" + EscapeRequired(serviceRecordId, "serviceRecordId") + "/health/history", ("limitPerTarget", Limit(limit))), null, cancellationToken);

    public Task<ProviderEarningsSummary> GetProviderEarningsSummaryAsync(CancellationToken cancellationToken = default)
        => OwnerRequestAsync<ProviderEarningsSummary>(HttpMethod.Get, "/api/v1/providers/earnings/summary", null, cancellationToken);

    public Task<ProviderWithdrawalCapability> GetProviderWithdrawalCapabilityAsync(CancellationToken cancellationToken = default)
        => OwnerRequestAsync<ProviderWithdrawalCapability>(HttpMethod.Get, "/api/v1/providers/withdrawals/capability", null, cancellationToken);

    public Task<ProviderWithdrawalIntentResult> CreateProviderWithdrawalIntentAsync(string amountUsdc, string? idempotencyKey = null, string? destinationAddress = null, CancellationToken cancellationToken = default)
    {
        var body = new Dictionary<string, object?> { ["amountUsdc"] = Require(amountUsdc, "amountUsdc") };
        if (!string.IsNullOrWhiteSpace(destinationAddress)) body["destinationAddress"] = destinationAddress;
        return OwnerRequestAsync<ProviderWithdrawalIntentResult>(HttpMethod.Post, "/api/v1/providers/withdrawals/intent", body, cancellationToken, Idempotency(idempotencyKey));
    }

    public Task<ProviderWithdrawalList> ListProviderWithdrawalsAsync(int limit = 100, CancellationToken cancellationToken = default)
        => OwnerRequestAsync<ProviderWithdrawalList>(HttpMethod.Get, QueryPath("/api/v1/providers/withdrawals", ("limit", Limit(limit))), null, cancellationToken);

    public async Task<ProviderServiceRecord> GetProviderServiceAsync(string serviceId, CancellationToken cancellationToken = default)
    {
        foreach (var service in await ListProviderServicesAsync(cancellationToken).ConfigureAwait(false))
        {
            if (service.ServiceId == serviceId) return service;
        }
        throw new AuthenticationException("SERVICE_NOT_FOUND", "Provider service not found: " + serviceId);
    }

    public async Task<ProviderServiceStatus> GetProviderServiceStatusAsync(string serviceId, CancellationToken cancellationToken = default)
    {
        var service = await GetProviderServiceAsync(serviceId, cancellationToken).ConfigureAwait(false);
        return new ProviderServiceStatus(service.ServiceId ?? service.Id ?? serviceId, service.Status ?? "unknown", service.RuntimeAvailable ?? false, service.Health);
    }

    private async Task<IReadOnlyList<AgentCredential>> CredentialListAsync(string path, CancellationToken cancellationToken)
        => ReadList<AgentCredential>(await OwnerRequestAsync<JsonElement>(HttpMethod.Get, path, null, cancellationToken).ConfigureAwait(false), "credentials");

    private async Task<T> GetAsync<T>(string path, CancellationToken cancellationToken)
        => await RequestAsync<T>(HttpMethod.Get, path, null, null, cancellationToken).ConfigureAwait(false);

    private async Task<T> OwnerRequestAsync<T>(HttpMethod method, string path, object? body, CancellationToken cancellationToken, IReadOnlyDictionary<string, string>? extraHeaders = null)
    {
        var headers = new Dictionary<string, string>(extraHeaders ?? new Dictionary<string, string>())
        {
            ["Authorization"] = "Bearer " + await GetTokenAsync(cancellationToken).ConfigureAwait(false),
        };
        return await RequestAsync<T>(method, path, body, headers, cancellationToken).ConfigureAwait(false);
    }

    private async Task<T> RequestAsync<T>(HttpMethod method, string path, object? body, IReadOnlyDictionary<string, string>? headers, CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(method, _gatewayUrl + path);
        request.Headers.Add("Accept", "application/json");
        foreach (var header in headers ?? new Dictionary<string, string>()) request.Headers.Add(header.Key, header.Value);
        if (body != null) request.Content = JsonContent.Create(body, options: JsonOptions);
        using var response = await _httpClient.SendAsync(request, cancellationToken).ConfigureAwait(false);
        var text = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
        if (!response.IsSuccessStatusCode) throw MapError(response.StatusCode, text);
        return JsonSerializer.Deserialize<T>(string.IsNullOrWhiteSpace(text) ? "{}" : text, JsonOptions)
            ?? throw new SynapseException("EMPTY_RESPONSE", "Gateway returned an empty response.");
    }

    private static Exception MapError(HttpStatusCode statusCode, string text)
    {
        using var document = JsonDocument.Parse(string.IsNullOrWhiteSpace(text) ? "{}" : text);
        var detail = document.RootElement.TryGetProperty("detail", out var node) ? node : document.RootElement;
        var code = detail.TryGetProperty("code", out var codeNode) ? codeNode.GetString() ?? "" : "";
        var message = detail.TryGetProperty("message", out var msgNode) ? msgNode.GetString() ?? text : text;
        return statusCode switch
        {
            HttpStatusCode.Unauthorized => new AuthenticationException(code, message),
            HttpStatusCode.PaymentRequired => new BudgetException(code, message),
            _ => new InvokeException(code, message),
        };
    }

    private Dictionary<string, object?> ProviderServiceBody(RegisterProviderServiceOptions options)
    {
        var kind = FirstText(options.ServiceKind, "api");
        var priceModel = FirstText(options.PriceModel, kind == "llm" ? "token_metered" : "fixed");
        var serviceId = FirstText(options.ServiceId, DefaultServiceId(options.ServiceName));
        return new Dictionary<string, object?>
        {
            ["serviceId"] = serviceId,
            ["agentToolName"] = serviceId,
            ["serviceName"] = Require(options.ServiceName, "serviceName"),
            ["serviceKind"] = kind,
            ["priceModel"] = priceModel,
            ["role"] = "Provider",
            ["status"] = FirstText(options.Status, "active"),
            ["isActive"] = options.IsActive ?? true,
            ["pricing"] = ProviderPricing(options, priceModel),
            ["summary"] = Require(options.DescriptionForModel, "descriptionForModel"),
            ["tags"] = options.Tags ?? Array.Empty<string>(),
            ["auth"] = new Dictionary<string, object?> { ["type"] = "gateway_signed" },
            ["invoke"] = new Dictionary<string, object?> { ["method"] = FirstText(options.EndpointMethod, "POST"), ["targets"] = new[] { new Dictionary<string, object?> { ["url"] = Require(options.EndpointUrl, "endpointUrl") } }, ["timeoutMs"] = options.RequestTimeoutMs ?? 15000 },
            ["healthCheck"] = new Dictionary<string, object?> { ["path"] = FirstText(options.HealthPath, "/health"), ["method"] = FirstText(options.HealthMethod, "GET"), ["timeoutMs"] = options.HealthTimeoutMs ?? 3000, ["successCodes"] = new[] { 200 } },
            ["providerProfile"] = new Dictionary<string, object?> { ["displayName"] = FirstText(options.ProviderDisplayName, options.ServiceName) },
            ["payoutAccount"] = new Dictionary<string, object?> { ["payoutAddress"] = FirstText(options.PayoutAddress, _walletAddress), ["chainId"] = options.ChainId ?? 31337, ["settlementCurrency"] = FirstText(options.SettlementCurrency, "USDC") },
            ["governance"] = new Dictionary<string, object?> { ["termsAccepted"] = true, ["riskAcknowledged"] = true },
        };
    }

    private static Dictionary<string, object?> ProviderPricing(RegisterProviderServiceOptions options, string priceModel)
        => priceModel == "token_metered"
            ? new Dictionary<string, object?> { ["priceModel"] = "token_metered", ["inputPricePer1MTokensUsdc"] = Require(options.InputPricePer1MTokensUsdc, "inputPricePer1MTokensUsdc"), ["outputPricePer1MTokensUsdc"] = Require(options.OutputPricePer1MTokensUsdc, "outputPricePer1MTokensUsdc"), ["currency"] = "USDC" }
            : new Dictionary<string, object?> { ["amount"] = Require(options.BasePriceUsdc, "basePriceUsdc"), ["currency"] = "USDC" };

    private static Dictionary<string, object?> CredentialBody(CredentialOptions? options)
    {
        var body = new Dictionary<string, object?>();
        if (options == null) return body;
        Put(body, "name", options.Name);
        Put(body, "maxCalls", options.MaxCalls);
        Put(body, "creditLimit", options.CreditLimit);
        Put(body, "resetInterval", options.ResetInterval);
        Put(body, "rpm", options.Rpm);
        Put(body, "expiresInSec", options.ExpiresInSec);
        return body;
    }

    private static Dictionary<string, object?> QuotaBody(CredentialQuotaOptions? options)
    {
        var body = new Dictionary<string, object?>();
        if (options == null) return body;
        Put(body, "maxCalls", options.MaxCalls);
        Put(body, "rpm", options.Rpm);
        Put(body, "creditLimit", options.CreditLimit);
        Put(body, "resetInterval", options.ResetInterval);
        Put(body, "expiresAt", options.ExpiresAt);
        return body;
    }

    private static IReadOnlyDictionary<string, string> Idempotency(string? value)
        => new Dictionary<string, string> { ["X-Idempotency-Key"] = string.IsNullOrWhiteSpace(value) ? "dotnet-" + DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() : value };

    private static IReadOnlyList<T> ReadList<T>(JsonElement root, string property)
    {
        if (!root.TryGetProperty(property, out var array) || array.ValueKind != JsonValueKind.Array) return Array.Empty<T>();
        return array.EnumerateArray().Select(item => item.Deserialize<T>(JsonOptions)!).Where(item => item != null).ToArray();
    }

    private static string QueryPath(string path, params (string Key, object Value)[] pairs)
        => path + "?" + string.Join("&", pairs.Select(item => Uri.EscapeDataString(item.Key) + "=" + Uri.EscapeDataString(Convert.ToString(item.Value, System.Globalization.CultureInfo.InvariantCulture) ?? "")));

    private static string EscapeRequired(string value, string name) => Uri.EscapeDataString(Require(value, name));
    private static int Limit(int limit) => limit <= 0 ? 100 : limit;
    private static string Require(string? value, string name) => string.IsNullOrWhiteSpace(value) ? throw new ArgumentException($"{name} is required") : value.Trim();
    private static string FirstText(params string?[] values) => values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value))?.Trim() ?? "";
    private static string DefaultServiceId(string name) => new string(Require(name, "serviceName").ToLowerInvariant().Select(ch => char.IsLetterOrDigit(ch) ? ch : '_').ToArray()).Trim('_');
    private static string GetString(JsonElement root, string property) => root.TryGetProperty(property, out var node) ? node.GetString() ?? "" : "";
    private static void Put(Dictionary<string, object?> body, string key, object? value)
    {
        if (value != null && !string.IsNullOrWhiteSpace(Convert.ToString(value)) && Convert.ToString(value) != "0") body[key] = value;
    }
}

public sealed record SynapseAuthOptions
{
    public string? WalletAddress { get; set; }
    public Func<string, string>? Signer { get; set; }
    public string? Environment { get; set; }
    public string? GatewayUrl { get; set; }
    public TimeSpan? Timeout { get; set; }
    public HttpClient? HttpClient { get; set; }
}

public sealed record CredentialOptions { public string? Name { get; set; } public int? MaxCalls { get; set; } public string? CreditLimit { get; set; } public string? ResetInterval { get; set; } public int? Rpm { get; set; } public int? ExpiresInSec { get; set; } }
public sealed record CredentialQuotaOptions { public int? MaxCalls { get; set; } public int? Rpm { get; set; } public string? CreditLimit { get; set; } public string? ResetInterval { get; set; } public string? ExpiresAt { get; set; } }
public sealed record RegisterProviderServiceOptions { public string? ServiceName { get; set; } public string? EndpointUrl { get; set; } public string? BasePriceUsdc { get; set; } public string? DescriptionForModel { get; set; } public string? ServiceKind { get; set; } public string? PriceModel { get; set; } public string? InputPricePer1MTokensUsdc { get; set; } public string? OutputPricePer1MTokensUsdc { get; set; } public string? ServiceId { get; set; } public string? ProviderDisplayName { get; set; } public string? PayoutAddress { get; set; } public int? ChainId { get; set; } public string? SettlementCurrency { get; set; } public IReadOnlyList<string>? Tags { get; set; } public string? Status { get; set; } public bool? IsActive { get; set; } public string? EndpointMethod { get; set; } public string? HealthPath { get; set; } public string? HealthMethod { get; set; } public int? HealthTimeoutMs { get; set; } public int? RequestTimeoutMs { get; set; } }
public sealed record ChallengeResponse(bool? Success, string? Challenge, string? Domain);
public sealed record TokenResponse(bool? Success, [property: JsonPropertyName("access_token")] string? AccessToken, [property: JsonPropertyName("token_type")] string? TokenType, [property: JsonPropertyName("expires_in")] long ExpiresIn);
public sealed record AuthLogoutResult(string? Status, bool? Success);
public sealed record OwnerProfile(string? OwnerAddress, string? WalletAddress, JsonElement? Profile);
public sealed record AgentCredential(string? Id = null, [property: JsonPropertyName("credential_id")] string? CredentialId = null, string? Token = null, string? Name = null, string? Status = null);
public sealed record IssueCredentialResult(AgentCredential Credential, string Token);
public sealed record CredentialStatusResult(string? Status, string? CredentialId, bool? Valid, string? CredentialStatus);
public sealed record CredentialRevokeResult(string? Status, string? CredentialId, AgentCredential? Credential);
public sealed record CredentialRotateResult(string? Status, string? CredentialId, string? Token, AgentCredential? Credential);
public sealed record CredentialDeleteResult(string? Status, string? CredentialId);
public sealed record CredentialQuotaUpdateResult(string? Status, string? CredentialId, AgentCredential? Credential);
public sealed record CredentialAuditLogList(IReadOnlyList<JsonElement>? Logs);
public sealed record BalanceSummary(JsonElement? OwnerBalance = null, JsonElement? ConsumerAvailableBalance = null, JsonElement? ProviderReceivable = null, JsonElement? PlatformFeeAccrued = null);
public sealed record DepositIntentResult(string? Status, [property: JsonPropertyName("tx_hash")] string? TxHash, JsonElement? Intent);
public sealed record DepositConfirmResult(string? Status, JsonElement? Intent);
public sealed record VoucherRedeemResult(string? Status, string? VoucherCode);
public sealed record UsageLogList(IReadOnlyList<JsonElement>? Logs);
public sealed record FinanceAuditLogList(IReadOnlyList<JsonElement>? Logs);
public sealed record RiskOverview(JsonElement? Risk);
public sealed record ProviderSecret(string? Id, string? Name, string? OwnerAddress, string? SecretKey, string? MaskedKey, string? Status);
public sealed record IssueProviderSecretResult(string? Status, ProviderSecret Secret);
public sealed record ProviderSecretDeleteResult(string? Status, string? SecretId);
public sealed record ProviderServiceRecord(string? ServiceId, string? Id, string? ServiceName, string? Status, bool? RuntimeAvailable, JsonElement? Health);
public sealed record RegisterProviderServiceResult(string? Status, string? ServiceId, ProviderServiceRecord? Service);
public sealed record ProviderServiceStatus(string ServiceId, string LifecycleStatus, bool RuntimeAvailable, JsonElement? Health);
public sealed record ProviderRegistrationGuide(IReadOnlyList<JsonElement>? Steps, JsonElement? Requirements);
public sealed record ServiceManifestDraft(JsonElement? Data, JsonElement? Manifest);
public sealed record ProviderServiceUpdateResult(string? Status, ProviderServiceRecord? Service);
public sealed record ProviderServiceDeleteResult(string? Status, string? ServiceId);
public sealed record ProviderServicePingResult(string? Status, JsonElement? Health);
public sealed record ProviderServiceHealthHistory(IReadOnlyList<JsonElement>? History);
public sealed record ProviderEarningsSummary(JsonElement? Total);
public sealed record ProviderWithdrawalCapability(bool? Available);
public sealed record ProviderWithdrawalIntentResult(string? Status, string? IntentId, JsonElement? AmountUsdc, JsonElement? Intent);
public sealed record ProviderWithdrawalList(IReadOnlyList<JsonElement>? Withdrawals);
