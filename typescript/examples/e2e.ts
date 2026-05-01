import {
  authNegative,
  awaitReceipt,
  client,
  decimalLessThanOrEqual,
  DEFAULT_LLM_PAYLOAD,
  emit,
  envBool,
  envDefault,
  fixedTarget,
  idempotencyKey,
  jsonPayload,
  localNegative,
} from "./_shared";

async function main(): Promise<void> {
  const synapse = client();
  await localNegative(synapse);
  await synapse.checkGatewayHealth();
  emit({ language: "typescript", scenario: "health", status: "ok" });

  if (!envBool("SYNAPSE_E2E_SKIP_AUTH_NEGATIVE")) {
    await authNegative();
  }

  const target = await fixedTarget(synapse);
  const fixedResult = await synapse.invoke(target.serviceId, target.payload, {
    costUsdc: target.costUsdc,
    idempotencyKey: idempotencyKey("typescript", "fixed"),
  });
  const fixedReceipt = await awaitReceipt(synapse, fixedResult.invocationId);
  emit({
    language: "typescript",
    scenario: "fixed-price",
    serviceId: target.serviceId,
    invocationId: fixedResult.invocationId,
    status: fixedResult.status,
    chargedUsdc: String(fixedReceipt.chargedUsdc),
    receiptStatus: fixedReceipt.status,
  });

  if (envBool("SYNAPSE_E2E_FREE_ONLY")) return;

  const llmServiceId = envDefault("SYNAPSE_E2E_LLM_SERVICE_ID", "svc_deepseek_chat");
  const maxCostUsdc = envDefault("SYNAPSE_E2E_LLM_MAX_COST_USDC", "0.010000");
  const llmResult = await synapse.invokeLlm(
    llmServiceId,
    jsonPayload("SYNAPSE_E2E_LLM_PAYLOAD_JSON", DEFAULT_LLM_PAYLOAD),
    {
      maxCostUsdc,
      idempotencyKey: idempotencyKey("typescript", "llm"),
    }
  );
  const llmReceipt = await awaitReceipt(synapse, llmResult.invocationId);
  const chargedUsdc = String(llmReceipt.chargedUsdc || llmResult.chargedUsdc);
  if (!decimalLessThanOrEqual(chargedUsdc, maxCostUsdc)) {
    throw new Error(`chargedUsdc ${chargedUsdc} exceeds maxCostUsdc ${maxCostUsdc}`);
  }
  emit({
    language: "typescript",
    scenario: "llm",
    serviceId: llmServiceId,
    invocationId: llmResult.invocationId,
    status: llmResult.status,
    chargedUsdc,
    receiptStatus: llmReceipt.status,
  });
}

void main();
