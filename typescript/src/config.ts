import type { SynapseEnvironment } from "./types";

export const DEFAULT_ENVIRONMENT: SynapseEnvironment = "staging";

export const GATEWAY_URLS: Record<SynapseEnvironment, string> = {
  staging: "https://api-staging.synapse-network.ai",
  prod: "https://api.synapse-network.ai",
};

export function resolveGatewayUrl(
  opts: {
    environment?: SynapseEnvironment;
    gatewayUrl?: string;
  } = {}
): string {
  const explicitUrl = opts.gatewayUrl?.trim();
  if (explicitUrl) return explicitUrl.replace(/\/+$/, "");

  const selected = opts.environment ?? DEFAULT_ENVIRONMENT;
  const resolved = GATEWAY_URLS[selected];
  if (!resolved) {
    const valid = Object.keys(GATEWAY_URLS).sort().join(", ");
    throw new Error(`unsupported Synapse environment '${String(selected)}'. Expected one of: ${valid}`);
  }
  return resolved.replace(/\/+$/, "");
}
