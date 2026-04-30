package ai.synapsenetwork.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.math.BigDecimal;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

public final class SynapseClient {
  public static final String DEFAULT_ENVIRONMENT = "staging";
  public static final String STAGING_GATEWAY_URL = "https://api-staging.synapse-network.ai";
  public static final String PROD_GATEWAY_URL = "https://api.synapse-network.ai";

  private static final ObjectMapper MAPPER = new ObjectMapper();

  private final String credential;
  private final String gatewayUrl;
  private final Duration timeout;
  private final HttpClient httpClient;

  public SynapseClient(Options options) {
    this.credential = requireNonBlank(options.credential, "credential");
    this.gatewayUrl = resolveGatewayUrl(options.environment, options.gatewayUrl);
    this.timeout = options.timeout == null ? Duration.ofSeconds(30) : options.timeout;
    this.httpClient = options.httpClient == null ? HttpClient.newHttpClient() : options.httpClient;
  }

  public static Options options(String credential) {
    return new Options(credential);
  }

  public static String resolveGatewayUrl(String environment, String gatewayUrl) {
    if (gatewayUrl != null && !gatewayUrl.isBlank()) {
      return stripTrailingSlash(gatewayUrl.trim());
    }
    String selected = environment == null || environment.isBlank() ? DEFAULT_ENVIRONMENT : environment.trim().toLowerCase();
    return switch (selected) {
      case "staging" -> STAGING_GATEWAY_URL;
      case "prod" -> PROD_GATEWAY_URL;
      default -> throw new IllegalArgumentException("unsupported Synapse environment: " + selected);
    };
  }

  public List<ServiceRecord> search(String query, SearchOptions options) {
    SearchOptions safeOptions = options == null ? new SearchOptions() : options;
    int pageSize = Math.max(1, safeOptions.limit == null ? 20 : safeOptions.limit);
    int offset = Math.max(0, safeOptions.offset == null ? 0 : safeOptions.offset);
    Map<String, Object> body = new java.util.LinkedHashMap<>();
    if (query != null && !query.isBlank()) {
      body.put("query", query.trim());
    }
    body.put("tags", safeOptions.tags == null ? List.of() : safeOptions.tags);
    body.put("page", (offset / pageSize) + 1);
    body.put("pageSize", pageSize);
    body.put("sort", safeOptions.sort == null || safeOptions.sort.isBlank() ? "best_match" : safeOptions.sort);
    DiscoveryResponse response = post("/api/v1/agent/discovery/search", body, safeOptions.requestId, DiscoveryResponse.class);
    return response.serviceList();
  }

  public List<ServiceRecord> discover(SearchOptions options) {
    return search("", options);
  }

  public InvocationResult invoke(String serviceId, Map<String, Object> payload, InvokeOptions options) {
    InvokeOptions safeOptions = Objects.requireNonNull(options, "options is required");
    if (safeOptions.costUsdc == null || safeOptions.costUsdc.isBlank()) {
      throw new IllegalArgumentException("costUsdc is required for fixed-price API services; use invokeLlm for LLM services");
    }
    Map<String, Object> body = invocationBody(serviceId, payload, safeOptions.idempotencyKey, safeOptions.responseMode);
    body.put("costUsdc", safeOptions.costUsdc);
    return post("/api/v1/agent/invoke", body, safeOptions.requestId, InvocationResult.class);
  }

  public InvocationResult invokeLlm(String serviceId, Map<String, Object> payload, LlmInvokeOptions options) {
    LlmInvokeOptions safeOptions = options == null ? new LlmInvokeOptions() : options;
    if (Boolean.TRUE.equals(payload == null ? null : payload.get("stream"))) {
      throw new InvokeException("LLM_STREAMING_NOT_SUPPORTED", "stream=true is not supported for token-metered billing");
    }
    Map<String, Object> body = invocationBody(serviceId, payload, safeOptions.idempotencyKey, "sync");
    if (safeOptions.maxCostUsdc != null && !safeOptions.maxCostUsdc.isBlank()) {
      body.put("maxCostUsdc", safeOptions.maxCostUsdc);
    }
    return post("/api/v1/agent/invoke", body, safeOptions.requestId, InvocationResult.class);
  }

  public InvocationResult getInvocation(String invocationId) {
    String encoded = URLEncoder.encode(requireNonBlank(invocationId, "invocationId"), StandardCharsets.UTF_8);
    return get("/api/v1/agent/invocations/" + encoded, InvocationResult.class);
  }

  public JsonNode health() {
    return get("/health", JsonNode.class);
  }

  private Map<String, Object> invocationBody(
      String serviceId, Map<String, Object> payload, String idempotencyKey, String responseMode) {
    return new java.util.LinkedHashMap<>(
        Map.of(
            "serviceId", requireNonBlank(serviceId, "serviceId"),
            "idempotencyKey", idempotencyKey == null || idempotencyKey.isBlank() ? UUID.randomUUID().toString() : idempotencyKey,
            "payload", Map.of("body", payload == null ? Map.of() : payload),
            "responseMode", responseMode == null || responseMode.isBlank() ? "sync" : responseMode));
  }

  private <T> T get(String path, Class<T> responseType) {
    HttpRequest request =
        HttpRequest.newBuilder(URI.create(gatewayUrl + path)).timeout(timeout).header("X-Credential", credential).GET().build();
    return send(request, responseType);
  }

  private <T> T post(String path, Map<String, Object> body, String requestId, Class<T> responseType) {
    try {
      HttpRequest.Builder builder =
          HttpRequest.newBuilder(URI.create(gatewayUrl + path))
              .timeout(timeout)
              .header("Content-Type", "application/json")
              .header("X-Credential", credential)
              .POST(HttpRequest.BodyPublishers.ofString(MAPPER.writeValueAsString(body)));
      if (requestId != null && !requestId.isBlank()) {
        builder.header("X-Request-Id", requestId);
      }
      return send(builder.build(), responseType);
    } catch (IOException ex) {
      throw new SynapseException("REQUEST_SERIALIZATION_FAILED", ex.getMessage(), ex);
    }
  }

  private <T> T send(HttpRequest request, Class<T> responseType) {
    try {
      HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
      if (response.statusCode() < 200 || response.statusCode() >= 300) {
        throw mapError(response.statusCode(), response.body());
      }
      return MAPPER.readValue(response.body(), responseType);
    } catch (IOException ex) {
      throw new SynapseException("HTTP_PARSE_FAILED", ex.getMessage(), ex);
    } catch (InterruptedException ex) {
      Thread.currentThread().interrupt();
      throw new SynapseException("HTTP_INTERRUPTED", ex.getMessage(), ex);
    }
  }

  private RuntimeException mapError(int status, String body) {
    JsonNode detail = errorDetail(body);
    String code = detail.path("code").asText("");
    String message = detail.path("message").asText(body);
    if (status == 401) {
      return new AuthenticationException(code, message);
    }
    if (status == 402) {
      return new BudgetException(code, message);
    }
    if (status == 422 && "PRICE_MISMATCH".equals(code)) {
      return new PriceMismatchException(
          code, message, detail.path("expectedPriceUsdc").asText(""), detail.path("currentPriceUsdc").asText(""));
    }
    return new InvokeException(code, message);
  }

  private JsonNode errorDetail(String body) {
    try {
      JsonNode root = MAPPER.readTree(body);
      return root.path("detail");
    } catch (IOException ex) {
      return MAPPER.createObjectNode();
    }
  }

  private static String requireNonBlank(String value, String name) {
    if (value == null || value.isBlank()) {
      throw new IllegalArgumentException(name + " is required");
    }
    return value.trim();
  }

  private static String stripTrailingSlash(String value) {
    return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
  }

  public static final class Options {
    private final String credential;
    private String environment;
    private String gatewayUrl;
    private Duration timeout;
    private HttpClient httpClient;

    private Options(String credential) {
      this.credential = credential;
    }

    public Options environment(String value) {
      this.environment = value;
      return this;
    }

    public Options gatewayUrl(String value) {
      this.gatewayUrl = value;
      return this;
    }

    public Options timeout(Duration value) {
      this.timeout = value;
      return this;
    }

    public Options httpClient(HttpClient value) {
      this.httpClient = value;
      return this;
    }
  }

  public static final class SearchOptions {
    public Integer limit;
    public Integer offset;
    public List<String> tags;
    public String sort;
    public String requestId;
  }

  public static final class InvokeOptions {
    public String costUsdc;
    public String idempotencyKey;
    public String responseMode;
    public String requestId;
  }

  public static final class LlmInvokeOptions {
    public String maxCostUsdc;
    public String idempotencyKey;
    public String requestId;
  }

  @JsonIgnoreProperties(ignoreUnknown = true)
  public record ServiceRecord(
      @JsonProperty("serviceId") String serviceId,
      String id,
      @JsonProperty("serviceName") String serviceName,
      String status,
      @JsonProperty("serviceKind") String serviceKind,
      @JsonProperty("priceModel") String priceModel,
      JsonNode pricing,
      String summary,
      List<String> tags) {}

  @JsonIgnoreProperties(ignoreUnknown = true)
  public record InvocationResult(
      @JsonProperty("invocationId") String invocationId,
      String status,
      @JsonProperty("chargedUsdc") String chargedUsdc,
      JsonNode result,
      JsonNode usage,
      JsonNode synapse,
      JsonNode error,
      JsonNode receipt) {}

  @JsonIgnoreProperties(ignoreUnknown = true)
  private record DiscoveryResponse(List<ServiceRecord> services, List<ServiceRecord> results) {
    List<ServiceRecord> serviceList() {
      return results == null ? (services == null ? List.of() : services) : results;
    }
  }

  public static class SynapseException extends RuntimeException {
    public final String code;

    public SynapseException(String code, String message) {
      super(message);
      this.code = code;
    }

    public SynapseException(String code, String message, Throwable cause) {
      super(message, cause);
      this.code = code;
    }
  }

  public static final class AuthenticationException extends SynapseException {
    public AuthenticationException(String code, String message) {
      super(code, message);
    }
  }

  public static class BudgetException extends SynapseException {
    public BudgetException(String code, String message) {
      super(code, message);
    }
  }

  public static class InvokeException extends SynapseException {
    public InvokeException(String code, String message) {
      super(code, message);
    }
  }

  public static final class PriceMismatchException extends InvokeException {
    public final BigDecimal expectedPriceUsdc;
    public final BigDecimal currentPriceUsdc;

    public PriceMismatchException(String code, String message, String expectedPriceUsdc, String currentPriceUsdc) {
      super(code, message);
      this.expectedPriceUsdc = expectedPriceUsdc.isBlank() ? BigDecimal.ZERO : new BigDecimal(expectedPriceUsdc);
      this.currentPriceUsdc = currentPriceUsdc.isBlank() ? BigDecimal.ZERO : new BigDecimal(currentPriceUsdc);
    }
  }
}
