/**
 * Synapse TypeScript SDK — Staging Agent Key E2E
 *
 * This replaces the retired wallet/chain flow. It validates that an existing
 * staging Agent Key can discover, invoke, and read receipts against staging.
 */

import { v4 as uuidv4 } from "uuid";
import { SynapseClient } from "../../src/client";

const runStagingE2E = process.env.RUN_STAGING_E2E === "1";
const describeStaging = runStagingE2E ? describe : describe.skip;

function requiredEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required for staging e2e`);
  return value;
}

describeStaging("Synapse TS SDK — Staging Agent Key E2E", () => {
  test("discovers staging services and invokes a known fixed-price service", async () => {
    const client = new SynapseClient({
      credential: requiredEnv("SYNAPSE_AGENT_KEY"),
      environment: "staging",
    });

    const services = await client.discover({ limit: 20 });
    expect(Array.isArray(services)).toBe(true);

    const result = await client.invoke(
      requiredEnv("SYNAPSE_STAGING_SERVICE_ID"),
      { prompt: "typescript sdk staging agent key e2e" },
      {
        costUsdc: requiredEnv("SYNAPSE_STAGING_SERVICE_PRICE_USDC"),
        idempotencyKey: `ts-staging-agent-e2e-${uuidv4()}`,
        pollTimeoutMs: 60_000,
      }
    );

    expect(result.invocationId).toBeTruthy();
    expect(["SUCCEEDED", "SETTLED"]).toContain(result.status);
  }, 90_000);
});
