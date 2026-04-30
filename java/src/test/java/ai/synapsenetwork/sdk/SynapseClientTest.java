package ai.synapsenetwork.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.math.BigDecimal;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import org.junit.jupiter.api.Test;

final class SynapseClientTest {
  @Test
  void resolvesGatewayUrlWithStagingDefaultAndExplicitOverride() {
    assertEquals(
        "https://gateway.example.com",
        SynapseClient.resolveGatewayUrl("staging", "https://gateway.example.com/"));
    assertEquals(SynapseClient.STAGING_GATEWAY_URL, SynapseClient.resolveGatewayUrl(null, null));
    assertThrows(IllegalArgumentException.class, () -> SynapseClient.resolveGatewayUrl("local", null));
  }

  @Test
  void searchInvokeLlmAndReceiptUseContractFixtures() throws Exception {
    try (FixtureServer server = new FixtureServer()) {
      SynapseClient client = new SynapseClient(SynapseClient.options("agt_test").gatewayUrl(server.url()));

      var services = client.search("fixture", new SynapseClient.SearchOptions());
      assertEquals(1, services.size());
      assertEquals("svc_contract_weather", services.get(0).serviceId());

      SynapseClient.LlmInvokeOptions llmOptions = new SynapseClient.LlmInvokeOptions();
      llmOptions.maxCostUsdc = "0.010000";
      llmOptions.idempotencyKey = "idem-llm";
      var result = client.invokeLlm(
          "svc_deepseek_chat",
          Map.of("messages", java.util.List.of(Map.of("role", "user", "content", "hello"))),
          llmOptions);
      assertEquals("inv_contract_llm", result.invocationId());
      assertEquals("0.004200", result.chargedUsdc());
      assertFalse(server.lastInvokeBody.contains("costUsdc"));
      assertTrue(server.lastInvokeBody.contains("\"maxCostUsdc\":\"0.010000\""));

      var receipt = client.getInvocation("inv_contract_llm");
      assertEquals("SETTLED", receipt.status());
    }
  }

  @Test
  void fixedPriceInvokeRequiresCostAndMapsPriceMismatch() throws Exception {
    try (FixtureServer server = new FixtureServer()) {
      server.priceMismatch = true;
      SynapseClient client = new SynapseClient(SynapseClient.options("agt_test").gatewayUrl(server.url()));
      assertThrows(IllegalArgumentException.class, () -> client.invoke("svc", Map.of(), new SynapseClient.InvokeOptions()));

      SynapseClient.InvokeOptions opts = new SynapseClient.InvokeOptions();
      opts.costUsdc = "0.010000";
      SynapseClient.PriceMismatchException err =
          assertThrows(SynapseClient.PriceMismatchException.class, () -> client.invoke("svc", Map.of(), opts));
      assertEquals(new BigDecimal("0.012000"), err.currentPriceUsdc);
    }
  }

  private static final class FixtureServer implements AutoCloseable {
    private final HttpServer server;
    boolean priceMismatch;
    String lastInvokeBody = "";

    FixtureServer() throws IOException {
      server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
      server.createContext("/", this::handle);
      server.start();
    }

    String url() {
      return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    private void handle(HttpExchange exchange) throws IOException {
      assertEquals("agt_test", exchange.getRequestHeaders().getFirst("X-Credential"));
      String path = exchange.getRequestURI().getPath();
      if (path.equals("/api/v1/agent/discovery/search")) {
        write(exchange, 200, fixture("discovery_search_response.json"));
      } else if (path.equals("/api/v1/agent/invoke")) {
        lastInvokeBody = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
        write(exchange, priceMismatch ? 422 : 200, fixture(priceMismatch ? "error_price_mismatch.json" : "llm_invoke_response.json"));
      } else if (path.equals("/api/v1/agent/invocations/inv_contract_llm")) {
        write(exchange, 200, fixture("receipt_response.json"));
      } else {
        write(exchange, 404, "{}");
      }
    }

    private String fixture(String name) throws IOException {
      return Files.readString(Path.of("..", "contracts", "sdk", "fixtures", name));
    }

    private void write(HttpExchange exchange, int status, String body) throws IOException {
      byte[] raw = body.getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(status, raw.length);
      exchange.getResponseBody().write(raw);
      exchange.close();
    }

    @Override
    public void close() {
      server.stop(0);
    }
  }
}
