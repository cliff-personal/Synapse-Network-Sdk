package ai.synapsenetwork.sdk.examples;

import ai.synapsenetwork.sdk.SynapseClient;
import java.util.Map;

public final class FreeServiceSmoke {
  private FreeServiceSmoke() {}

  public static void main(String[] args) {
    SynapseClient client = ExampleSupport.client();
    var services = client.search("free", new SynapseClient.SearchOptions());
    var service =
        services.stream()
            .filter(ExampleSupport::isFreeFixedApiService)
            .findFirst()
            .orElseThrow(
                () ->
                    new IllegalStateException(
                        "no free fixed-price API service found; set SYNAPSE_E2E_FIXED_SERVICE_ID and "
                            + "SYNAPSE_E2E_FIXED_COST_USDC for paid smoke tests"));
    SynapseClient.InvokeOptions options = new SynapseClient.InvokeOptions();
    options.costUsdc = service.pricing().path("amount").asText("0");
    options.idempotencyKey = "java-free-smoke-" + System.currentTimeMillis();
    var result = client.invoke(service.serviceId(), Map.of("prompt", "hello"), options);
    var receipt = ExampleSupport.awaitReceipt(client, result.invocationId());
    ExampleSupport.emit(
        "free-service-smoke",
        result.status(),
        result.invocationId(),
        receipt.chargedUsdc(),
        receipt.status(),
        service.serviceId());
  }
}
