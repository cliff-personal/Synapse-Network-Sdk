package ai.synapsenetwork.sdk.examples;

import ai.synapsenetwork.sdk.SynapseClient;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class ExampleSupport {
  private static final ObjectMapper MAPPER = new ObjectMapper();

  private ExampleSupport() {}

  static SynapseClient client() {
    return client(requireEnv("SYNAPSE_AGENT_KEY"));
  }

  static SynapseClient client(String credential) {
    SynapseClient.Options options = SynapseClient.options(credential);
    String gatewayUrl = System.getenv("SYNAPSE_GATEWAY_URL");
    if (gatewayUrl != null && !gatewayUrl.isBlank()) {
      options.gatewayUrl(gatewayUrl);
    } else {
      options.environment("staging");
    }
    return new SynapseClient(options);
  }

  static FixedTarget fixedTarget(SynapseClient client) {
    Map<String, Object> configuredPayload = payload("SYNAPSE_E2E_FIXED_PAYLOAD_JSON", Map.of("prompt", "hello"));
    String configuredServiceId = System.getenv("SYNAPSE_E2E_FIXED_SERVICE_ID");
    if (configuredServiceId != null && !configuredServiceId.isBlank()) {
      String cost = System.getenv("SYNAPSE_E2E_FIXED_COST_USDC");
      if (cost == null || cost.isBlank()) {
        fail("SYNAPSE_E2E_FIXED_COST_USDC is required when SYNAPSE_E2E_FIXED_SERVICE_ID is set");
      }
      return new FixedTarget(configuredServiceId.trim(), cost.trim(), configuredPayload);
    }

    SynapseClient.SearchOptions options = new SynapseClient.SearchOptions();
    options.limit = 25;
    List<SynapseClient.ServiceRecord> services = client.search("free", options);
    for (SynapseClient.ServiceRecord service : services) {
      String amount = pricingAmount(service);
      if (isFreeFixedApiService(service)) {
        return new FixedTarget(service.serviceId(), amount, configuredPayload);
      }
    }
    fail(
        "no free fixed-price API service found; set SYNAPSE_E2E_FIXED_SERVICE_ID, "
            + "SYNAPSE_E2E_FIXED_COST_USDC, and SYNAPSE_E2E_FIXED_PAYLOAD_JSON");
    throw new IllegalStateException("unreachable");
  }

  static boolean isFreeFixedApiService(SynapseClient.ServiceRecord service) {
    return service.serviceId() != null
        && "api".equalsIgnoreCase(service.serviceKind())
        && "fixed".equalsIgnoreCase(service.priceModel())
        && decimalEquals(pricingAmount(service), "0");
  }

  static SynapseClient.InvocationResult awaitReceipt(SynapseClient client, String invocationId) {
    if (invocationId == null || invocationId.isBlank()) {
      fail("invoke returned empty invocationId");
    }
    long deadline = System.currentTimeMillis() + Duration.ofSeconds(envInt("SYNAPSE_E2E_RECEIPT_TIMEOUT_S", 60)).toMillis();
    while (true) {
      SynapseClient.InvocationResult receipt = client.getInvocation(invocationId);
      if (receipt.invocationId() != null && !receipt.invocationId().isBlank() && !receipt.invocationId().equals(invocationId)) {
        fail("receipt invocationId mismatch: got " + receipt.invocationId() + " want " + invocationId);
      }
      if (terminal(receipt.status())) {
        return receipt;
      }
      if (System.currentTimeMillis() > deadline) {
        fail("receipt " + invocationId + " did not reach a terminal status, last status=" + receipt.status());
      }
      try {
        Thread.sleep(2000);
      } catch (InterruptedException ex) {
        Thread.currentThread().interrupt();
        fail("interrupted while waiting for receipt");
      }
    }
  }

  static Map<String, Object> payload(String name, Map<String, Object> fallback) {
    String raw = System.getenv(name);
    if (raw == null || raw.isBlank()) {
      return fallback;
    }
    try {
      return MAPPER.readValue(raw, new TypeReference<Map<String, Object>>() {});
    } catch (Exception ex) {
      throw new IllegalArgumentException(name + " must be a JSON object", ex);
    }
  }

  static void emit(
      String scenario,
      String status,
      String invocationId,
      String chargedUsdc,
      String receiptStatus,
      String serviceId) {
    try {
      Map<String, String> event = new LinkedHashMap<>();
      event.put("language", "java");
      event.put("scenario", scenario);
      putIfPresent(event, "invocationId", invocationId);
      putIfPresent(event, "status", status);
      putIfPresent(event, "chargedUsdc", chargedUsdc);
      putIfPresent(event, "receiptStatus", receiptStatus);
      putIfPresent(event, "serviceId", serviceId);
      System.out.println(MAPPER.writeValueAsString(event));
    } catch (Exception ex) {
      fail(ex.getMessage());
    }
  }

  static String envDefault(String name, String fallback) {
    String value = System.getenv(name);
    return value == null || value.isBlank() ? fallback : value;
  }

  static int envInt(String name, int fallback) {
    String value = System.getenv(name);
    if (value == null || value.isBlank()) {
      return fallback;
    }
    try {
      int parsed = Integer.parseInt(value);
      return parsed > 0 ? parsed : fallback;
    } catch (NumberFormatException ex) {
      return fallback;
    }
  }

  static boolean envBool(String name) {
    String value = System.getenv(name);
    return value != null
        && ("1".equals(value.trim())
            || "true".equalsIgnoreCase(value.trim())
            || "yes".equalsIgnoreCase(value.trim())
            || "y".equalsIgnoreCase(value.trim()));
  }

  static String firstNonBlank(String... values) {
    for (String value : values) {
      if (value != null && !value.isBlank()) {
        return value.trim();
      }
    }
    return "";
  }

  static void expectFailure(Runnable action, Class<? extends Throwable> expectedType) {
    try {
      action.run();
    } catch (Throwable ex) {
      if (expectedType.isInstance(ex)) {
        return;
      }
      fail("expected " + expectedType.getSimpleName() + ", got " + ex.getClass().getSimpleName() + ": " + ex.getMessage());
    }
    fail("expected " + expectedType.getSimpleName());
  }

  static void fail(String message) {
    System.err.println("java example failed: " + message);
    System.exit(1);
  }

  private static String requireEnv(String name) {
    String value = System.getenv(name);
    if (value == null || value.isBlank()) {
      fail(name + " is required");
    }
    return value.trim();
  }

  private static boolean terminal(String status) {
    return "SUCCEEDED".equalsIgnoreCase(status) || "SETTLED".equalsIgnoreCase(status);
  }

  private static boolean decimalEquals(String left, String right) {
    if (left == null || left.isBlank()) {
      return false;
    }
    return new BigDecimal(left).compareTo(new BigDecimal(right)) == 0;
  }

  private static String pricingAmount(SynapseClient.ServiceRecord service) {
    return service.pricing() == null ? "" : service.pricing().path("amount").asText("");
  }

  private static void putIfPresent(Map<String, String> target, String key, String value) {
    if (value != null && !value.isBlank()) {
      target.put(key, value);
    }
  }

  record FixedTarget(String serviceId, String costUsdc, Map<String, Object> payload) {}
}
