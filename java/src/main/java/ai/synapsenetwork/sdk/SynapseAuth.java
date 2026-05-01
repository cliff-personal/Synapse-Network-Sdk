package ai.synapsenetwork.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.DeserializationFeature;
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
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import org.web3j.crypto.Credentials;
import org.web3j.crypto.Sign;
import org.web3j.utils.Numeric;

public final class SynapseAuth {
  private static final ObjectMapper MAPPER = new ObjectMapper().configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);

  private final String walletAddress;
  private final String gatewayUrl;
  private final Duration timeout;
  private final HttpClient httpClient;
  private final Signer signer;
  private String token;
  private Instant tokenExpiresAt = Instant.EPOCH;

  public SynapseAuth(Options options) {
    this.walletAddress = requireNonBlank(options.walletAddress, "walletAddress").toLowerCase();
    this.gatewayUrl = SynapseClient.resolveGatewayUrl(options.environment, options.gatewayUrl);
    this.timeout = options.timeout == null ? Duration.ofSeconds(30) : options.timeout;
    this.httpClient = options.httpClient == null ? HttpClient.newHttpClient() : options.httpClient;
    this.signer = Objects.requireNonNull(options.signer, "signer is required");
  }

  public static SynapseAuth fromPrivateKey(String privateKey, Options options) {
    Credentials credentials = Credentials.create(privateKey);
    Options resolved = options == null ? new Options() : options;
    resolved.walletAddress = credentials.getAddress();
    resolved.signer = message -> {
      Sign.SignatureData signature = Sign.signPrefixedMessage(message.getBytes(StandardCharsets.UTF_8), credentials.getEcKeyPair());
      return "0x" + Numeric.toHexStringNoPrefix(signature.getR()) + Numeric.toHexStringNoPrefix(signature.getS()) + Numeric.toHexStringNoPrefix(signature.getV());
    };
    return new SynapseAuth(resolved);
  }

  public SynapseProvider provider() {
    return new SynapseProvider(this);
  }

  public String authenticate() {
    if (token != null && Instant.now().isBefore(tokenExpiresAt.minusSeconds(30))) {
      return token;
    }
    ChallengeResponse challenge = get("/api/v1/auth/challenge?address=" + encode(walletAddress), ChallengeResponse.class, null);
    if (!challenge.success() || challenge.challenge() == null || challenge.challenge().isBlank()) {
      throw new SynapseClient.AuthenticationException("AUTH_CHALLENGE_FAILED", "challenge request did not return a usable challenge");
    }
    TokenResponse response =
        request(
            "POST",
            "/api/v1/auth/verify",
            Map.of(
                "wallet_address", walletAddress,
                "message", challenge.challenge(),
                "signature", signer.sign(challenge.challenge())),
            TokenResponse.class,
            null,
            null);
    if (!response.success() || response.accessToken() == null || response.accessToken().isBlank()) {
      throw new SynapseClient.AuthenticationException("AUTH_VERIFY_FAILED", "auth verify did not return an access token");
    }
    token = response.accessToken();
    tokenExpiresAt = Instant.now().plusSeconds(Math.max(0, response.expiresIn()));
    return token;
  }

  public String getToken() {
    return authenticate();
  }

  public AuthLogoutResult logout() {
    AuthLogoutResult result = ownerRequest("POST", "/api/v1/auth/logout", null, AuthLogoutResult.class);
    token = null;
    tokenExpiresAt = Instant.EPOCH;
    return result;
  }

  public OwnerProfile getOwnerProfile() {
    return ownerRequest("GET", "/api/v1/auth/me", null, OwnerProfile.class);
  }

  public IssueCredentialResult issueCredential(CredentialOptions options) {
    JsonNode raw = ownerRequest("POST", "/api/v1/credentials/agent/issue", credentialBody(options), JsonNode.class);
    AgentCredential credential = MAPPER.convertValue(raw.path("credential"), AgentCredential.class);
    String tokenValue = firstText(raw.path("token").asText(""), credential.token(), raw.path("credential_token").asText(""));
    String id = firstText(raw.path("credential_id").asText(""), raw.path("id").asText(""), credential.id(), credential.credentialId());
    if (tokenValue.isBlank() || id.isBlank()) {
      throw new SynapseClient.AuthenticationException("CREDENTIAL_PAYLOAD_MISSING", raw.toString());
    }
    return new IssueCredentialResult(new AgentCredential(id, id, tokenValue, firstText(credential.name(), options == null ? "" : options.name), "active"), tokenValue);
  }

  public List<AgentCredential> listCredentials() {
    return credentialList("/api/v1/credentials/agent/list");
  }

  public List<AgentCredential> listActiveCredentials() {
    return credentialList("/api/v1/credentials/agent/list?active_only=true");
  }

  public CredentialStatusResult getCredentialStatus(String credentialId) {
    return ownerRequest("GET", "/api/v1/credentials/agent/" + encodeRequired(credentialId, "credentialId") + "/status", null, CredentialStatusResult.class);
  }

  public CredentialStatusResult checkCredentialStatus(String credentialId) {
    return getCredentialStatus(credentialId);
  }

  public CredentialRevokeResult revokeCredential(String credentialId) {
    return ownerRequest("POST", "/api/v1/credentials/agent/" + encodeRequired(credentialId, "credentialId") + "/revoke", null, CredentialRevokeResult.class);
  }

  public CredentialRotateResult rotateCredential(String credentialId) {
    return ownerRequest("POST", "/api/v1/credentials/agent/" + encodeRequired(credentialId, "credentialId") + "/rotate", null, CredentialRotateResult.class);
  }

  public CredentialDeleteResult deleteCredential(String credentialId) {
    return ownerRequest("DELETE", "/api/v1/credentials/agent/" + encodeRequired(credentialId, "credentialId"), null, CredentialDeleteResult.class);
  }

  public CredentialQuotaUpdateResult updateCredentialQuota(String credentialId, CredentialQuotaOptions options) {
    return ownerRequest("PATCH", "/api/v1/credentials/agent/" + encodeRequired(credentialId, "credentialId") + "/quota", quotaBody(options), CredentialQuotaUpdateResult.class);
  }

  public CredentialAuditLogList getCredentialAuditLogs(int limit) {
    return ownerRequest("GET", withQuery("/api/v1/credentials/agent/audit-logs", Map.of("limit", limitOrDefault(limit))), null, CredentialAuditLogList.class);
  }

  public String ensureCredential(String name, CredentialOptions options) {
    for (AgentCredential credential : listActiveCredentials()) {
      if (Objects.equals(credential.name(), name)) {
        if (credential.token() != null && !credential.token().isBlank()) return credential.token();
        return rotateCredential(firstText(credential.credentialId(), credential.id())).token();
      }
    }
    CredentialOptions resolved = options == null ? new CredentialOptions() : options;
    resolved.name = name;
    return issueCredential(resolved).token();
  }

  public BalanceSummary getBalance() {
    JsonNode raw = ownerRequest("GET", "/api/v1/balance", null, JsonNode.class);
    JsonNode balance = raw.has("balance") ? raw.path("balance") : raw;
    return MAPPER.convertValue(balance, BalanceSummary.class);
  }

  public DepositIntentResult registerDepositIntent(String txHash, String amountUsdc, String idempotencyKey) {
    return ownerRequestWithHeaders("POST", "/api/v1/balance/deposit/intent", Map.of("txHash", txHash, "amountUsdc", amountUsdc), DepositIntentResult.class, idempotency(idempotencyKey));
  }

  public DepositConfirmResult confirmDeposit(String intentId, String eventKey, int confirmations) {
    return ownerRequest("POST", "/api/v1/balance/deposit/intents/" + encodeRequired(intentId, "intentId") + "/confirm", Map.of("eventKey", eventKey, "confirmations", confirmations == 0 ? 1 : confirmations), DepositConfirmResult.class);
  }

  public void setSpendingLimit(String spendingLimitUsdc) {
    Map<String, Object> body = spendingLimitUsdc == null ? Map.of("allowUnlimited", true) : Map.of("spendingLimitUsdc", spendingLimitUsdc, "allowUnlimited", false);
    ownerRequest("PUT", "/api/v1/balance/spending-limit", body, JsonNode.class);
  }

  public VoucherRedeemResult redeemVoucher(String voucherCode, String idempotencyKey) {
    return ownerRequestWithHeaders("POST", "/api/v1/balance/vouchers/redeem", Map.of("voucherCode", requireNonBlank(voucherCode, "voucherCode")), VoucherRedeemResult.class, idempotency(idempotencyKey));
  }

  public UsageLogList getUsageLogs(int limit) {
    return ownerRequest("GET", withQuery("/api/v1/usage/logs", Map.of("limit", limitOrDefault(limit))), null, UsageLogList.class);
  }

  public FinanceAuditLogList getFinanceAuditLogs(int limit) {
    return ownerRequest("GET", withQuery("/api/v1/finance/audit-logs", Map.of("limit", limitOrDefault(limit))), null, FinanceAuditLogList.class);
  }

  public RiskOverview getRiskOverview() {
    return ownerRequest("GET", "/api/v1/finance/risk-overview", null, RiskOverview.class);
  }

  public IssueProviderSecretResult issueProviderSecret(CredentialOptions options) {
    return ownerRequest("POST", "/api/v1/secrets/provider/issue", credentialBody(options), IssueProviderSecretResult.class);
  }

  public List<ProviderSecret> listProviderSecrets() {
    JsonNode raw = ownerRequest("GET", "/api/v1/secrets/provider/list", null, JsonNode.class);
    return listOf(raw.path("secrets"), ProviderSecret.class);
  }

  public ProviderSecretDeleteResult deleteProviderSecret(String secretId) {
    return ownerRequest("DELETE", "/api/v1/secrets/provider/" + encodeRequired(secretId, "secretId"), null, ProviderSecretDeleteResult.class);
  }

  public RegisterProviderServiceResult registerProviderService(RegisterProviderServiceOptions options) {
    return ownerRequest("POST", "/api/v1/services", providerServiceBody(options), RegisterProviderServiceResult.class);
  }

  public List<ProviderServiceRecord> listProviderServices() {
    JsonNode raw = ownerRequest("GET", "/api/v1/services", null, JsonNode.class);
    return listOf(raw.path("services"), ProviderServiceRecord.class);
  }

  public ProviderRegistrationGuide getRegistrationGuide() {
    return ownerRequest("GET", "/api/v1/services/registration-guide", null, ProviderRegistrationGuide.class);
  }

  public ServiceManifestDraft parseCurlToServiceManifest(String curlCommand) {
    return ownerRequest("POST", "/api/v1/services/parse-curl", Map.of("curlCommand", requireNonBlank(curlCommand, "curlCommand")), ServiceManifestDraft.class);
  }

  public ProviderServiceUpdateResult updateProviderService(String serviceRecordId, Map<String, Object> patch) {
    return ownerRequest("PUT", "/api/v1/services/" + encodeRequired(serviceRecordId, "serviceRecordId"), patch == null ? Map.of() : patch, ProviderServiceUpdateResult.class);
  }

  public ProviderServiceDeleteResult deleteProviderService(String serviceRecordId) {
    return ownerRequest("DELETE", "/api/v1/services/" + encodeRequired(serviceRecordId, "serviceRecordId"), null, ProviderServiceDeleteResult.class);
  }

  public ProviderServicePingResult pingProviderService(String serviceRecordId) {
    return ownerRequest("POST", "/api/v1/services/" + encodeRequired(serviceRecordId, "serviceRecordId") + "/ping", null, ProviderServicePingResult.class);
  }

  public ProviderServiceHealthHistory getProviderServiceHealthHistory(String serviceRecordId, int limit) {
    return ownerRequest("GET", withQuery("/api/v1/services/" + encodeRequired(serviceRecordId, "serviceRecordId") + "/health/history", Map.of("limitPerTarget", limitOrDefault(limit))), null, ProviderServiceHealthHistory.class);
  }

  public ProviderEarningsSummary getProviderEarningsSummary() {
    return ownerRequest("GET", "/api/v1/providers/earnings/summary", null, ProviderEarningsSummary.class);
  }

  public ProviderWithdrawalCapability getProviderWithdrawalCapability() {
    return ownerRequest("GET", "/api/v1/providers/withdrawals/capability", null, ProviderWithdrawalCapability.class);
  }

  public ProviderWithdrawalIntentResult createProviderWithdrawalIntent(String amountUsdc, String idempotencyKey, String destinationAddress) {
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("amountUsdc", requireNonBlank(amountUsdc, "amountUsdc"));
    if (destinationAddress != null && !destinationAddress.isBlank()) body.put("destinationAddress", destinationAddress);
    return ownerRequestWithHeaders("POST", "/api/v1/providers/withdrawals/intent", body, ProviderWithdrawalIntentResult.class, idempotency(idempotencyKey));
  }

  public ProviderWithdrawalList listProviderWithdrawals(int limit) {
    return ownerRequest("GET", withQuery("/api/v1/providers/withdrawals", Map.of("limit", limitOrDefault(limit))), null, ProviderWithdrawalList.class);
  }

  public ProviderServiceRecord getProviderService(String serviceId) {
    return listProviderServices().stream()
        .filter(service -> Objects.equals(service.serviceId(), serviceId))
        .findFirst()
        .orElseThrow(() -> new SynapseClient.AuthenticationException("SERVICE_NOT_FOUND", "provider service not found: " + serviceId));
  }

  public ProviderServiceStatus getProviderServiceStatus(String serviceId) {
    ProviderServiceRecord service = getProviderService(serviceId);
    return new ProviderServiceStatus(service.serviceId(), service.status() == null ? "unknown" : service.status(), service.runtimeAvailable(), service.health());
  }

  private <T> T ownerRequest(String method, String path, Object body, Class<T> responseType) {
    return ownerRequestWithHeaders(method, path, body, responseType, Map.of());
  }

  private <T> T ownerRequestWithHeaders(String method, String path, Object body, Class<T> responseType, Map<String, String> extraHeaders) {
    Map<String, String> headers = new LinkedHashMap<>(extraHeaders);
    headers.put("Authorization", "Bearer " + getToken());
    return request(method, path, body, responseType, headers, null);
  }

  private <T> T get(String path, Class<T> responseType, Map<String, String> headers) {
    return request("GET", path, null, responseType, headers == null ? Map.of() : headers, null);
  }

  private <T> T request(String method, String path, Object body, Class<T> responseType, Map<String, String> headers, String requestId) {
    try {
      HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(gatewayUrl + path)).timeout(timeout).header("Content-Type", "application/json");
      if (headers == null) headers = Map.of();
      headers.forEach(builder::header);
      if (requestId != null && !requestId.isBlank()) builder.header("X-Request-Id", requestId);
      if ("GET".equals(method)) builder.GET();
      else builder.method(method, body == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(MAPPER.writeValueAsString(body)));
      HttpResponse<String> response = httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
      if (response.statusCode() < 200 || response.statusCode() >= 300) throw mapError(response.statusCode(), response.body());
      return MAPPER.readValue(response.body().isBlank() ? "{}" : response.body(), responseType);
    } catch (IOException ex) {
      throw new SynapseClient.SynapseException("HTTP_PARSE_FAILED", ex.getMessage(), ex);
    } catch (InterruptedException ex) {
      Thread.currentThread().interrupt();
      throw new SynapseClient.SynapseException("HTTP_INTERRUPTED", ex.getMessage(), ex);
    }
  }

  private RuntimeException mapError(int status, String body) {
    try {
      JsonNode detail = MAPPER.readTree(body).path("detail");
      String code = detail.path("code").asText("");
      String message = detail.path("message").asText(body);
      if (status == 401) return new SynapseClient.AuthenticationException(code, message);
      if (status == 402) return new SynapseClient.BudgetException(code, message);
      return new SynapseClient.InvokeException(code, message);
    } catch (IOException ex) {
      return new SynapseClient.InvokeException("HTTP_ERROR", body);
    }
  }

  private List<AgentCredential> credentialList(String path) {
    JsonNode raw = ownerRequest("GET", path, null, JsonNode.class);
    return listOf(raw.path("credentials"), AgentCredential.class);
  }

  private static Map<String, Object> credentialBody(CredentialOptions options) {
    Map<String, Object> body = new LinkedHashMap<>();
    if (options == null) return body;
    put(body, "name", options.name);
    put(body, "maxCalls", options.maxCalls);
    put(body, "creditLimit", options.creditLimit);
    put(body, "resetInterval", options.resetInterval);
    put(body, "rpm", options.rpm);
    put(body, "expiresInSec", options.expiresInSec);
    return body;
  }

  private static Map<String, Object> quotaBody(CredentialQuotaOptions options) {
    Map<String, Object> body = new LinkedHashMap<>();
    if (options == null) return body;
    put(body, "maxCalls", options.maxCalls);
    put(body, "rpm", options.rpm);
    put(body, "creditLimit", options.creditLimit);
    put(body, "resetInterval", options.resetInterval);
    put(body, "expiresAt", options.expiresAt);
    return body;
  }

  private Map<String, Object> providerServiceBody(RegisterProviderServiceOptions options) {
    String name = requireNonBlank(options.serviceName, "serviceName");
    String endpoint = requireNonBlank(options.endpointUrl, "endpointUrl");
    String serviceKind = firstText(options.serviceKind, "api");
    String priceModel = firstText(options.priceModel, "llm".equals(serviceKind) ? "token_metered" : "fixed");
    Map<String, Object> body = new LinkedHashMap<>();
    String serviceId = firstText(options.serviceId, defaultServiceId(name));
    body.put("serviceId", serviceId);
    body.put("agentToolName", serviceId);
    body.put("serviceName", name);
    body.put("serviceKind", serviceKind);
    body.put("priceModel", priceModel);
    body.put("role", "Provider");
    body.put("status", firstText(options.status, "active"));
    body.put("isActive", options.isActive == null || options.isActive);
    body.put("pricing", providerPricing(options, priceModel));
    body.put("summary", requireNonBlank(options.descriptionForModel, "descriptionForModel"));
    body.put("tags", options.tags == null ? List.of() : options.tags);
    body.put("auth", Map.of("type", "gateway_signed"));
    body.put("invoke", Map.of("method", firstText(options.endpointMethod, "POST"), "targets", List.of(Map.of("url", endpoint)), "timeoutMs", options.requestTimeoutMs == 0 ? 15000 : options.requestTimeoutMs));
    body.put("healthCheck", Map.of("path", firstText(options.healthPath, "/health"), "method", firstText(options.healthMethod, "GET"), "timeoutMs", options.healthTimeoutMs == 0 ? 3000 : options.healthTimeoutMs, "successCodes", List.of(200)));
    body.put("providerProfile", Map.of("displayName", firstText(options.providerDisplayName, name)));
    body.put("payoutAccount", Map.of("payoutAddress", firstText(options.payoutAddress, walletAddress), "chainId", options.chainId == null || options.chainId == 0 ? 31337 : options.chainId, "settlementCurrency", firstText(options.settlementCurrency, "USDC")));
    body.put("governance", Map.of("termsAccepted", true, "riskAcknowledged", true));
    return body;
  }

  private static Map<String, Object> providerPricing(RegisterProviderServiceOptions options, String priceModel) {
    if ("token_metered".equals(priceModel)) {
      return Map.of("priceModel", "token_metered", "inputPricePer1MTokensUsdc", requireNonBlank(options.inputPricePer1MTokensUsdc, "inputPricePer1MTokensUsdc"), "outputPricePer1MTokensUsdc", requireNonBlank(options.outputPricePer1MTokensUsdc, "outputPricePer1MTokensUsdc"), "currency", "USDC");
    }
    return Map.of("amount", requireNonBlank(options.basePriceUsdc, "basePriceUsdc"), "currency", "USDC");
  }

  private static <T> List<T> listOf(JsonNode node, Class<T> type) {
    List<T> items = new ArrayList<>();
    if (node != null && node.isArray()) node.forEach(item -> items.add(MAPPER.convertValue(item, type)));
    return items;
  }

  private static Map<String, String> idempotency(String value) {
    return Map.of("X-Idempotency-Key", value == null || value.isBlank() ? "java-" + System.currentTimeMillis() : value);
  }

  private static String withQuery(String path, Map<String, Object> params) {
    StringBuilder query = new StringBuilder();
    params.forEach((key, value) -> {
      if (query.length() > 0) query.append('&');
      query.append(encode(key)).append('=').append(encode(String.valueOf(value)));
    });
    return query.isEmpty() ? path : path + "?" + query;
  }

  private static String encodeRequired(String value, String name) {
    return encode(requireNonBlank(value, name));
  }

  private static String encode(String value) {
    return URLEncoder.encode(value, StandardCharsets.UTF_8);
  }

  private static int limitOrDefault(int limit) {
    return limit <= 0 ? 100 : limit;
  }

  private static void put(Map<String, Object> body, String key, Object value) {
    if (value != null && !String.valueOf(value).isBlank() && !"0".equals(String.valueOf(value))) body.put(key, value);
  }

  private static String requireNonBlank(String value, String name) {
    if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " is required");
    return value.trim();
  }

  private static String firstText(String... values) {
    for (String value : values) if (value != null && !value.isBlank()) return value.trim();
    return "";
  }

  private static String defaultServiceId(String name) {
    String value = name.trim().toLowerCase().replaceAll("[^a-z0-9_-]+", "_").replaceAll("_+", "_").replaceAll("^_+|_+$", "");
    return value.isBlank() ? "service_" + System.currentTimeMillis() : value;
  }

  @FunctionalInterface
  public interface Signer {
    String sign(String message);
  }

  public static final class Options {
    public String walletAddress;
    public Signer signer;
    public String environment;
    public String gatewayUrl;
    public Duration timeout;
    public HttpClient httpClient;
  }

  public static final class CredentialOptions {
    public String name;
    public Integer maxCalls;
    public String creditLimit;
    public String resetInterval;
    public Integer rpm;
    public Integer expiresInSec;
  }

  public static final class CredentialQuotaOptions {
    public Integer maxCalls;
    public Integer rpm;
    public String creditLimit;
    public String resetInterval;
    public String expiresAt;
  }

  public static final class RegisterProviderServiceOptions {
    public String serviceName;
    public String endpointUrl;
    public String basePriceUsdc;
    public String descriptionForModel;
    public String serviceKind;
    public String priceModel;
    public String inputPricePer1MTokensUsdc;
    public String outputPricePer1MTokensUsdc;
    public String serviceId;
    public String providerDisplayName;
    public String payoutAddress;
    public Integer chainId;
    public String settlementCurrency;
    public List<String> tags;
    public String status;
    public Boolean isActive;
    public String endpointMethod;
    public String healthPath;
    public String healthMethod;
    public int healthTimeoutMs;
    public int requestTimeoutMs;
  }

  public record ChallengeResponse(boolean success, String challenge, String domain) {}
  public record TokenResponse(boolean success, @JsonProperty("access_token") String accessToken, @JsonProperty("expires_in") long expiresIn) {}
  public record AuthLogoutResult(String status, Boolean success) {}
  public record OwnerProfile(String ownerAddress, String walletAddress, JsonNode profile) {}
  public record AgentCredential(String id, @JsonProperty("credential_id") String credentialId, String token, String name, String status) {}
  public record IssueCredentialResult(AgentCredential credential, String token) {}
  public record CredentialStatusResult(String status, String credentialId, Boolean valid, String credentialStatus) {}
  public record CredentialRevokeResult(String status, String credentialId, AgentCredential credential) {}
  public record CredentialRotateResult(String status, String credentialId, String token, AgentCredential credential) {}
  public record CredentialDeleteResult(String status, String credentialId) {}
  public record CredentialQuotaUpdateResult(String status, String credentialId, AgentCredential credential) {}
  public record CredentialAuditLogList(List<JsonNode> logs) {}
  public record BalanceSummary(JsonNode ownerBalance, JsonNode consumerAvailableBalance, JsonNode providerReceivable, JsonNode platformFeeAccrued) {}
  public record DepositIntentResult(String status, @JsonProperty("tx_hash") String txHash, JsonNode intent) {}
  public record DepositConfirmResult(String status, JsonNode intent) {}
  public record VoucherRedeemResult(String status, String voucherCode) {}
  public record UsageLogList(List<JsonNode> logs) {}
  public record FinanceAuditLogList(List<JsonNode> logs) {}
  public record RiskOverview(JsonNode risk) {}
  public record ProviderSecret(String id, String name, String ownerAddress, String secretKey, String maskedKey, String status) {}
  public record IssueProviderSecretResult(String status, ProviderSecret secret) {}
  public record ProviderSecretDeleteResult(String status, String secretId) {}
  @JsonIgnoreProperties(ignoreUnknown = true)
  public record ProviderServiceRecord(String serviceId, String id, String serviceName, String status, Boolean runtimeAvailable, JsonNode health) {}
  public record RegisterProviderServiceResult(String status, String serviceId, ProviderServiceRecord service) {}
  public record ProviderServiceStatus(String serviceId, String lifecycleStatus, Boolean runtimeAvailable, JsonNode health) {}
  public record ProviderRegistrationGuide(List<JsonNode> steps, JsonNode requirements) {}
  public record ServiceManifestDraft(JsonNode data, JsonNode manifest) {}
  public record ProviderServiceUpdateResult(String status, ProviderServiceRecord service) {}
  public record ProviderServiceDeleteResult(String status, String serviceId) {}
  public record ProviderServicePingResult(String status, JsonNode health) {}
  public record ProviderServiceHealthHistory(List<JsonNode> history) {}
  public record ProviderEarningsSummary(JsonNode total) {}
  public record ProviderWithdrawalCapability(Boolean available) {}
  public record ProviderWithdrawalIntentResult(String status, String intentId, JsonNode amountUsdc, JsonNode intent) {}
  public record ProviderWithdrawalList(List<JsonNode> withdrawals) {}
}
