/**
 * SynapseClient Unit Tests
 *
 * Tests client behaviour without a live gateway by intercepting fetch()
 * via jest.spyOn / globalThis.fetch mock.
 */

import { SynapseClient } from "../../src/client";
import { SynapseAuth } from "../../src/auth";
import { resolveGatewayUrl } from "../../src/config";
import {
  AuthenticationError,
  InsufficientFundsError,
  InvokeError,
  PriceMismatchError,
} from "../../src/errors";

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeFetchMock(
  responses: Array<{ status: number; body: unknown }>
): jest.Mock {
  let callCount = 0;
  return jest.fn(async (_url: string, _init?: RequestInit) => {
    const resp = responses[callCount % responses.length];
    callCount += 1;
    const text = JSON.stringify(resp.body);
    return {
      ok: resp.status >= 200 && resp.status < 300,
      status: resp.status,
      text: async () => text,
    } as Response;
  });
}

beforeEach(() => {
  jest.restoreAllMocks();
});

// ── Constructor ───────────────────────────────────────────────────────────────

test("constructor throws when credential is empty", () => {
  expect(() => new SynapseClient({ credential: "" })).toThrow("credential is required");
});

test("constructor accepts default gatewayUrl", () => {
  const client = new SynapseClient({ credential: "agt_test" });
  expect(client).toBeInstanceOf(SynapseClient);
});

test("resolveGatewayUrl defaults to staging public preview", () => {
  expect(resolveGatewayUrl()).toBe("https://api-staging.synapse-network.ai");
});

test("resolveGatewayUrl supports presets and explicit override", () => {
  expect(resolveGatewayUrl({ environment: "local" })).toBe("http://127.0.0.1:8000");
  expect(resolveGatewayUrl({ environment: "staging" })).toBe("https://api-staging.synapse-network.ai");
  expect(resolveGatewayUrl({ environment: "prod" })).toBe("https://api.synapse-network.ai");
  expect(resolveGatewayUrl({ environment: "prod", gatewayUrl: "https://gateway.example/" })).toBe("https://gateway.example");
});

test("resolveGatewayUrl rejects invalid environment", () => {
  expect(() => resolveGatewayUrl({ environment: "preview" as never })).toThrow("unsupported Synapse environment");
});

test("SynapseAuth defaults to staging gateway", async () => {
  const urls: string[] = [];
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (url: string) => {
    urls.push(url);
    return {
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify(
          urls.length === 1
            ? { success: true, challenge: "sign-me", domain: "synapse" }
            : { success: true, access_token: "jwt-token", token_type: "bearer", expires_in: 3600 }
        ),
    } as Response;
  });

  const auth = SynapseAuth.fromWallet({
    address: "0xabc",
    signMessage: async () => "0xsigned",
  });

  await auth.getToken();
  expect(urls[0]).toContain("https://api-staging.synapse-network.ai/api/v1/auth/challenge");
});

// ── invoke() — single-call path ───────────────────────────────────────────────

test("invoke() calls /agent/invoke and returns InvocationResult", async () => {
  const urls: string[] = [];

  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async (url: string) => {
      urls.push(url as string);
      return {
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            invocationId: "inv_001",
            status: "SUCCEEDED",
            chargedUsdc: 0.05,
            result: { answer: "hello world" },
          }),
      } as Response;
    }
  );

  const client = new SynapseClient({
    credential: "agt_test",
    environment: "local",
  });

  const result = await client.invoke("svc_test", { prompt: "hi" }, { costUsdc: 0.05, idempotencyKey: "key-1" });

  expect(urls).toHaveLength(1);
  expect(urls[0]).toContain("/api/v1/agent/invoke");
  expect(result.invocationId).toBe("inv_001");
  expect(result.status).toBe("SUCCEEDED");
  expect(result.chargedUsdc).toBeCloseTo(0.05);
});

test("invoke() skips polling when invocation already terminal", async () => {
  let callCount = 0;
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async () => {
    callCount += 1;
    return {
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({ invocationId: "inv_002", status: "SUCCEEDED", chargedUsdc: 0.01 }),
    } as Response;
  });

  const client = new SynapseClient({ credential: "agt_test" });
  await client.invoke("svc_t", {}, { costUsdc: 0.01 });

  // Should have made exactly 1 call — no extra poll
  expect(callCount).toBe(1);
});

test("invoke() sends correct body to /agent/invoke", async () => {
  let capturedBody: unknown;
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (_url: string, init?: RequestInit) => {
    capturedBody = JSON.parse((init?.body as string) ?? "{}");
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ invocationId: "inv_b", status: "SUCCEEDED", chargedUsdc: 0.10 }),
    } as Response;
  });

  const client = new SynapseClient({ credential: "agt_test" });
  await client.invoke("svc_2", { text: "test" }, { costUsdc: 0.10, idempotencyKey: "ik-2" });

  const body = capturedBody as Record<string, unknown>;
  expect(body["serviceId"]).toBe("svc_2");
  expect(body["costUsdc"]).toBe(0.10);
  expect(body["idempotencyKey"]).toBe("ik-2");
  expect((body["payload"] as Record<string, unknown>)["body"]).toEqual({ text: "test" });
});

// ── Error mapping ─────────────────────────────────────────────────────────────

test("401 response from invoke throws AuthenticationError", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async () => ({
    ok: false,
    status: 401,
    text: async () => JSON.stringify({ detail: "Invalid credential" }),
  } as Response));

  const client = new SynapseClient({ credential: "agt_bad" });
  await expect(client.invoke("svc_1", {}, { costUsdc: 0.01 })).rejects.toThrow(AuthenticationError);
});

test("402 response from invoke throws InsufficientFundsError", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async () => ({
    ok: false,
    status: 402,
    text: async () => JSON.stringify({ detail: "Insufficient funds" }),
  } as Response));

  const client = new SynapseClient({ credential: "agt_test" });
  await expect(client.invoke("svc_1", {}, { costUsdc: 0.05 })).rejects.toThrow(InsufficientFundsError);
});

test("500 from invoke throws InvokeError", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async () => ({
    ok: false,
    status: 500,
    text: async () => "internal server error",
  } as Response));

  const client = new SynapseClient({ credential: "agt_test" });
  await expect(client.invoke("svc_bad", {}, { costUsdc: 0.01 })).rejects.toThrow(InvokeError);
});

// ── discover() ────────────────────────────────────────────────────────────────

test("discover() returns service array from response.services", async () => {
  let capturedUrl = "";
  let capturedBody: Record<string, unknown> = {};
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (url: string, init?: RequestInit) => {
    capturedUrl = url;
    capturedBody = JSON.parse((init?.body as string) ?? "{}");
    return {
    ok: true,
    status: 200,
    text: async () =>
      JSON.stringify({
        services: [
          { serviceId: "svc_a", serviceName: "Service A", summary: "test", status: "online" },
        ],
      }),
  } as Response;
  });

  const client = new SynapseClient({ credential: "agt_test" });
  const svcs = await client.discover({ limit: 10, offset: 20, tags: ["llm"], sort: "lowest_price" });
  expect(svcs).toHaveLength(1);
  expect(svcs[0].serviceId).toBe("svc_a");
  expect(capturedUrl).toContain("/api/v1/agent/discovery/search");
  expect(capturedBody).toEqual({
    tags: ["llm"],
    page: 3,
    pageSize: 10,
    sort: "lowest_price",
  });
});

test("search() sends current gateway discovery request shape", async () => {
  let capturedBody: Record<string, unknown> = {};
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (_url: string, init?: RequestInit) => {
    capturedBody = JSON.parse((init?.body as string) ?? "{}");
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ results: [] }),
    } as Response;
  });

  const client = new SynapseClient({ credential: "agt_test" });
  await client.search("quotes", { limit: 5, offset: 10, tags: ["text"] });

  expect(capturedBody).toEqual({
    query: "quotes",
    tags: ["text"],
    page: 3,
    pageSize: 5,
    sort: "best_match",
  });
});

// ── PRICE_MISMATCH ────────────────────────────────────────────────────────────

test("invoke() throws PriceMismatchError on 422 PRICE_MISMATCH", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async () => ({
    ok: false,
    status: 422,
    text: async () =>
      JSON.stringify({
        detail: {
          code: "PRICE_MISMATCH",
          message: "Price changed: expected 0.05, current 0.15",
          expectedPriceUsdc: 0.05,
          currentPriceUsdc: 0.15,
        },
      }),
  } as Response));

  const client = new SynapseClient({ credential: "agt_test" });
  const err = await client.invoke("svc_x", {}, { costUsdc: 0.05 }).catch((e) => e);
  expect(err).toBeInstanceOf(PriceMismatchError);
  expect((err as PriceMismatchError).expectedPriceUsdc).toBeCloseTo(0.05);
  expect((err as PriceMismatchError).currentPriceUsdc).toBeCloseTo(0.15);
});
