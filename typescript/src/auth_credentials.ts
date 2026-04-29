import { AgentCredential, IssueCredentialOptions, IssueCredentialResult } from "./types";
import { AuthenticationError } from "./errors";

type FetchJson = <T>(
  url: string,
  init?: { method?: string; body?: string; headers?: Record<string, string> }
) => Promise<T>;

export interface AuthCredentialContext {
  gatewayUrl: string;
  getToken: () => Promise<string>;
  fetchJson: FetchJson;
}

function credentialOptionsBody(opts: IssueCredentialOptions): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (opts.name) body["name"] = opts.name;
  if (opts.maxCalls != null) body["maxCalls"] = opts.maxCalls;
  if (opts.creditLimit != null) body["creditLimit"] = opts.creditLimit;
  if (opts.resetInterval != null) body["resetInterval"] = opts.resetInterval;
  if (opts.rpm != null) body["rpm"] = opts.rpm;
  if (opts.expiresInSec != null) body["expiresInSec"] = opts.expiresInSec;
  return body;
}

export async function issueCredential(
  ctx: AuthCredentialContext,
  opts: IssueCredentialOptions = {}
): Promise<IssueCredentialResult> {
  const token = await ctx.getToken();
  const resp = await ctx.fetchJson<Record<string, unknown>>(`${ctx.gatewayUrl}/api/v1/credentials/agent/issue`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(credentialOptionsBody(opts)),
  });

  const credentialPayload = (resp["credential"] as Record<string, unknown>) ?? {};
  const credToken = firstString([resp["token"], credentialPayload["token"], resp["credential_token"]]);
  const credId = firstString([
    resp["credential_id"],
    resp["id"],
    credentialPayload["id"],
    credentialPayload["credential_id"],
  ]);

  if (!credToken) throw new AuthenticationError(`Credential token missing: ${JSON.stringify(resp)}`);
  if (!credId) throw new AuthenticationError(`Credential ID missing: ${JSON.stringify(resp)}`);

  const credential: AgentCredential = {
    id: credId,
    credential_id: credId,
    token: credToken,
    name: opts.name,
    status: "active",
    ...credentialPayload,
  };

  return { credential, token: credToken };
}

function firstString(values: unknown[]): string | null {
  const found = values.find((value) => typeof value === "string" && value.length > 0);
  return (found as string | undefined) ?? null;
}
