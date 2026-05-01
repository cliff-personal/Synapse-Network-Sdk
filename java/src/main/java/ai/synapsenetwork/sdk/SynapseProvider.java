package ai.synapsenetwork.sdk;

import java.util.List;
import java.util.Map;

public final class SynapseProvider {
  private final SynapseAuth auth;

  SynapseProvider(SynapseAuth auth) {
    this.auth = auth;
  }

  public SynapseAuth.IssueProviderSecretResult issueSecret(SynapseAuth.CredentialOptions options) {
    return auth.issueProviderSecret(options);
  }

  public List<SynapseAuth.ProviderSecret> listSecrets() {
    return auth.listProviderSecrets();
  }

  public SynapseAuth.ProviderSecretDeleteResult deleteSecret(String secretId) {
    return auth.deleteProviderSecret(secretId);
  }

  public SynapseAuth.ProviderRegistrationGuide getRegistrationGuide() {
    return auth.getRegistrationGuide();
  }

  public SynapseAuth.ServiceManifestDraft parseCurlToServiceManifest(String curlCommand) {
    return auth.parseCurlToServiceManifest(curlCommand);
  }

  public SynapseAuth.RegisterProviderServiceResult registerService(SynapseAuth.RegisterProviderServiceOptions options) {
    return auth.registerProviderService(options);
  }

  public SynapseAuth.RegisterProviderServiceResult registerLlmService(SynapseAuth.RegisterProviderServiceOptions options) {
    options.serviceKind = "llm";
    options.priceModel = "token_metered";
    return auth.registerProviderService(options);
  }

  public List<SynapseAuth.ProviderServiceRecord> listServices() {
    return auth.listProviderServices();
  }

  public SynapseAuth.ProviderServiceRecord getService(String serviceId) {
    return auth.getProviderService(serviceId);
  }

  public SynapseAuth.ProviderServiceStatus getServiceStatus(String serviceId) {
    return auth.getProviderServiceStatus(serviceId);
  }

  public SynapseAuth.ProviderServiceUpdateResult updateService(String serviceRecordId, Map<String, Object> patch) {
    return auth.updateProviderService(serviceRecordId, patch);
  }

  public SynapseAuth.ProviderServiceDeleteResult deleteService(String serviceRecordId) {
    return auth.deleteProviderService(serviceRecordId);
  }

  public SynapseAuth.ProviderServicePingResult pingService(String serviceRecordId) {
    return auth.pingProviderService(serviceRecordId);
  }

  public SynapseAuth.ProviderServiceHealthHistory getServiceHealthHistory(String serviceRecordId, int limit) {
    return auth.getProviderServiceHealthHistory(serviceRecordId, limit);
  }

  public SynapseAuth.ProviderEarningsSummary getEarningsSummary() {
    return auth.getProviderEarningsSummary();
  }

  public SynapseAuth.ProviderWithdrawalCapability getWithdrawalCapability() {
    return auth.getProviderWithdrawalCapability();
  }

  public SynapseAuth.ProviderWithdrawalIntentResult createWithdrawalIntent(
      String amountUsdc, String idempotencyKey, String destinationAddress) {
    return auth.createProviderWithdrawalIntent(amountUsdc, idempotencyKey, destinationAddress);
  }

  public SynapseAuth.ProviderWithdrawalList listWithdrawals(int limit) {
    return auth.listProviderWithdrawals(limit);
  }
}
