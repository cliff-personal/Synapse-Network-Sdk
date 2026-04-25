import type { SynapseAuth } from "./auth";
import type {
  IssueCredentialOptions,
  IssueProviderSecretResult,
  ProviderSecret,
  RegisterProviderServiceOptions,
  RegisterProviderServiceResult,
  ProviderServiceRecord,
  ProviderServiceStatus,
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

  deleteSecret(secretId: string): Promise<Record<string, unknown>> {
    return this.auth.deleteProviderSecret(secretId);
  }

  getRegistrationGuide(): Promise<Record<string, unknown>> {
    return this.auth.getRegistrationGuide();
  }

  parseCurlToServiceManifest(curlCommand: string): Promise<Record<string, unknown>> {
    return this.auth.parseCurlToServiceManifest(curlCommand);
  }

  registerService(opts: RegisterProviderServiceOptions): Promise<RegisterProviderServiceResult> {
    return this.auth.registerProviderService(opts);
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

  updateService(serviceRecordId: string, patch: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.auth.updateProviderService(serviceRecordId, patch);
  }

  deleteService(serviceRecordId: string): Promise<Record<string, unknown>> {
    return this.auth.deleteProviderService(serviceRecordId);
  }

  pingService(serviceRecordId: string): Promise<Record<string, unknown>> {
    return this.auth.pingProviderService(serviceRecordId);
  }

  getServiceHealthHistory(
    serviceRecordId: string,
    opts: { limitPerTarget?: number } = {}
  ): Promise<Record<string, unknown>> {
    return this.auth.getProviderServiceHealthHistory(serviceRecordId, opts);
  }

  getEarningsSummary(): Promise<Record<string, unknown>> {
    return this.auth.getProviderEarningsSummary();
  }

  getWithdrawalCapability(): Promise<Record<string, unknown>> {
    return this.auth.getProviderWithdrawalCapability();
  }

  createWithdrawalIntent(
    amountUsdc: number,
    opts: { idempotencyKey?: string; destinationAddress?: string } = {}
  ): Promise<Record<string, unknown>> {
    return this.auth.createProviderWithdrawalIntent(amountUsdc, opts);
  }

  listWithdrawals(opts: { limit?: number } = {}): Promise<Record<string, unknown>> {
    return this.auth.listProviderWithdrawals(opts);
  }
}
