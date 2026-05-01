package ai.synapsenetwork.sdk;

import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.math.BigInteger;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.web3j.crypto.Keys;
import org.web3j.crypto.Sign;
import org.web3j.utils.Numeric;

final class SynapseAuthTest {
  private static final String PRIVATE_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

  @Test
  void fromPrivateKeySignsChallengeAndCachesToken() throws Exception {
    try (FixtureServer server = new FixtureServer()) {
      SynapseAuth auth = SynapseAuth.fromPrivateKey(PRIVATE_KEY, options(server.url()));

      assertEquals("jwt_owner", auth.getToken());
      assertEquals("jwt_owner", auth.getToken());
      assertEquals(1, server.challengeCalls);
      assertEquals(1, server.verifyCalls);
      assertEquals("0xowner", auth.getOwnerProfile().ownerAddress());
    }
  }

  @Test
  void credentialFinanceAndProviderRoutesReturnNamedObjects() throws Exception {
    try (FixtureServer server = new FixtureServer()) {
      SynapseAuth auth = SynapseAuth.fromPrivateKey(PRIVATE_KEY, options(server.url()));
      SynapseAuth.IssueCredentialResult issued = auth.issueCredential(new SynapseAuth.CredentialOptions());
      assertEquals("agt_1", issued.token());
      assertEquals("cred_1", issued.credential().id());

      assertEquals(1, auth.listCredentials().size());
      assertEquals("success", auth.updateCredentialQuota("cred_1", new SynapseAuth.CredentialQuotaOptions()).status());
      assertEquals("1.00", auth.getBalance().ownerBalance().asText());
      assertEquals(1, auth.getUsageLogs(5).logs().size());

      SynapseProvider provider = auth.provider();
      assertEquals(1, provider.getRegistrationGuide().steps().size());
      SynapseAuth.RegisterProviderServiceOptions serviceOptions = new SynapseAuth.RegisterProviderServiceOptions();
      serviceOptions.serviceName = "Weather";
      serviceOptions.endpointUrl = "https://provider.example.com/invoke";
      serviceOptions.basePriceUsdc = "0.01";
      serviceOptions.descriptionForModel = "Weather";
      assertEquals("svc_weather", provider.registerService(serviceOptions).serviceId());
      assertTrue(provider.getServiceStatus("svc_weather").runtimeAvailable());
      assertEquals("success", provider.updateService("rec_1", Map.of("status", "active")).status());
      assertEquals("wd_1", provider.createWithdrawalIntent("0.10", "idem", "0xabc").intentId());

      assertTrue(server.seen.contains("POST /api/v1/credentials/agent/issue"));
      assertTrue(server.seen.contains("GET /api/v1/balance"));
      assertTrue(server.seen.contains("POST /api/v1/services"));
      assertTrue(server.seen.contains("POST /api/v1/providers/withdrawals/intent"));
    }
  }

  private static SynapseAuth.Options options(String gatewayUrl) {
    SynapseAuth.Options options = new SynapseAuth.Options();
    options.gatewayUrl = gatewayUrl;
    return options;
  }

  private static final class FixtureServer implements AutoCloseable {
    private final HttpServer server;
    final List<String> seen = new ArrayList<>();
    int challengeCalls;
    int verifyCalls;

    FixtureServer() throws IOException {
      server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
      server.createContext("/", this::handle);
      server.start();
    }

    String url() {
      return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    private void handle(HttpExchange exchange) throws IOException {
      String path = exchange.getRequestURI().getPath();
      seen.add(exchange.getRequestMethod() + " " + path);
      if (path.startsWith("/api/v1/auth/")) {
        auth(exchange, path);
        return;
      }
      assertEquals("Bearer jwt_owner", exchange.getRequestHeaders().getFirst("Authorization"));
      switch (path) {
        case "/api/v1/credentials/agent/issue" -> write(exchange, "{\"credential\":{\"id\":\"cred_1\",\"token\":\"agt_1\",\"status\":\"active\"},\"token\":\"agt_1\"}");
        case "/api/v1/credentials/agent/list" -> write(exchange, "{\"credentials\":[{\"id\":\"cred_1\",\"name\":\"agent\",\"status\":\"active\"}]}");
        case "/api/v1/credentials/agent/cred_1/quota" -> write(exchange, "{\"status\":\"success\",\"credentialId\":\"cred_1\"}");
        case "/api/v1/balance" -> write(exchange, "{\"balance\":{\"ownerBalance\":\"1.00\"}}");
        case "/api/v1/usage/logs" -> write(exchange, "{\"logs\":[{\"id\":\"usage_1\"}]}");
        case "/api/v1/services/registration-guide" -> write(exchange, "{\"steps\":[\"register\"]}");
        case "/api/v1/services" -> {
          if ("POST".equals(exchange.getRequestMethod())) write(exchange, "{\"status\":\"success\",\"serviceId\":\"svc_weather\",\"service\":{\"serviceId\":\"svc_weather\"}}");
          else write(exchange, "{\"services\":[{\"serviceId\":\"svc_weather\",\"status\":\"active\",\"runtimeAvailable\":true}]}");
        }
        case "/api/v1/services/rec_1" -> write(exchange, "{\"status\":\"success\"}");
        case "/api/v1/providers/withdrawals/intent" -> write(exchange, "{\"status\":\"success\",\"intentId\":\"wd_1\"}");
        default -> write(exchange, "{\"status\":\"success\"}");
      }
    }

    private void auth(HttpExchange exchange, String path) throws IOException {
      if (path.equals("/api/v1/auth/challenge")) {
        challengeCalls++;
        assertEquals("0xfcad0b19bb29d4674531d6f115237e16afce377c", exchange.getRequestURI().getQuery().split("=")[1]);
        write(exchange, "{\"success\":true,\"challenge\":\"sign me\"}");
        return;
      }
      if (path.equals("/api/v1/auth/me")) {
        assertEquals("Bearer jwt_owner", exchange.getRequestHeaders().getFirst("Authorization"));
        write(exchange, "{\"ownerAddress\":\"0xowner\"}");
        return;
      }
      verifyCalls++;
      String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
      assertTrue(validSignature(body));
      write(exchange, "{\"success\":true,\"access_token\":\"jwt_owner\",\"expires_in\":3600}");
    }

    private static boolean validSignature(String body) {
      String signature = body.replaceAll(".*\\\"signature\\\":\\\"([^\\\"]+)\\\".*", "$1");
      byte[] raw = Numeric.hexStringToByteArray(signature);
      Sign.SignatureData data = new Sign.SignatureData(raw[64], Arrays.copyOfRange(raw, 0, 32), Arrays.copyOfRange(raw, 32, 64));
      try {
        BigInteger key = Sign.signedPrefixedMessageToKey("sign me".getBytes(StandardCharsets.UTF_8), data);
        return ("0x" + Keys.getAddress(key)).equals("0xfcad0b19bb29d4674531d6f115237e16afce377c");
      } catch (Exception ex) {
        return false;
      }
    }

    private static void write(HttpExchange exchange, String body) throws IOException {
      byte[] raw = body.getBytes(StandardCharsets.UTF_8);
      exchange.getResponseHeaders().set("Content-Type", "application/json");
      exchange.sendResponseHeaders(200, raw.length);
      exchange.getResponseBody().write(raw);
      exchange.close();
    }

    @Override
    public void close() {
      server.stop(0);
    }
  }
}
