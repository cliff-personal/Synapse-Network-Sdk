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
10. credential revoke / rotate / delete
11. credential quota update
12. credential audit logs
13. check credential status alias
14. ensure credential
15. discovery/search
16. invoke
17. invoke with rediscovery on `PRICE_MISMATCH`
18. invocation receipt
19. gateway health check
20. empty discovery diagnostics
21. owner profile
22. usage logs
23. voucher redeem
24. finance audit logs
25. finance risk overview
26. spending limit through `AgentWallet`

Deprecated:

1. `create_quote()`
2. `create_invocation()`
3. `invoke_service()`
4. `quote()`

## Python Provider

Supported:

1. issue provider secret
2. list provider secret
3. delete provider secret
4. registration guide
5. parse curl to service manifest
6. register provider service
7. list provider service
8. get provider service
9. provider service status
10. update provider service
11. delete provider service
12. ping provider service
13. provider service health history
14. provider earnings summary
15. provider withdrawal capability
16. create provider withdrawal intent
17. list provider withdrawals

## TypeScript Consumer

Supported:

1. auth challenge / verify
2. JWT cache
3. balance
4. deposit intent / confirm
5. issue credential
6. list credential
7. credential status
8. credential revoke / rotate / delete
9. credential quota update
10. credential audit logs
11. discovery/search
12. invoke
13. invoke with rediscovery on `PRICE_MISMATCH`
14. invocation receipt
15. gateway health check
16. empty discovery diagnostics
17. owner profile
18. usage logs
19. voucher redeem
20. finance audit logs
21. finance risk overview
22. spending limit through issued credential settings

Discovery/search sends the current gateway request body: `query`, `tags`, `page`, `pageSize`, and `sort`. `limit/offset` remain SDK convenience inputs and are converted to `page/pageSize`.

## TypeScript Provider

Supported:

1. issue provider secret
2. list provider secret
3. delete provider secret
4. registration guide
5. parse curl to service manifest
6. register provider service
7. list provider service
8. get provider service
9. provider service status
10. update provider service
11. delete provider service
12. ping provider service
13. provider service health history
14. provider earnings summary
15. provider withdrawal capability
16. create provider withdrawal intent
17. list provider withdrawals

## Gateway Capabilities Not Yet Wrapped

The SDK does not currently wrap the full gateway management surface. Known uncovered areas:

1. refunds
2. notifications
3. community / support APIs
4. events
5. on-chain transaction signing helpers
6. provider withdrawal completion helper

## Product Boundary

The SDK current promise is consumer/provider canonical main flow coverage, not full gateway administration coverage. New management APIs should be added deliberately with tests and docs, rather than implied by broad README language.

Finance and withdrawal methods are high-impact wrappers. They construct gateway requests but do not sign on-chain transactions, automatically move funds, or make policy decisions for an agent.
