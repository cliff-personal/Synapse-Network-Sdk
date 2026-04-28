import { SynapseAuth, SynapseClient, SynapseProvider, AuthenticationError, resolveGatewayUrl } from "../../src";

type MockResponse = { status?: number; body: unknown };

function mockFetch(responses: MockResponse[]) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  let index = 0;
  (globalThis as unknown as Record<string, unknown>).fetch = jest.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    const response = responses[Math.min(index, responses.length - 1)];
    index += 1;
    const status = response.status ?? 200;
    return {
      ok: status >= 200 && status < 300,
      status,
      text: async () => (typeof response.body === "string" ? response.body : JSON.stringify(response.body)),
    } as Response;
  });
  return calls;
}

function authForTests(): SynapseAuth {
  return SynapseAuth.fromWallet(
    {
      address: "0xABCDEF",
      signMessage: async (message: string) => `signed:${message}`,
    },
    { environment: "local" }
  );
}

function authHandshakeResponses(token = "jwt-token"): MockResponse[] {
  return [
    { body: { success: true, challenge: "sign this", domain: "synapse" } },
    { body: { success: true, access_token: token, token_type: "bearer", expires_in: 3600 } },
  ];
}

function headersOf(call: { init?: RequestInit }): Record<string, string> {
  return (call.init?.headers ?? {}) as Record<string, string>;
}

beforeEach(() => {
  jest.restoreAllMocks();
});

test("public barrel exports SDK entrypoints", () => {
  expect(SynapseAuth).toBeDefined();
  expect(SynapseClient).toBeDefined();
  expect(SynapseProvider).toBeDefined();
  expect(resolveGatewayUrl({ environment: "local" })).toBe("http://127.0.0.1:8000");
});

test("authenticate signs challenge, verifies wallet, and caches JWT", async () => {
  const signer = jest.fn(async (message: string) => `signature:${message}`);
  const calls = mockFetch(authHandshakeResponses("cached-jwt"));
  const auth = new SynapseAuth({
    environment: "local",
    signer,
    walletAddress: "0xABCDEF",
  });

  await expect(auth.authenticate()).resolves.toBe("cached-jwt");
  await expect(auth.getToken()).resolves.toBe("cached-jwt");

  expect(signer).toHaveBeenCalledTimes(1);
  expect(calls).toHaveLength(2);
  expect(calls[0].url).toContain("/api/v1/auth/challenge?address=0xabcdef");
  expect(calls[1].url).toContain("/api/v1/auth/verify");
  expect(JSON.parse((calls[1].init?.body as string) ?? "{}")).toEqual({
    wallet_address: "0xabcdef",
    message: "sign this",
    signature: "signature:sign this",
  });
});

test("authenticate maps unsuccessful challenge and verify responses to AuthenticationError", async () => {
  mockFetch([{ body: { success: false, error: "bad challenge" } }]);
  await expect(authForTests().authenticate()).rejects.toThrow(AuthenticationError);

  mockFetch([{ body: { success: true, challenge: "sign this" } }, { body: { success: false, error: "bad verify" } }]);
  await expect(authForTests().authenticate()).rejects.toThrow(AuthenticationError);
});

test("issueCredential returns flattened credential token and metadata", async () => {
  const calls = mockFetch([
    ...authHandshakeResponses(),
    {
      body: {
        credential: {
          id: "cred_1",
          token: "agt_1",
          status: "active",
        },
      },
    },
  ]);

  const result = await authForTests().issueCredential({
    name: "CI bot",
    maxCalls: 10,
    creditLimit: 2,
    resetInterval: "monthly",
    rpm: 30,
    expiresInSec: 600,
  });

  expect(result.token).toBe("agt_1");
  expect(result.credential.credential_id).toBe("cred_1");
  expect(JSON.parse((calls[2].init?.body as string) ?? "{}")).toEqual({
    name: "CI bot",
    maxCalls: 10,
    creditLimit: 2,
    resetInterval: "monthly",
    rpm: 30,
    expiresInSec: 600,
  });
});

test("issueCredential fails when gateway omits credential token or id", async () => {
  mockFetch([...authHandshakeResponses(), { body: { credential: { id: "cred_1" } } }]);
  await expect(authForTests().issueCredential()).rejects.toThrow("Credential token missing");

  mockFetch([...authHandshakeResponses(), { body: { token: "agt_1" } }]);
  await expect(authForTests().issueCredential()).rejects.toThrow("Credential ID missing");
});

test("provider secret and credential list APIs use owner bearer token", async () => {
  const calls = mockFetch([
    ...authHandshakeResponses(),
    { body: { status: "ok", secret: { id: "sec_1", token: "prov_1" } } },
    { body: { secrets: [{ id: "sec_1", token: "prov_1" }] } },
    { body: { credentials: [{ id: "cred_1", token: "agt_1", status: "active" }] } },
  ]);
  const auth = authForTests();

  await expect(auth.issueProviderSecret({ name: "provider" })).resolves.toEqual({
    status: "ok",
    secret: { id: "sec_1", token: "prov_1" },
  });
  await expect(auth.listProviderSecrets()).resolves.toHaveLength(1);
  await expect(auth.listCredentials()).resolves.toHaveLength(1);

  expect(calls.slice(2).every((call) => headersOf(call)["Authorization"] === "Bearer jwt-token")).toBe(true);
});

test("issueProviderSecret fails on malformed gateway payload", async () => {
  mockFetch([...authHandshakeResponses(), { body: { status: "ok", secret: {} } }]);
  await expect(authForTests().issueProviderSecret()).rejects.toThrow("Provider secret payload missing");
});

test("balance, deposit, confirm, and spending limit APIs send expected payloads", async () => {
  const calls = mockFetch([
    ...authHandshakeResponses(),
    { body: { balance: { availableUsdc: 42 } } },
    { body: { status: "registered", intentId: "dep_1" } },
    { body: { status: "confirmed" } },
    { body: { status: "limited" } },
    { body: { status: "unlimited" } },
  ]);
  const auth = authForTests();

  await expect(auth.getBalance()).resolves.toEqual({ availableUsdc: 42 });
  await expect(auth.registerDepositIntent("0xtx", 1.25, "idem-1")).resolves.toEqual({
    status: "registered",
    intentId: "dep_1",
  });
  await expect(auth.confirmDeposit("dep_1", "event-1")).resolves.toEqual({ status: "confirmed" });
  await expect(auth.setSpendingLimit(9.5)).resolves.toBeUndefined();
  await expect(auth.setSpendingLimit(null)).resolves.toBeUndefined();

  expect(headersOf(calls[3])["X-Idempotency-Key"]).toBe("idem-1");
  expect(JSON.parse((calls[4].init?.body as string) ?? "{}")).toEqual({
    eventKey: "event-1",
    confirmations: 1,
  });
  expect(JSON.parse((calls[5].init?.body as string) ?? "{}")).toEqual({
    spendingLimitUsdc: 9.5,
    allowUnlimited: false,
  });
  expect(JSON.parse((calls[6].init?.body as string) ?? "{}")).toEqual({
    allowUnlimited: true,
  });
});

test("registerProviderService validates input and builds provider service contract", async () => {
  await expect(
    authForTests().registerProviderService({
      serviceName: "",
      endpointUrl: "http://provider.local/invoke",
      descriptionForModel: "Summarize text",
      basePriceUsdc: 0.01,
    })
  ).rejects.toThrow("serviceName is required");
  await expect(
    authForTests().registerProviderService({
      serviceName: "Summarizer",
      endpointUrl: "",
      descriptionForModel: "Summarize text",
      basePriceUsdc: 0.01,
    })
  ).rejects.toThrow("endpointUrl is required");
  await expect(
    authForTests().registerProviderService({
      serviceName: "Summarizer",
      endpointUrl: "http://provider.local/invoke",
      descriptionForModel: "",
      basePriceUsdc: 0.01,
    })
  ).rejects.toThrow("descriptionForModel is required");

  const calls = mockFetch([
    ...authHandshakeResponses(),
    { body: { status: "created", service: { serviceId: "summarizer", status: "active" } } },
  ]);

  await expect(
    authForTests().registerProviderService({
      serviceName: "Summarizer Pro",
      endpointUrl: "http://provider.local/invoke",
      descriptionForModel: "Summarize text",
      basePriceUsdc: 0.05,
      tags: ["text"],
      providerDisplayName: "Provider Inc",
    })
  ).resolves.toMatchObject({
    status: "created",
    serviceId: "summarizer",
  });

  const body = JSON.parse((calls[2].init?.body as string) ?? "{}");
  expect(body.serviceId).toBe("summarizer_pro");
  expect(body.pricing).toEqual({ amount: "0.05", currency: "USDC" });
  expect(body.providerProfile).toEqual({ displayName: "Provider Inc" });
  expect(body.payoutAccount.payoutAddress).toBe("0xabcdef");
});

test("registerProviderService preserves explicit provider manifest options", async () => {
  const calls = mockFetch([
    ...authHandshakeResponses(),
    { body: { status: "created", serviceId: "svc_custom", service: { id: "record_1" } } },
  ]);

  await expect(
    authForTests().registerProviderService({
      serviceId: "svc_custom",
      serviceName: "Custom Provider",
      endpointUrl: "https://provider.example/invoke",
      descriptionForModel: "Run the custom provider.",
      basePriceUsdc: "0.25",
      providerDisplayName: "Custom Team",
      payoutAddress: "0x123",
      chainId: 84532,
      settlementCurrency: "USDC",
      tags: ["custom", "paid"],
      status: "paused",
      isActive: false,
      inputSchema: { type: "object", properties: { q: { type: "string" } }, required: ["q"] },
      outputSchema: { type: "object", properties: { answer: { type: "string" } } },
      endpointMethod: "PUT",
      healthPath: "/ready",
      healthMethod: "POST",
      healthTimeoutMs: 5_000,
      requestTimeoutMs: 30_000,
      governanceNote: "accepted in test",
    })
  ).resolves.toMatchObject({ serviceId: "svc_custom" });

  const body = JSON.parse((calls[2].init?.body as string) ?? "{}");
  expect(body).toMatchObject({
    serviceId: "svc_custom",
    status: "paused",
    isActive: false,
    tags: ["custom", "paid"],
    invoke: {
      method: "PUT",
      targets: [{ url: "https://provider.example/invoke" }],
      timeoutMs: 30_000,
    },
    healthCheck: {
      path: "/ready",
      method: "POST",
      timeoutMs: 5_000,
    },
    providerProfile: { displayName: "Custom Team" },
    payoutAccount: {
      payoutAddress: "0x123",
      chainId: 84532,
      settlementCurrency: "USDC",
    },
    governance: {
      termsAccepted: true,
      riskAcknowledged: true,
      note: "accepted in test",
    },
  });
  expect(body.invoke.request.body.required).toEqual(["q"]);
  expect(body.invoke.response.body.properties.answer.type).toBe("string");
});

test("provider service lookup and status derive from listed services", async () => {
  mockFetch([
    ...authHandshakeResponses(),
    {
      body: {
        services: [
          {
            serviceId: "svc_1",
            status: "active",
            runtimeAvailable: true,
            health: { ok: true },
          },
        ],
      },
    },
  ]);
  const auth = authForTests();

  await expect(auth.listProviderServices()).resolves.toHaveLength(1);
  await expect(auth.getProviderService("svc_1")).resolves.toMatchObject({ serviceId: "svc_1" });
  await expect(auth.getProviderServiceStatus("svc_1")).resolves.toEqual({
    serviceId: "svc_1",
    lifecycleStatus: "active",
    runtimeAvailable: true,
    health: { ok: true },
  });
});

test("provider service lookup rejects empty or unknown service id", async () => {
  await expect(authForTests().getProviderService(" ")).rejects.toThrow("serviceId is required");

  mockFetch([...authHandshakeResponses(), { body: { services: [] } }]);
  await expect(authForTests().getProviderService("missing")).rejects.toThrow(AuthenticationError);
});

test("auth fetch includes HTTP detail for non-ok responses", async () => {
  mockFetch([{ status: 500, body: { detail: { code: "BROKEN" } } }]);
  await expect(authForTests().authenticate()).rejects.toThrow("HTTP 500");
});

test("credential lifecycle and owner observability helpers call current gateway routes", async () => {
  const calls = mockFetch([
    ...authHandshakeResponses(),
    { body: { status: "success" } },
    { body: { status: "success" } },
    { body: { status: "success" } },
    { body: { status: "success" } },
    { body: { logs: [] } },
    { body: { profile: { ownerAddress: "0xabcdef" } } },
    { body: { logs: [] } },
    { body: { logs: [] } },
    { body: { risk: "low" } },
  ]);
  const auth = authForTests();

  await auth.revokeCredential("cred_1");
  await auth.rotateCredential("cred_1");
  await auth.updateCredentialQuota("cred_1", { creditLimit: 5, rpm: 60 });
  await auth.deleteCredential("cred_1");
  await auth.getCredentialAuditLogs({ limit: 25 });
  await auth.getOwnerProfile();
  await auth.getUsageLogs({ limit: 10 });
  await auth.getFinanceAuditLogs({ limit: 7 });
  await auth.getRiskOverview();

  expect(calls[2].url).toContain("/api/v1/credentials/agent/cred_1/revoke");
  expect(calls[3].url).toContain("/api/v1/credentials/agent/cred_1/rotate");
  expect(calls[4].url).toContain("/api/v1/credentials/agent/cred_1/quota");
  expect(JSON.parse((calls[4].init?.body as string) ?? "{}")).toEqual({ creditLimit: 5, rpm: 60 });
  expect(calls[5].url).toContain("/api/v1/credentials/agent/cred_1");
  expect(calls[6].url).toContain("/api/v1/credentials/agent/audit-logs?limit=25");
  expect(calls[7].url).toContain("/api/v1/auth/me");
  expect(calls[8].url).toContain("/api/v1/usage/logs?limit=10");
  expect(calls[9].url).toContain("/api/v1/finance/audit-logs?limit=7");
  expect(calls[10].url).toContain("/api/v1/finance/risk-overview");
});

test("logout clears session and credential status aliases share current route", async () => {
  const calls = mockFetch([
    ...authHandshakeResponses(),
    { body: { status: "valid" } },
    { body: { status: "valid" } },
    { body: { status: "logged_out" } },
    { body: { success: true, challenge: "sign again", domain: "synapse" } },
    { body: { success: true, access_token: "jwt-token-2", token_type: "bearer", expires_in: 3600 } },
  ]);
  const auth = authForTests();

  await expect(auth.checkCredentialStatus("cred_1")).resolves.toEqual({ status: "valid" });
  await expect(auth.getCredentialStatus("cred_1")).resolves.toEqual({ status: "valid" });
  await expect(auth.logout()).resolves.toEqual({ status: "logged_out" });
  await expect(auth.getToken()).resolves.toBe("jwt-token-2");

  expect(calls[2].url).toContain("/api/v1/credentials/agent/cred_1/status");
  expect(calls[3].url).toContain("/api/v1/credentials/agent/cred_1/status");
  expect(calls[4].url).toContain("/api/v1/auth/logout");
  expect(calls[5].url).toContain("/api/v1/auth/challenge");
});

test("provider lifecycle and finance helpers call current gateway routes", async () => {
  const calls = mockFetch([
    ...authHandshakeResponses(),
    { body: { status: "success" } },
    { body: { steps: [] } },
    { body: { data: { serviceId: "svc_1" } } },
    { body: { status: "success" } },
    { body: { status: "success" } },
    { body: { status: "success" } },
    { body: { history: [] } },
    { body: { total: "12.34" } },
    { body: { available: true } },
    { body: { intentId: "wd_1" } },
    { body: { withdrawals: [] } },
    { body: { status: "redeemed" } },
  ]);
  const auth = authForTests();

  await auth.deleteProviderSecret("psk_1");
  await auth.getRegistrationGuide();
  await auth.parseCurlToServiceManifest("curl https://provider.example/health");
  await auth.updateProviderService("svc_rec_1", { summary: "updated" });
  await auth.deleteProviderService("svc_rec_1");
  await auth.pingProviderService("svc_rec_1");
  await auth.getProviderServiceHealthHistory("svc_rec_1", { limitPerTarget: 12 });
  await auth.getProviderEarningsSummary();
  await auth.getProviderWithdrawalCapability();
  await auth.createProviderWithdrawalIntent(10, { idempotencyKey: "provider-withdraw-fixed" });
  await auth.listProviderWithdrawals({ limit: 5 });
  await auth.redeemVoucher("ABC123DEF456", "voucher-fixed-1234");

  expect(calls[2].url).toContain("/api/v1/secrets/provider/psk_1");
  expect(calls[3].url).toContain("/api/v1/services/registration-guide");
  expect(calls[4].url).toContain("/api/v1/services/parse-curl");
  expect(JSON.parse((calls[4].init?.body as string) ?? "{}")).toEqual({
    curlCommand: "curl https://provider.example/health",
  });
  expect(calls[5].url).toContain("/api/v1/services/svc_rec_1");
  expect(calls[7].url).toContain("/api/v1/services/svc_rec_1/ping");
  expect(calls[8].url).toContain("/api/v1/services/svc_rec_1/health/history?limitPerTarget=12");
  expect(calls[9].url).toContain("/api/v1/providers/earnings/summary");
  expect(calls[10].url).toContain("/api/v1/providers/withdrawals/capability");
  expect(calls[11].url).toContain("/api/v1/providers/withdrawals/intent");
  expect(headersOf(calls[11])["X-Idempotency-Key"]).toBe("provider-withdraw-fixed");
  expect(calls[12].url).toContain("/api/v1/providers/withdrawals?limit=5");
  expect(calls[13].url).toContain("/api/v1/balance/vouchers/redeem");
});

test("provider facade delegates to owner auth provider methods", async () => {
  const auth = {
    issueProviderSecret: jest.fn(async () => ({ secret: { id: "psk_1" } })),
    listProviderSecrets: jest.fn(async () => []),
    deleteProviderSecret: jest.fn(async () => ({ status: "deleted" })),
    getRegistrationGuide: jest.fn(async () => ({ steps: [] })),
    parseCurlToServiceManifest: jest.fn(async () => ({ manifest: {} })),
    registerProviderService: jest.fn(async () => ({ serviceId: "svc_1", service: { serviceId: "svc_1" } })),
    listProviderServices: jest.fn(async () => []),
    getProviderService: jest.fn(async () => ({ serviceId: "svc_1" })),
    getProviderServiceStatus: jest.fn(async () => ({ serviceId: "svc_1" })),
    updateProviderService: jest.fn(async () => ({ status: "updated" })),
    deleteProviderService: jest.fn(async () => ({ status: "deleted" })),
    pingProviderService: jest.fn(async () => ({ status: "ok" })),
    getProviderServiceHealthHistory: jest.fn(async () => ({ history: [] })),
    getProviderEarningsSummary: jest.fn(async () => ({ total: "0" })),
    getProviderWithdrawalCapability: jest.fn(async () => ({ available: true })),
    createProviderWithdrawalIntent: jest.fn(async () => ({ intentId: "wd_1" })),
    listProviderWithdrawals: jest.fn(async () => ({ withdrawals: [] })),
  } as unknown as SynapseAuth;
  const provider = new SynapseProvider(auth);

  await provider.issueSecret({ name: "provider" });
  await provider.issueSecret();
  await provider.listSecrets();
  await provider.deleteSecret("psk_1");
  await provider.getRegistrationGuide();
  await provider.parseCurlToServiceManifest("curl https://provider.example/health");
  await provider.registerService({
    serviceName: "Weather",
    endpointUrl: "https://provider.example/invoke",
    descriptionForModel: "Weather data",
    basePriceUsdc: 0,
  });
  await provider.listServices();
  await provider.getService("svc_1");
  await provider.getServiceStatus("svc_1");
  await provider.updateService("rec_1", { summary: "updated" });
  await provider.deleteService("rec_1");
  await provider.pingService("rec_1");
  await provider.getServiceHealthHistory("rec_1", { limitPerTarget: 3 });
  await provider.getServiceHealthHistory("rec_2");
  await provider.getEarningsSummary();
  await provider.getWithdrawalCapability();
  await provider.createWithdrawalIntent(5, { idempotencyKey: "fixed", destinationAddress: "0xabc" });
  await provider.createWithdrawalIntent(6);
  await provider.listWithdrawals({ limit: 2 });
  await provider.listWithdrawals();

  expect(auth.issueProviderSecret).toHaveBeenCalledWith({ name: "provider" });
  expect(auth.issueProviderSecret).toHaveBeenCalledWith({});
  expect(auth.deleteProviderSecret).toHaveBeenCalledWith("psk_1");
  expect(auth.registerProviderService).toHaveBeenCalledWith({
    serviceName: "Weather",
    endpointUrl: "https://provider.example/invoke",
    descriptionForModel: "Weather data",
    basePriceUsdc: 0,
  });
  expect(auth.getProviderServiceHealthHistory).toHaveBeenCalledWith("rec_1", { limitPerTarget: 3 });
  expect(auth.getProviderServiceHealthHistory).toHaveBeenCalledWith("rec_2", {});
  expect(auth.createProviderWithdrawalIntent).toHaveBeenCalledWith(5, {
    idempotencyKey: "fixed",
    destinationAddress: "0xabc",
  });
  expect(auth.createProviderWithdrawalIntent).toHaveBeenCalledWith(6, {});
  expect(auth.listProviderWithdrawals).toHaveBeenCalledWith({ limit: 2 });
  expect(auth.listProviderWithdrawals).toHaveBeenCalledWith({});
  expect(authForTests().provider()).toBeInstanceOf(SynapseProvider);
});
