import type { SynapseAuth } from "./auth";
import type {
  IssueCredentialOptions,
  IssueProviderSecretResult,
  ProviderEarningsSummary,
  ProviderRegistrationGuide,
  ProviderSecret,
  ProviderSecretDeleteResult,
  RegisterProviderServiceOptions,
  RegisterProviderServiceResult,
  ProviderServiceRecord,
  ProviderServiceDeleteResult,
  ProviderServiceHealthHistory,
  ProviderServicePingResult,
  ProviderServiceStatus,
  ProviderServiceUpdateResult,
  ProviderWithdrawalCapability,
  ProviderWithdrawalIntentResult,
  ProviderWithdrawalList,
  ServiceManifestDraft,
} from "./types";

/**
 * Provider publishing facade backed by an authenticated SynapseAuth owner.
 *
 * Provider is an owner-scoped supply-side role in SynapseNetwork. This facade
 * keeps provider onboarding discoverable without introducing a second auth
 * root or breaking the existing SynapseAuth methods.
 */
export class SynapseProvider {
  constructor(private readonly auth: SynapseAuth) {}

  issueSecret(opts: IssueCredentialOptions = {}): Promise<IssueProviderSecretResult> {
    return this.auth.issueProviderSecret(opts);
  }

  listSecrets(): Promise<ProviderSecret[]> {
    return this.auth.listProviderSecrets();
  }

  deleteSecret(secretId: string): Promise<ProviderSecretDeleteResult> {
    return this.auth.deleteProviderSecret(secretId);
  }

  getRegistrationGuide(): Promise<ProviderRegistrationGuide> {
    return this.auth.getRegistrationGuide();
  }

  parseCurlToServiceManifest(curlCommand: string): Promise<ServiceManifestDraft> {
    return this.auth.parseCurlToServiceManifest(curlCommand);
  }

  registerService(opts: RegisterProviderServiceOptions): Promise<RegisterProviderServiceResult> {
    return this.auth.registerProviderService(opts);
  }

  registerLlmService(
    opts: Omit<RegisterProviderServiceOptions, "serviceKind" | "priceModel" | "basePriceUsdc">
  ): Promise<RegisterProviderServiceResult> {
    return this.auth.registerProviderService({
      ...opts,
      serviceKind: "llm",
      priceModel: "token_metered",
    });
  }

  listServices(): Promise<ProviderServiceRecord[]> {
    return this.auth.listProviderServices();
  }

  getService(serviceId: string): Promise<ProviderServiceRecord> {
    return this.auth.getProviderService(serviceId);
  }

  getServiceStatus(serviceId: string): Promise<ProviderServiceStatus> {
    return this.auth.getProviderServiceStatus(serviceId);
  }

  updateService(serviceRecordId: string, patch: Record<string, unknown>): Promise<ProviderServiceUpdateResult> {
    return this.auth.updateProviderService(serviceRecordId, patch);
  }

  deleteService(serviceRecordId: string): Promise<ProviderServiceDeleteResult> {
    return this.auth.deleteProviderService(serviceRecordId);
  }

  pingService(serviceRecordId: string): Promise<ProviderServicePingResult> {
    return this.auth.pingProviderService(serviceRecordId);
  }

  getServiceHealthHistory(
    serviceRecordId: string,
    opts: { limitPerTarget?: number } = {}
  ): Promise<ProviderServiceHealthHistory> {
    return this.auth.getProviderServiceHealthHistory(serviceRecordId, opts);
  }

  getEarningsSummary(): Promise<ProviderEarningsSummary> {
    return this.auth.getProviderEarningsSummary();
  }

  getWithdrawalCapability(): Promise<ProviderWithdrawalCapability> {
    return this.auth.getProviderWithdrawalCapability();
  }

  createWithdrawalIntent(
    amountUsdc: number,
    opts: { idempotencyKey?: string; destinationAddress?: string } = {}
  ): Promise<ProviderWithdrawalIntentResult> {
    return this.auth.createProviderWithdrawalIntent(amountUsdc, opts);
  }

  listWithdrawals(opts: { limit?: number } = {}): Promise<ProviderWithdrawalList> {
    return this.auth.listProviderWithdrawals(opts);
  }
}
