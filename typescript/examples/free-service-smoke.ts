import { awaitReceipt, client, emit, fixedTarget } from "./_shared";

async function main(): Promise<void> {
  const synapse = client();
  const target = await fixedTarget(synapse);
  const result = await synapse.invoke(target.serviceId, target.payload, {
    costUsdc: target.costUsdc,
    idempotencyKey: `typescript-free-smoke-${Date.now()}`,
  });
  const receipt = await awaitReceipt(synapse, result.invocationId);
  emit({
    language: "typescript",
    scenario: "free-service-smoke",
    serviceId: target.serviceId,
    invocationId: result.invocationId,
    status: result.status,
    chargedUsdc: String(receipt.chargedUsdc),
    receiptStatus: receipt.status,
  });
}

void main();
