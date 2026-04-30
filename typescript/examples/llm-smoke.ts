import {
  awaitReceipt,
  client,
  decimalLessThanOrEqual,
  DEFAULT_LLM_PAYLOAD,
  emit,
  envDefault,
  jsonPayload,
} from "./_shared";

async function main(): Promise<void> {
  const synapse = client();
  const serviceId = envDefault("SYNAPSE_E2E_LLM_SERVICE_ID", "svc_deepseek_chat");
  const maxCostUsdc = envDefault("SYNAPSE_E2E_LLM_MAX_COST_USDC", "0.010000");
  const result = await synapse.invokeLlm(serviceId, jsonPayload("SYNAPSE_E2E_LLM_PAYLOAD_JSON", DEFAULT_LLM_PAYLOAD), {
    maxCostUsdc,
    idempotencyKey: `typescript-llm-smoke-${Date.now()}`,
  });
  const receipt = await awaitReceipt(synapse, result.invocationId);
  const chargedUsdc = String(receipt.chargedUsdc || result.chargedUsdc);
  if (!decimalLessThanOrEqual(chargedUsdc, maxCostUsdc)) {
    throw new Error(`chargedUsdc ${chargedUsdc} exceeds maxCostUsdc ${maxCostUsdc}`);
  }
  emit({
    language: "typescript",
    scenario: "llm-smoke",
    serviceId,
    invocationId: result.invocationId,
    status: result.status,
    chargedUsdc,
    receiptStatus: receipt.status,
  });
}

void main();
