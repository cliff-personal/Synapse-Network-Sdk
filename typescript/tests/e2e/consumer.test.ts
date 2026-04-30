/**
 * Synapse TypeScript SDK — Staging Consumer E2E
 *
 * These tests are skipped by default. Set RUN_STAGING_E2E=1 plus the required
 * staging service environment variables to run live gateway smoke tests.
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

describeStaging("Synapse TS SDK — Staging Consumer E2E", () => {
  test("fixed-price invoke reaches a terminal status and receipt is readable", async () => {
    const client = new SynapseClient({
      credential: requiredEnv("SYNAPSE_AGENT_KEY"),
      environment: "staging",
    });

    const result = await client.invoke(
      requiredEnv("SYNAPSE_STAGING_SERVICE_ID"),
      { prompt: "typescript sdk staging e2e" },
      {
        costUsdc: requiredEnv("SYNAPSE_STAGING_SERVICE_PRICE_USDC"),
        idempotencyKey: `ts-staging-e2e-${uuidv4()}`,
        pollTimeoutMs: 60_000,
      }
    );

    expect(result.invocationId).toBeTruthy();
    expect(["SUCCEEDED", "SETTLED"]).toContain(result.status);

    const receipt = await client.getInvocation(result.invocationId);
    expect(receipt.invocationId).toBe(result.invocationId);
    expect(["SUCCEEDED", "SETTLED"]).toContain(receipt.status);
  }, 90_000);

  test("token-metered LLM invoke omits costUsdc and returns billing metadata", async () => {
    const serviceId = process.env.SYNAPSE_STAGING_LLM_SERVICE_ID?.trim();
    if (!serviceId) {
      console.warn("Skipping optional LLM staging e2e: SYNAPSE_STAGING_LLM_SERVICE_ID is not set");
      return;
    }

    const client = new SynapseClient({
      credential: requiredEnv("SYNAPSE_AGENT_KEY"),
      environment: "staging",
    });

    const result = await client.invokeLlm(
      serviceId,
      { messages: [{ role: "user", content: "hello from typescript staging e2e" }] },
      {
        maxCostUsdc: process.env.SYNAPSE_STAGING_LLM_MAX_COST_USDC?.trim() ?? "0.010000",
        idempotencyKey: `ts-staging-llm-e2e-${uuidv4()}`,
        pollTimeoutMs: 60_000,
      }
    );

    expect(result.invocationId).toBeTruthy();
    expect(["SUCCEEDED", "SETTLED"]).toContain(result.status);
    expect(result.synapse).toBeTruthy();
  }, 90_000);
});
