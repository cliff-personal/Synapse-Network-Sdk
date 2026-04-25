# Synapse SDK Capability Inventory

This inventory describes what the SDKs currently wrap for the live gateway contract. It is intentionally narrower than the full gateway API surface.

## Runtime Contract

Consumer runtime is:

1. owner auth / credential issue
2. agent discovery/search
3. `POST /api/v1/agent/invoke`
4. `GET /api/v1/agent/invocations/{id}`

The old quote-first flow is not a current SDK main path. Python keeps deprecated compatibility methods that raise a clear error instead of calling removed endpoints.

## Python Consumer

Supported:

1. auth challenge / verify
2. JWT cache
3. balance
4. deposit intent / confirm
5. issue credential
6. list credential
7. list active credentials
8. credential status
9. credential update
10. ensure credential
11. discovery/search
12. invoke
13. invocation receipt
14. spending limit through `AgentWallet`

Deprecated:

1. `create_quote()`
2. `create_invocation()`
3. `invoke_service()`
4. `quote()`

## Python Provider

Supported:

1. issue provider secret
2. list provider secret
3. register provider service
4. list provider service
5. get provider service
6. provider service status

## TypeScript Consumer

Supported:

1. auth challenge / verify
2. JWT cache
3. balance
4. deposit intent / confirm
5. issue credential
6. list credential
7. discovery/search
8. invoke
9. invocation receipt
10. spending limit through issued credential settings

Discovery/search sends the current gateway request body: `query`, `tags`, `page`, `pageSize`, and `sort`. `limit/offset` remain SDK convenience inputs and are converted to `page/pageSize`.

## TypeScript Provider

Supported:

1. issue provider secret
2. list provider secret
3. register provider service
4. list provider service
5. get provider service
6. provider service status

## Gateway Capabilities Not Yet Wrapped

The SDK does not currently wrap the full gateway management surface. Known uncovered areas:

1. owner profile
2. credential revoke / delete / quota / audit logs
3. provider secret revoke
4. service update / delete / ping / registration guide / health history / admin lifecycle
5. voucher / refunds / withdrawals / usage logs / finance risk
6. notifications / community / events

## Product Boundary

The SDK current promise is consumer/provider canonical main flow coverage, not full gateway administration coverage. New management APIs should be added deliberately with tests and docs, rather than implied by broad README language.
