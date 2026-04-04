/**
 * SynapseClient Unit Tests
 *
 * Tests client behaviour without a live gateway by intercepting fetch()
 * via jest.spyOn / globalThis.fetch mock.
 */

import { SynapseClient } from "../../src/client";
import {
  AuthenticationError,
  InsufficientFundsError,
  QuoteError,
  InvokeError,
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
  // Just ensure no exception is thrown — no public gatewayUrl accessor needed
  expect(client).toBeInstanceOf(SynapseClient);
});

// ── invoke() — one-step flow ──────────────────────────────────────────────────

test("invoke() calls quotes then invocations and returns InvocationResult", async () => {
  const urls: string[] = [];

  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async (url: string, init?: RequestInit) => {
      urls.push(url as string);
      if ((url as string).endsWith("/api/v1/agent/quotes")) {
        return {
          ok: true,
          status: 200,
          text: async () =>
            JSON.stringify({
              quoteId: "quote_001",
              serviceId: "svc_test",
              priceUsdc: 0.05,
              expiresAt: "2099-01-01T00:00:00Z",
            }),
        } as Response;
      }
      // invocations endpoint
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
    gatewayUrl: "http://127.0.0.1:8000",
  });

  const result = await client.invoke("svc_test", { prompt: "hi" }, { idempotencyKey: "key-1" });

  expect(urls[0]).toContain("/api/v1/agent/quotes");
  expect(urls[1]).toContain("/api/v1/agent/invocations");
  expect(result.invocationId).toBe("inv_001");
  expect(result.status).toBe("SUCCEEDED");
  expect(result.chargedUsdc).toBeCloseTo(0.05);
});

test("invoke() skips polling when invocation already terminal", async () => {
  let callCount = 0;
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (url: string) => {
    callCount += 1;
    if ((url as string).endsWith("/api/v1/agent/quotes")) {
      return {
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({ quoteId: "q2", serviceId: "svc_t", priceUsdc: 0.01, expiresAt: "2099-01-01T00:00:00Z" }),
      } as Response;
    }
    return {
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({ invocationId: "inv_002", status: "SUCCEEDED", chargedUsdc: 0.01 }),
    } as Response;
  });

  const client = new SynapseClient({ credential: "agt_test" });
  await client.invoke("svc_t", {});

  // Should have made exactly 2 calls: quote + invoke — no extra poll
  expect(callCount).toBe(2);
});

// ── quote() ───────────────────────────────────────────────────────────────────

test("quote() returns quoteId from response", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async (_url: string) => ({
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({ quoteId: "quote_abc", serviceId: "svc_1", priceUsdc: 0.1, expiresAt: "2099-01-01T00:00:00Z" }),
    } as Response)
  );

  const client = new SynapseClient({ credential: "agt_test" });
  const result = await client.quote("svc_1");

  expect(result.quoteId).toBe("quote_abc");
});

test("quote() throws QuoteError when quoteId is missing", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async () => ({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ serviceId: "svc_1" }), // no quoteId
    } as Response)
  );

  const client = new SynapseClient({ credential: "agt_test" });
  await expect(client.quote("svc_1")).rejects.toThrow(QuoteError);
});

// ── invokeByQuote() ────────────────────────────────────────────────────────────

test("invokeByQuote() sends correct body and returns result", async () => {
  let capturedBody: unknown;
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(
    async (_url: string, init?: RequestInit) => {
      capturedBody = JSON.parse((init?.body as string) ?? "{}");
      return {
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({ invocationId: "inv_003", status: "SUCCEEDED", chargedUsdc: 0.02 }),
      } as Response;
    }
  );

  const client = new SynapseClient({ credential: "agt_test" });
  const result = await client.invokeByQuote("q_xyz", { data: "test" }, { idempotencyKey: "ik-1" });

  expect((capturedBody as Record<string, unknown>)["quoteId"]).toBe("q_xyz");
  expect((capturedBody as Record<string, unknown>)["idempotencyKey"]).toBe("ik-1");
  expect(result.invocationId).toBe("inv_003");
});

// ── Error mapping ─────────────────────────────────────────────────────────────

test("401 response from quotes throws AuthenticationError", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async () => ({
    ok: false,
    status: 401,
    text: async () => JSON.stringify({ detail: "Invalid credential" }),
  } as Response));

  const client = new SynapseClient({ credential: "agt_bad" });
  await expect(client.quote("svc_1")).rejects.toThrow(AuthenticationError);
});

test("402 response from invocations throws InsufficientFundsError", async () => {
  let callCount = 0;
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (url: string) => {
    callCount += 1;
    if ((url as string).endsWith("/api/v1/agent/quotes")) {
      return {
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({ quoteId: "q3", serviceId: "svc_1", priceUsdc: 0.05, expiresAt: "2099-01-01T00:00:00Z" }),
      } as Response;
    }
    return {
      ok: false,
      status: 402,
      text: async () => JSON.stringify({ detail: "Insufficient funds" }),
    } as Response;
  });

  const client = new SynapseClient({ credential: "agt_test" });
  await expect(client.invoke("svc_1", {})).rejects.toThrow(InsufficientFundsError);
});

test("500 from invokeByQuote throws InvokeError", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async () => ({
    ok: false,
    status: 500,
    text: async () => "internal server error",
  } as Response));

  const client = new SynapseClient({ credential: "agt_test" });
  await expect(client.invokeByQuote("q_bad", {})).rejects.toThrow(InvokeError);
});

// ── discover() ────────────────────────────────────────────────────────────────

test("discover() returns service array from response.services", async () => {
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async () => ({
    ok: true,
    status: 200,
    text: async () =>
      JSON.stringify({
        services: [
          { serviceId: "svc_a", serviceName: "Service A", summary: "test", status: "online" },
        ],
      }),
  } as Response));

  const client = new SynapseClient({ credential: "agt_test" });
  const svcs = await client.discover();
  expect(svcs).toHaveLength(1);
  expect(svcs[0].serviceId).toBe("svc_a");
});
