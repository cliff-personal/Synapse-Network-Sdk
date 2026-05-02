package ai.synapsenetwork.sdk.examples;

import ai.synapsenetwork.sdk.SynapseClient;

public final class FreeServiceSmoke {
  private FreeServiceSmoke() {}

  public static void main(String[] args) {
    SynapseClient client = ExampleSupport.client();
    var target = ExampleSupport.fixedTarget(client);
    SynapseClient.InvokeOptions options = new SynapseClient.InvokeOptions();
    options.costUsdc = target.costUsdc();
    options.idempotencyKey = "java-free-smoke-" + System.currentTimeMillis();
    var result = client.invoke(target.serviceId(), target.payload(), options);
    var receipt = ExampleSupport.awaitReceipt(client, result.invocationId());
    ExampleSupport.emit(
        "free-service-smoke",
        result.status(),
        result.invocationId(),
        receipt.chargedUsdc(),
        receipt.status(),
        target.serviceId());
  }
}
