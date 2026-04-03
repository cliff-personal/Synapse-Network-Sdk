/**
 * Synapse TypeScript SDK — Provider Onboarding E2E Test
 *
 * 冷启动 Provider 控制面链路：
 *   创建钱包 → challenge/sign/verify → issue provider secret
 *   → register provider service → read provider service status
 */

import { Wallet } from "ethers";
import * as http from "http";
import { v4 as uuidv4 } from "uuid";
import { SynapseAuth } from "../../src/auth";

const GATEWAY_URL = process.env.SYNAPSE_GATEWAY ?? "http://127.0.0.1:8000";
const MOCK_PROVIDER_PORT = 9498;
const SESSION_ID = uuidv4().replace(/-/g, "").slice(0, 8);

let mockServer: http.Server;
let providerAuth: SynapseAuth;
let providerServiceId: string;

async function startMockProvider(): Promise<string> {
  return new Promise((resolve) => {
    mockServer = http.createServer((req, res) => {
      if (req.method === "GET") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "healthy" }));
      } else if (req.method === "POST") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ result: "ts provider-sdk e2e mock response" }));
      } else {
        res.writeHead(405);
        res.end();
      }
    });
    mockServer.listen(MOCK_PROVIDER_PORT, "127.0.0.1", () => {
      resolve(`http://127.0.0.1:${MOCK_PROVIDER_PORT}`);
    });
  });
}

describe("Synapse TS SDK — Provider Onboarding E2E", () => {
  beforeAll(async () => {
    const mockServiceUrl = await startMockProvider();
    const freshProvider = Wallet.createRandom();

    providerAuth = SynapseAuth.fromWallet(freshProvider, {
      gatewayUrl: GATEWAY_URL,
    });

    const token = await providerAuth.getToken();
    expect(typeof token).toBe("string");
    expect(token.length).toBeGreaterThan(20);

    const issued = await providerAuth.issueProviderSecret({
      name: `ts-provider-secret-${SESSION_ID}`,
      rpm: 180,
      creditLimit: 25,
      resetInterval: "monthly",
    });
    expect(issued.secret.id).toBeTruthy();
    expect(String(issued.secret.secretKey ?? "")).toMatch(/^agt_/);

    const registered = await providerAuth.registerProviderService({
      serviceName: `TS Provider OCR ${SESSION_ID}`,
      endpointUrl: mockServiceUrl,
      basePriceUsdc: "0.002",
      descriptionForModel: "Extract structured invoice fields for TypeScript provider onboarding e2e.",
      providerDisplayName: `TS Provider ${SESSION_ID}`,
      governanceNote: "typescript provider sdk e2e",
    });
    expect(registered.status).toBe("success");
    expect(registered.serviceId).toBeTruthy();
    providerServiceId = registered.serviceId;
  }, 120_000);

  afterAll(() => {
    if (mockServer) mockServer.close();
  });

  it("lists the newly issued provider secret", async () => {
    const secrets = await providerAuth.listProviderSecrets();
    const names = secrets.map((secret) => secret.name);
    expect(names).toContain(`ts-provider-secret-${SESSION_ID}`);
  });

  it("lists the newly registered provider service", async () => {
    const services = await providerAuth.listProviderServices();
    const serviceIds = services.map((service) => service.serviceId);
    expect(serviceIds).toContain(providerServiceId);
  });

  it("returns lifecycle and runtime status for the provider service", async () => {
    const status = await providerAuth.getProviderServiceStatus(providerServiceId);
    expect(status.serviceId).toBe(providerServiceId);
    expect(["active", "draft", "paused"]).toContain(status.lifecycleStatus);
    expect(["healthy", "unknown", "degraded"]).toContain(
      String(status.health.overallStatus ?? "unknown")
    );
  });
});
