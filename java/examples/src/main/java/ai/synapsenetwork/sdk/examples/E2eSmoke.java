package ai.synapsenetwork.sdk.examples;

import ai.synapsenetwork.sdk.SynapseClient;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

public final class E2eSmoke {
  private E2eSmoke() {}

  public static void main(String[] args) {
    SynapseClient client = ExampleSupport.client();

    localNegative(client);
    client.health();
    ExampleSupport.emit("health", "ok", "", "", "", "");

    if (!ExampleSupport.envBool("SYNAPSE_E2E_SKIP_AUTH_NEGATIVE")) {
      authNegative();
    }

    ExampleSupport.FixedTarget fixed = ExampleSupport.fixedTarget(client);
    SynapseClient.InvokeOptions fixedOptions = new SynapseClient.InvokeOptions();
    fixedOptions.costUsdc = fixed.costUsdc();
    fixedOptions.idempotencyKey = ExampleSupport.idempotencyKey("fixed");
    SynapseClient.InvocationResult fixedResult = client.invoke(fixed.serviceId(), fixed.payload(), fixedOptions);
    SynapseClient.InvocationResult fixedReceipt = ExampleSupport.awaitReceipt(client, fixedResult.invocationId());
    ExampleSupport.emit(
        "fixed-price",
        fixedResult.status(),
        fixedResult.invocationId(),
        fixedReceipt.chargedUsdc(),
        fixedReceipt.status(),
        fixed.serviceId());

    if (ExampleSupport.envBool("SYNAPSE_E2E_FREE_ONLY")) {
      return;
    }

    String llmServiceId = ExampleSupport.envDefault("SYNAPSE_E2E_LLM_SERVICE_ID", "svc_deepseek_chat");
    String maxCost = ExampleSupport.envDefault("SYNAPSE_E2E_LLM_MAX_COST_USDC", "0.010000");
    SynapseClient.LlmInvokeOptions llmOptions = new SynapseClient.LlmInvokeOptions();
    llmOptions.maxCostUsdc = maxCost;
    llmOptions.idempotencyKey = ExampleSupport.idempotencyKey("llm");
    SynapseClient.InvocationResult llmResult =
        client.invokeLlm(
            llmServiceId,
            ExampleSupport.payload(
                "SYNAPSE_E2E_LLM_PAYLOAD_JSON",
                Map.of("messages", List.of(Map.of("role", "user", "content", "hello")))),
            llmOptions);
    SynapseClient.InvocationResult llmReceipt = ExampleSupport.awaitReceipt(client, llmResult.invocationId());
    String charged = ExampleSupport.firstNonBlank(llmReceipt.chargedUsdc(), llmResult.chargedUsdc());
    if (charged.isBlank()) {
      ExampleSupport.fail("llm invoke did not report chargedUsdc");
    }
    if (new BigDecimal(charged).compareTo(new BigDecimal(maxCost)) > 0) {
      ExampleSupport.fail("llm chargedUsdc " + charged + " exceeds maxCostUsdc " + maxCost);
    }
    ExampleSupport.emit("llm", llmResult.status(), llmResult.invocationId(), charged, llmReceipt.status(), llmServiceId);
  }

  private static void localNegative(SynapseClient client) {
    SynapseClient.InvokeOptions invokeOptions = new SynapseClient.InvokeOptions();
    ExampleSupport.expectFailure(
        () -> client.invoke("svc_local", Map.of(), invokeOptions), IllegalArgumentException.class);
    ExampleSupport.expectFailure(
        () -> client.invokeLlm("svc_llm", Map.of("stream", true), new SynapseClient.LlmInvokeOptions()),
        SynapseClient.InvokeException.class);
    ExampleSupport.emit("local-negative", "ok", "", "", "", "");
  }

  private static void authNegative() {
    SynapseClient invalidClient = ExampleSupport.client("agt_invalid");
    SynapseClient.InvokeOptions options = new SynapseClient.InvokeOptions();
    options.costUsdc = "0";
    ExampleSupport.expectFailure(
        () -> invalidClient.invoke("svc_invalid_auth_probe", Map.of(), options),
        SynapseClient.AuthenticationException.class);
    ExampleSupport.emit("auth-negative", "ok", "", "", "", "");
  }
}
