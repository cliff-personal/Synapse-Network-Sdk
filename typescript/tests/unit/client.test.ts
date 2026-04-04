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

// ── invoke() with costUsdc — single-call path ─────────────────────────────────

test("invoke() with costUsdc calls /agent/invoke directly (1 HTTP call)", async () => {
  const urls: string[] = [];
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (url: string) => {
    urls.push(url as string);
    return {
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({ invocationId: "inv_cost", status: "SUCCEEDED", chargedUsdc: 0.05 }),
    } as Response;
  });

  const client = new SynapseClient({ credential: "agt_test", gatewayUrl: "http://127.0.0.1:8000" });
  const result = await client.invoke("svc_1", { prompt: "hi" }, { costUsdc: 0.05, idempotencyKey: "k1" });

  expect(urls).toHaveLength(1);
  expect(urls[0]).toContain("/api/v1/agent/invoke");
  expect(result.invocationId).toBe("inv_cost");
  expect(result.chargedUsdc).toBeCloseTo(0.05);
});

test("invoke() with costUsdc sends correct body to /agent/invoke", async () => {
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

test("invoke() without costUsdc falls back to quote + invoke (2 HTTP calls)", async () => {
  const urls: string[] = [];
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (url: string) => {
    urls.push(url as string);
    if ((url as string).endsWith("/api/v1/agent/quotes")) {
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ quoteId: "q_fb", serviceId: "svc_3", priceUsdc: 0.02, expiresAt: "2099-01-01T00:00:00Z" }),
      } as Response;
    }
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ invocationId: "inv_fb", status: "SUCCEEDED", chargedUsdc: 0.02 }),
    } as Response;
  });

  const client = new SynapseClient({ credential: "agt_test" });
  await client.invoke("svc_3", {});
  expect(urls[0]).toContain("/api/v1/agent/quotes");
  expect(urls[1]).toContain("/api/v1/agent/invocations");
  expect(urls).toHaveLength(2);
});

test("invoke() with costUsdc throws PriceMismatchError on 422 PRICE_MISMATCH", async () => {
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
