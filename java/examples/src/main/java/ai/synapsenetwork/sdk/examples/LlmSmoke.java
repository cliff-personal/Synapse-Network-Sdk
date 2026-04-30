package ai.synapsenetwork.sdk.examples;

import ai.synapsenetwork.sdk.SynapseClient;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

public final class LlmSmoke {
  private LlmSmoke() {}

  public static void main(String[] args) {
    SynapseClient client = ExampleSupport.client();
    String serviceId = ExampleSupport.envDefault("SYNAPSE_E2E_LLM_SERVICE_ID", "svc_deepseek_chat");
    String maxCost = ExampleSupport.envDefault("SYNAPSE_E2E_LLM_MAX_COST_USDC", "0.010000");
    SynapseClient.LlmInvokeOptions options = new SynapseClient.LlmInvokeOptions();
    options.maxCostUsdc = maxCost;
    options.idempotencyKey = "java-llm-smoke-" + System.currentTimeMillis();
    var result =
        client.invokeLlm(
            serviceId,
            ExampleSupport.payload(
                "SYNAPSE_E2E_LLM_PAYLOAD_JSON",
                Map.of("messages", List.of(Map.of("role", "user", "content", "hello")))),
            options);
    var receipt = ExampleSupport.awaitReceipt(client, result.invocationId());
    String charged = ExampleSupport.firstNonBlank(receipt.chargedUsdc(), result.chargedUsdc());
    if (charged.isBlank()) {
      ExampleSupport.fail("llm invoke did not report chargedUsdc");
    }
    if (new BigDecimal(charged).compareTo(new BigDecimal(maxCost)) > 0) {
      ExampleSupport.fail("llm chargedUsdc " + charged + " exceeds maxCostUsdc " + maxCost);
    }
    ExampleSupport.emit("llm-smoke", result.status(), result.invocationId(), charged, receipt.status(), serviceId);
  }
}
