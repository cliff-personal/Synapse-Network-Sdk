using System.Net;
using System.Text;
using System.Text.Json;
using Nethereum.Signer;
using SynapseNetwork.Sdk;
using Xunit;

namespace SynapseNetwork.Sdk.Tests;

public sealed class SynapseAuthTests
{
    private const string PrivateKey = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    [Fact]
    public async Task FromPrivateKeySignsChallengeAndCachesToken()
    {
        var handler = new AuthFixtureHandler();
        var auth = SynapseAuth.FromPrivateKey(PrivateKey, new SynapseAuthOptions
        {
            GatewayUrl = "https://gateway.test",
            HttpClient = new HttpClient(handler),
        });

        Assert.Equal("jwt_owner", await auth.GetTokenAsync());
        Assert.Equal("jwt_owner", await auth.GetTokenAsync());
        Assert.Equal(1, handler.ChallengeCalls);
        Assert.Equal(1, handler.VerifyCalls);
        Assert.Equal("0xowner", (await auth.GetOwnerProfileAsync()).OwnerAddress);
    }

    [Fact]
    public async Task CredentialFinanceAndProviderRoutesReturnNamedObjects()
    {
        var handler = new AuthFixtureHandler();
        var auth = SynapseAuth.FromPrivateKey(PrivateKey, new SynapseAuthOptions
        {
            GatewayUrl = "https://gateway.test",
            HttpClient = new HttpClient(handler),
        });

        var issued = await auth.IssueCredentialAsync(new CredentialOptions { Name = "agent" });
        Assert.Equal("agt_1", issued.Token);
        Assert.Equal("cred_1", issued.Credential.Id);
        Assert.Single(await auth.ListCredentialsAsync());
        Assert.Equal("success", (await auth.UpdateCredentialQuotaAsync("cred_1", new CredentialQuotaOptions { CreditLimit = "1.00" })).Status);
        Assert.Equal("1.00", (await auth.GetBalanceAsync()).OwnerBalance?.GetString());
        Assert.Single((await auth.GetUsageLogsAsync(5)).Logs ?? Array.Empty<JsonElement>());

        var provider = auth.Provider();
        Assert.Single((await provider.GetRegistrationGuideAsync()).Steps ?? Array.Empty<JsonElement>());
        var service = await provider.RegisterServiceAsync(new RegisterProviderServiceOptions
        {
            ServiceName = "Weather",
            EndpointUrl = "https://provider.example.com/invoke",
            BasePriceUsdc = "0.01",
            DescriptionForModel = "Weather",
        });
        Assert.Equal("svc_weather", service.ServiceId);
        Assert.True((await provider.GetServiceStatusAsync("svc_weather")).RuntimeAvailable);
        Assert.Equal("success", (await provider.UpdateServiceAsync("rec_1", new Dictionary<string, object?> { ["status"] = "active" })).Status);
        Assert.Equal("wd_1", (await provider.CreateWithdrawalIntentAsync("0.10", "idem", "0xabc")).IntentId);

        Assert.Contains("POST /api/v1/credentials/agent/issue", handler.Seen);
        Assert.Contains("GET /api/v1/balance", handler.Seen);
        Assert.Contains("POST /api/v1/services", handler.Seen);
        Assert.Contains("POST /api/v1/providers/withdrawals/intent", handler.Seen);
    }

    private sealed class AuthFixtureHandler : HttpMessageHandler
    {
        public List<string> Seen { get; } = [];
        public int ChallengeCalls { get; private set; }
        public int VerifyCalls { get; private set; }

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var path = request.RequestUri?.AbsolutePath ?? "";
            Seen.Add(request.Method.Method + " " + path);
            if (path.StartsWith("/api/v1/auth/", StringComparison.Ordinal))
            {
                return await Auth(request, path, cancellationToken);
            }
            Assert.Equal("Bearer jwt_owner", request.Headers.GetValues("Authorization").Single());
            return path switch
            {
                "/api/v1/credentials/agent/issue" => Json("""{"credential":{"id":"cred_1","token":"agt_1","status":"active"},"token":"agt_1"}"""),
                "/api/v1/credentials/agent/list" => Json("""{"credentials":[{"id":"cred_1","name":"agent","status":"active"}]}"""),
                "/api/v1/credentials/agent/cred_1/quota" => Json("""{"status":"success","credentialId":"cred_1"}"""),
                "/api/v1/balance" => Json("""{"balance":{"ownerBalance":"1.00"}}"""),
                "/api/v1/usage/logs" => Json("""{"logs":[{"id":"usage_1"}]}"""),
                "/api/v1/services/registration-guide" => Json("""{"steps":["register"]}"""),
                "/api/v1/services" when request.Method == HttpMethod.Post => Json("""{"status":"success","serviceId":"svc_weather","service":{"serviceId":"svc_weather"}}"""),
                "/api/v1/services" => Json("""{"services":[{"serviceId":"svc_weather","status":"active","runtimeAvailable":true}]}"""),
                "/api/v1/services/rec_1" => Json("""{"status":"success"}"""),
                "/api/v1/providers/withdrawals/intent" => Json("""{"status":"success","intentId":"wd_1"}"""),
                _ => Json("""{"status":"success"}"""),
            };
        }

        private async Task<HttpResponseMessage> Auth(HttpRequestMessage request, string path, CancellationToken cancellationToken)
        {
            if (path == "/api/v1/auth/challenge")
            {
                ChallengeCalls++;
                Assert.Contains("address=0xfcad0b19bb29d4674531d6f115237e16afce377c", request.RequestUri?.Query);
                return Json("""{"success":true,"challenge":"sign me"}""");
            }
            if (path == "/api/v1/auth/me")
            {
                Assert.Equal("Bearer jwt_owner", request.Headers.GetValues("Authorization").Single());
                return Json("""{"ownerAddress":"0xowner"}""");
            }
            VerifyCalls++;
            var body = request.Content == null ? "" : await request.Content.ReadAsStringAsync(cancellationToken);
            Assert.True(ValidSignature(body));
            return Json("""{"success":true,"access_token":"jwt_owner","expires_in":3600}""");
        }

        private static bool ValidSignature(string body)
        {
            using var doc = JsonDocument.Parse(body);
            var signature = doc.RootElement.GetProperty("signature").GetString();
            var signer = new EthereumMessageSigner();
            return signer.EncodeUTF8AndEcRecover("sign me", signature) == "0xFCAd0B19bB29D4674531d6f115237E16AfCE377c";
        }

        private static HttpResponseMessage Json(string body)
            => new(HttpStatusCode.OK) { Content = new StringContent(body, Encoding.UTF8, "application/json") };
    }
}
