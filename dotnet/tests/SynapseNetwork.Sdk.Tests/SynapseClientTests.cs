using System.Net;
using System.Text;
using SynapseNetwork.Sdk;
using Xunit;

namespace SynapseNetwork.Sdk.Tests;

public sealed class SynapseClientTests
{
    [Fact]
    public void ResolvesGatewayUrlWithStagingDefaultAndExplicitOverride()
    {
        Assert.Equal("https://gateway.example.com", SynapseClient.ResolveGatewayUrl(gatewayUrl: "https://gateway.example.com/"));
        Assert.Equal(SynapseClient.StagingGatewayUrl, SynapseClient.ResolveGatewayUrl());
        Assert.Throws<ArgumentException>(() => SynapseClient.ResolveGatewayUrl(environment: "local"));
    }

    [Fact]
    public async Task SearchInvokeLlmAndReceiptUseContractFixtures()
    {
        var handler = new FixtureHandler();
        var client = new SynapseClient(new SynapseClientOptions
        {
            Credential = "agt_test",
            GatewayUrl = "https://gateway.test",
            HttpClient = new HttpClient(handler),
        });

        var services = await client.SearchAsync("fixture", new SearchOptions { Limit = 10 });
        Assert.Single(services);
        Assert.Equal("svc_contract_weather", services[0].ServiceId);

        var result = await client.InvokeLlmAsync(
            "svc_deepseek_chat",
            new Dictionary<string, object?>
            {
                ["messages"] = new[] { new Dictionary<string, object?> { ["role"] = "user", ["content"] = "hello" } },
            },
            new LlmInvokeOptions { MaxCostUsdc = "0.010000", IdempotencyKey = "idem-llm" });
        Assert.Equal("inv_contract_llm", result.InvocationId);
        Assert.Equal("0.004200", result.ChargedUsdc);
        Assert.DoesNotContain("costUsdc", handler.LastInvokeBody);
        Assert.Contains("\"maxCostUsdc\":\"0.010000\"", handler.LastInvokeBody);

        var receipt = await client.GetInvocationAsync("inv_contract_llm");
        Assert.Equal("SETTLED", receipt.Status);
    }

    [Fact]
    public async Task FixedPriceInvokeRequiresCostAndMapsPriceMismatch()
    {
        var handler = new FixtureHandler { PriceMismatch = true };
        var client = new SynapseClient(new SynapseClientOptions
        {
            Credential = "agt_test",
            GatewayUrl = "https://gateway.test",
            HttpClient = new HttpClient(handler),
        });

        await Assert.ThrowsAsync<ArgumentException>(() => client.InvokeAsync("svc", null, new InvokeOptions { CostUsdc = "" }));
        var error = await Assert.ThrowsAsync<PriceMismatchException>(() =>
            client.InvokeAsync("svc", null, new InvokeOptions { CostUsdc = "0.010000" }));
        Assert.Equal(0.012000m, error.CurrentPriceUsdc);
    }

    private sealed class FixtureHandler : HttpMessageHandler
    {
        public bool PriceMismatch { get; init; }
        public string LastInvokeBody { get; private set; } = "";

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Assert.Equal("agt_test", request.Headers.GetValues("X-Credential").Single());
            var path = request.RequestUri?.AbsolutePath ?? "";
            if (path == "/api/v1/agent/discovery/search")
            {
                return Json("discovery_search_response.json");
            }
            if (path == "/api/v1/agent/invoke")
            {
                LastInvokeBody = request.Content == null ? "" : await request.Content.ReadAsStringAsync(cancellationToken);
                return Json(PriceMismatch ? "error_price_mismatch.json" : "llm_invoke_response.json", PriceMismatch ? HttpStatusCode.UnprocessableEntity : HttpStatusCode.OK);
            }
            if (path == "/api/v1/agent/invocations/inv_contract_llm")
            {
                return Json("receipt_response.json");
            }
            return new HttpResponseMessage(HttpStatusCode.NotFound) { Content = new StringContent("{}") };
        }

        private static HttpResponseMessage Json(string fixtureName, HttpStatusCode status = HttpStatusCode.OK)
        {
            return new HttpResponseMessage(status)
            {
                Content = new StringContent(File.ReadAllText(FixturePath(fixtureName)), Encoding.UTF8, "application/json"),
            };
        }

        private static string FixturePath(string fixtureName)
        {
            var directory = new DirectoryInfo(Environment.CurrentDirectory);
            while (directory != null)
            {
                var candidate = Path.Combine(directory.FullName, "contracts", "sdk", "fixtures", fixtureName);
                if (File.Exists(candidate))
                {
                    return candidate;
                }
                directory = directory.Parent;
            }
            throw new FileNotFoundException(fixtureName);
        }
    }
}
