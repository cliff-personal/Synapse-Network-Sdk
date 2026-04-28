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
  DiscoveryError,
  InsufficientFundsError,
  InvokeError,
  PriceMismatchError,
  TimeoutError,
} from "../../src/errors";

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeFetchMock(responses: Array<{ status: number; body: unknown }>): jest.Mock {
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
  expect(resolveGatewayUrl({ environment: "prod", gatewayUrl: "https://gateway.example/" })).toBe(
    "https://gateway.example"
  );
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

  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (url: string) => {
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
  });

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
      text: async () => JSON.stringify({ invocationId: "inv_002", status: "SUCCEEDED", chargedUsdc: 0.01 }),
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
      text: async () => JSON.stringify({ invocationId: "inv_b", status: "SUCCEEDED", chargedUsdc: 0.1 }),
    } as Response;
  });

  const client = new SynapseClient({ credential: "agt_test" });
  await client.invoke("svc_2", { text: "test" }, { costUsdc: 0.1, idempotencyKey: "ik-2" });

  const body = capturedBody as Record<string, unknown>;
  expect(body["serviceId"]).toBe("svc_2");
  expect(body["costUsdc"]).toBe(0.1);
  expect(body["idempotencyKey"]).toBe("ik-2");
  expect((body["payload"] as Record<string, unknown>)["body"]).toEqual({ text: "test" });
});

// ── Error mapping ─────────────────────────────────────────────────────────────

test("401 response from invoke throws AuthenticationError", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async () =>
      ({
        ok: false,
        status: 401,
        text: async () => JSON.stringify({ detail: "Invalid credential" }),
      }) as Response
  );

  const client = new SynapseClient({ credential: "agt_bad" });
  await expect(client.invoke("svc_1", {}, { costUsdc: 0.01 })).rejects.toThrow(AuthenticationError);
});

test("402 response from invoke throws InsufficientFundsError", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async () =>
      ({
        ok: false,
        status: 402,
        text: async () => JSON.stringify({ detail: "Insufficient funds" }),
      }) as Response
  );

  const client = new SynapseClient({ credential: "agt_test" });
  await expect(client.invoke("svc_1", {}, { costUsdc: 0.05 })).rejects.toThrow(InsufficientFundsError);
});

test("500 from invoke throws InvokeError", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async () =>
      ({
        ok: false,
        status: 500,
        text: async () => "internal server error",
      }) as Response
  );

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
          services: [{ serviceId: "svc_a", serviceName: "Service A", summary: "test", status: "online" }],
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
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async () =>
      ({
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
      }) as Response
  );

  const client = new SynapseClient({ credential: "agt_test" });
  const err = await client.invoke("svc_x", {}, { costUsdc: 0.05 }).catch((e) => e);
  expect(err).toBeInstanceOf(PriceMismatchError);
  expect((err as PriceMismatchError).expectedPriceUsdc).toBeCloseTo(0.05);
  expect((err as PriceMismatchError).currentPriceUsdc).toBeCloseTo(0.15);
});

test("invoke() returns pending result without polling when pollTimeoutMs is zero", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async () =>
      ({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ invocationId: "inv_pending", status: "PENDING" }),
      }) as Response
  );

  const client = new SynapseClient({ credential: "agt_test" });
  const result = await client.invoke("svc_pending", {}, { costUsdc: 0.01, pollTimeoutMs: 0 });

  expect(result.status).toBe("PENDING");
  expect(globalThis.fetch as jest.Mock).toHaveBeenCalledTimes(1);
});

test("invoke() polls when sync response is non-terminal and polling remains enabled", async () => {
  const statuses = ["PENDING", "SUCCEEDED"];
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async (url: string) =>
      ({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify(
            url.includes("/api/v1/agent/invoke")
              ? { invocationId: "inv_poll", status: "PENDING", chargedUsdc: 0 }
              : { invocationId: "inv_poll", status: statuses.shift() ?? "SUCCEEDED", chargedUsdc: 0.03 }
          ),
      }) as Response
  );

  const client = new SynapseClient({ credential: "agt_test" });
  const result = await client.invoke("svc_poll", {}, { costUsdc: 0.03, pollIntervalMs: 0, pollTimeoutMs: 50 });

  expect(result.status).toBe("SUCCEEDED");
  expect((globalThis.fetch as jest.Mock).mock.calls.length).toBeGreaterThan(1);
});

test("waitForInvocation polls until a terminal receipt is returned", async () => {
  const statuses = ["PENDING", "SUCCEEDED"];
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async (url: string) =>
      ({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            id: decodeURIComponent(url.split("/").pop() ?? ""),
            status: statuses.shift() ?? "SUCCEEDED",
            charged_usdc: 0.2,
          }),
      }) as Response
  );

  const client = new SynapseClient({ credential: "agt_test" });
  const result = await client.waitForInvocation("inv spaced", { pollTimeoutMs: 50, pollIntervalMs: 0 });

  expect(result.invocationId).toBe("inv spaced");
  expect(result.status).toBe("SUCCEEDED");
  expect(result.chargedUsdc).toBeCloseTo(0.2);
  expect((globalThis.fetch as jest.Mock).mock.calls[0][0]).toContain("inv%20spaced");
});

test("waitForInvocation times out when receipt never reaches terminal state", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn();

  const client = new SynapseClient({ credential: "agt_test" });
  await expect(client.waitForInvocation("inv_timeout", { pollTimeoutMs: 0 })).rejects.toThrow(TimeoutError);
});

test("discover and search map gateway failures to DiscoveryError", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async () =>
      ({
        ok: false,
        status: 500,
        text: async () => JSON.stringify({ detail: { code: "DISCOVERY_DOWN" } }),
      }) as Response
  );

  const client = new SynapseClient({ credential: "agt_test" });
  await expect(client.search("broken")).rejects.toThrow(DiscoveryError);
  await expect(client.discover()).rejects.toThrow(DiscoveryError);
});

test("search accepts legacy array discovery response", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async () =>
      ({
        ok: true,
        status: 200,
        text: async () => JSON.stringify([{ serviceId: "svc_array", serviceName: "Array Service" }]),
      }) as Response
  );

  const client = new SynapseClient({ credential: "agt_test" });
  const services = await client.search("array", { limit: 0, offset: -10 });

  expect(services).toEqual([{ serviceId: "svc_array", serviceName: "Array Service" }]);
});

test("invokeWithRediscovery retries once with live discovered price", async () => {
  const calls: Array<{ url: string; body?: Record<string, unknown> }> = [];
  let invokeCount = 0;
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (url: string, init?: RequestInit) => {
    const body = init?.body ? (JSON.parse(init.body as string) as Record<string, unknown>) : undefined;
    calls.push({ url, body });
    if (url.includes("/api/v1/agent/invoke")) {
      invokeCount += 1;
      if (invokeCount === 1) {
        return {
          ok: false,
          status: 422,
          text: async () =>
            JSON.stringify({
              detail: {
                code: "PRICE_MISMATCH",
                message: "Price changed",
                expectedPriceUsdc: 0.05,
                currentPriceUsdc: 0.12,
              },
            }),
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ invocationId: "inv_retry", status: "SUCCEEDED", chargedUsdc: 0.12 }),
      } as Response;
    }
    return {
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          services: [{ serviceId: "svc_1", serviceName: "Service 1", pricing: { amount: "0.12", currency: "USDC" } }],
        }),
    } as Response;
  });

  const client = new SynapseClient({ credential: "agt_test" });
  const result = await client.invokeWithRediscovery(
    "svc_1",
    { prompt: "hi" },
    {
      costUsdc: 0.05,
      query: "market data",
      idempotencyKey: "ik-retry",
    }
  );

  expect(result.invocationId).toBe("inv_retry");
  expect(calls[1].url).toContain("/api/v1/agent/discovery/search");
  expect(calls[1].body?.query).toBe("market data");
  expect(calls[2].body?.costUsdc).toBe(0.12);
});

test("gateway health, invocation receipt alias, and empty discovery diagnostics are exposed", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async (url: string) =>
      ({
        ok: true,
        status: 200,
        text: async () =>
          url.endsWith("/health")
            ? JSON.stringify({ status: "ok" })
            : JSON.stringify({ invocationId: "inv_1", status: "SUCCEEDED", chargedUsdc: 0 }),
      }) as Response
  );

  const client = new SynapseClient({ credential: "agt_test", environment: "local" });
  await expect(client.checkGatewayHealth()).resolves.toEqual({ status: "ok" });
  await expect(client.getInvocationReceipt("inv_1")).resolves.toMatchObject({ invocationId: "inv_1" });
  expect(client.explainDiscoveryEmptyResult({ query: "quotes" })).toMatchObject({ query: "quotes" });
});

test("invokeWithRediscovery respects disabled retry and falls back to gateway live price", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async () =>
      ({
        ok: false,
        status: 422,
        text: async () =>
          JSON.stringify({
            detail: {
              code: "PRICE_MISMATCH",
              message: "Price changed",
              expectedPriceUsdc: 0.05,
              currentPriceUsdc: 0.12,
            },
          }),
      }) as Response
  );

  const client = new SynapseClient({ credential: "agt_test" });
  await expect(
    client.invokeWithRediscovery(
      "svc_1",
      {},
      {
        costUsdc: 0.05,
        maxRediscoveryRetries: 0,
      }
    )
  ).rejects.toThrow(PriceMismatchError);
});

test("invokeWithRediscovery handles string prices and missing discovered prices", async () => {
  const calls: Array<{ url: string; body?: Record<string, unknown> }> = [];
  let invokeCount = 0;
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (url: string, init?: RequestInit) => {
    const body = init?.body ? (JSON.parse(init.body as string) as Record<string, unknown>) : undefined;
    calls.push({ url, body });
    if (url.includes("/api/v1/agent/invoke")) {
      invokeCount += 1;
      if (invokeCount === 1) {
        return {
          ok: false,
          status: 422,
          text: async () =>
            JSON.stringify({
              detail: {
                code: "PRICE_MISMATCH",
                message: "Price changed",
                expectedPriceUsdc: 0.05,
                currentPriceUsdc: 0.13,
              },
            }),
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ invocationId: "inv_string_price", status: "SUCCEEDED", chargedUsdc: 0.14 }),
      } as Response;
    }
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ services: [{ serviceId: "svc_1", pricing: "0.14" }] }),
    } as Response;
  });

  const client = new SynapseClient({ credential: "agt_test" });
  const result = await client.invokeWithRediscovery("svc_1", {}, { costUsdc: 0.05 });

  expect(result.invocationId).toBe("inv_string_price");
  expect(calls[2].body?.costUsdc).toBe(0.14);
});

test("invokeWithRediscovery fails clearly when rediscovery cannot provide a price", async () => {
  let invokeCount = 0;
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (url: string) => {
    if (url.includes("/api/v1/agent/invoke")) {
      invokeCount += 1;
      return {
        ok: false,
        status: 422,
        text: async () =>
          JSON.stringify({
            detail: {
              code: "PRICE_MISMATCH",
              message: "Price changed but no live price was returned",
              expectedPriceUsdc: 0.05,
              currentPriceUsdc: 0,
            },
          }),
      } as Response;
    }
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ services: [{ serviceId: "svc_1", pricing: {} }] }),
    } as Response;
  });

  const client = new SynapseClient({ credential: "agt_test" });
  await expect(client.invokeWithRediscovery("svc_1", {}, { costUsdc: 0.05 })).rejects.toThrow(PriceMismatchError);
  expect(invokeCount).toBe(1);
});
