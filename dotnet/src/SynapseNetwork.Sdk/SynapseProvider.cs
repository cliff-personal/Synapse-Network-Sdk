namespace SynapseNetwork.Sdk;

public sealed class SynapseProvider(SynapseAuth auth)
{
    public Task<IssueProviderSecretResult> IssueSecretAsync(CredentialOptions? options = null, CancellationToken cancellationToken = default)
        => auth.IssueProviderSecretAsync(options, cancellationToken);

    public Task<IReadOnlyList<ProviderSecret>> ListSecretsAsync(CancellationToken cancellationToken = default)
        => auth.ListProviderSecretsAsync(cancellationToken);

    public Task<ProviderSecretDeleteResult> DeleteSecretAsync(string secretId, CancellationToken cancellationToken = default)
        => auth.DeleteProviderSecretAsync(secretId, cancellationToken);

    public Task<ProviderRegistrationGuide> GetRegistrationGuideAsync(CancellationToken cancellationToken = default)
        => auth.GetRegistrationGuideAsync(cancellationToken);

    public Task<ServiceManifestDraft> ParseCurlToServiceManifestAsync(string curlCommand, CancellationToken cancellationToken = default)
        => auth.ParseCurlToServiceManifestAsync(curlCommand, cancellationToken);

    public Task<RegisterProviderServiceResult> RegisterServiceAsync(RegisterProviderServiceOptions options, CancellationToken cancellationToken = default)
        => auth.RegisterProviderServiceAsync(options, cancellationToken);

    public Task<RegisterProviderServiceResult> RegisterLlmServiceAsync(RegisterProviderServiceOptions options, CancellationToken cancellationToken = default)
    {
        options.ServiceKind = "llm";
        options.PriceModel = "token_metered";
        return auth.RegisterProviderServiceAsync(options, cancellationToken);
    }

    public Task<IReadOnlyList<ProviderServiceRecord>> ListServicesAsync(CancellationToken cancellationToken = default)
        => auth.ListProviderServicesAsync(cancellationToken);

    public Task<ProviderServiceRecord> GetServiceAsync(string serviceId, CancellationToken cancellationToken = default)
        => auth.GetProviderServiceAsync(serviceId, cancellationToken);

    public Task<ProviderServiceStatus> GetServiceStatusAsync(string serviceId, CancellationToken cancellationToken = default)
        => auth.GetProviderServiceStatusAsync(serviceId, cancellationToken);

    public Task<ProviderServiceUpdateResult> UpdateServiceAsync(string serviceRecordId, IReadOnlyDictionary<string, object?> patch, CancellationToken cancellationToken = default)
        => auth.UpdateProviderServiceAsync(serviceRecordId, patch, cancellationToken);

    public Task<ProviderServiceDeleteResult> DeleteServiceAsync(string serviceRecordId, CancellationToken cancellationToken = default)
        => auth.DeleteProviderServiceAsync(serviceRecordId, cancellationToken);

    public Task<ProviderServicePingResult> PingServiceAsync(string serviceRecordId, CancellationToken cancellationToken = default)
        => auth.PingProviderServiceAsync(serviceRecordId, cancellationToken);

    public Task<ProviderServiceHealthHistory> GetServiceHealthHistoryAsync(string serviceRecordId, int limit = 100, CancellationToken cancellationToken = default)
        => auth.GetProviderServiceHealthHistoryAsync(serviceRecordId, limit, cancellationToken);

    public Task<ProviderEarningsSummary> GetEarningsSummaryAsync(CancellationToken cancellationToken = default)
        => auth.GetProviderEarningsSummaryAsync(cancellationToken);

    public Task<ProviderWithdrawalCapability> GetWithdrawalCapabilityAsync(CancellationToken cancellationToken = default)
        => auth.GetProviderWithdrawalCapabilityAsync(cancellationToken);

    public Task<ProviderWithdrawalIntentResult> CreateWithdrawalIntentAsync(string amountUsdc, string? idempotencyKey = null, string? destinationAddress = null, CancellationToken cancellationToken = default)
        => auth.CreateProviderWithdrawalIntentAsync(amountUsdc, idempotencyKey, destinationAddress, cancellationToken);

    public Task<ProviderWithdrawalList> ListWithdrawalsAsync(int limit = 100, CancellationToken cancellationToken = default)
        => auth.ListProviderWithdrawalsAsync(limit, cancellationToken);
}
