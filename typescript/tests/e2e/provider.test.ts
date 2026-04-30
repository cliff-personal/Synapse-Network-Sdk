/**
 * Synapse TypeScript SDK — Staging Provider E2E
 *
 * Skipped by default. Set RUN_STAGING_PROVIDER_E2E=1 and provide a real
 * staging provider private key plus a public HTTPS provider endpoint.
 */

import { Wallet } from "ethers";
import { v4 as uuidv4 } from "uuid";
import { SynapseAuth } from "../../src/auth";

const runStagingProviderE2E = process.env.RUN_STAGING_PROVIDER_E2E === "1";
const describeStagingProvider = runStagingProviderE2E ? describe : describe.skip;

function requiredEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required for staging provider e2e`);
  return value;
}

describeStagingProvider("Synapse TS SDK — Staging Provider E2E", () => {
  test("registers a provider service and reads lifecycle status", async () => {
    const endpointUrl = requiredEnv("SYNAPSE_PROVIDER_ENDPOINT_URL");
    if (!endpointUrl.startsWith("https://")) {
      throw new Error("SYNAPSE_PROVIDER_ENDPOINT_URL must be a public HTTPS endpoint");
    }

    const sessionId = uuidv4().replace(/-/g, "").slice(0, 8);
    const providerAuth = SynapseAuth.fromWallet(new Wallet(requiredEnv("SYNAPSE_PROVIDER_PRIVATE_KEY")), {
      environment: "staging",
    });

    const token = await providerAuth.getToken();
    expect(token.length).toBeGreaterThan(20);

    const issued = await providerAuth.issueProviderSecret({
      name: `ts-provider-secret-${sessionId}`,
      rpm: 180,
      creditLimit: 25,
      resetInterval: "monthly",
    });
    expect(issued.secret.id).toBeTruthy();
    expect(String(issued.secret.secretKey ?? "")).toMatch(/^agt_/);

    const registered = await providerAuth.registerProviderService({
      serviceName: `TS Provider Staging ${sessionId}`,
      endpointUrl,
      basePriceUsdc: "0.002",
      descriptionForModel: "Staging provider onboarding e2e service.",
      providerDisplayName: `TS Provider ${sessionId}`,
      governanceNote: "typescript provider sdk staging e2e",
    });
    expect(registered.serviceId).toBeTruthy();

    const services = await providerAuth.listProviderServices();
    expect(services.map((service) => service.serviceId)).toContain(registered.serviceId);

    const status = await providerAuth.getProviderServiceStatus(registered.serviceId);
    expect(status.serviceId).toBe(registered.serviceId);
  }, 120_000);
});
