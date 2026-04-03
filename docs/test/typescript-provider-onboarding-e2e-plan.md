# TypeScript SDK — Provider Onboarding E2E 自动化测试方案

> 目标：验证 TypeScript SDK 能从 **新钱包 Provider 冷启动** 开始，完整走通  
> `创建钱包 -> 登录 -> 创建 provider credentials -> 注册服务 -> 读取注册状态`

---

## 1. 测试范围

| # | 阶段 | 验证点 |
|---|---|---|
| 1 | 创建钱包 | `Wallet.createRandom()` 生成全新 Provider EOA |
| 2 | 登录 | `SynapseAuth.fromWallet()` 完成 challenge/sign/verify |
| 3 | JWT 缓存 | `getToken()` 返回稳定 token |
| 4 | 创建 provider secret | `issueProviderSecret()` 成功返回 `secret.id` 与 `secretKey` |
| 5 | 查询 provider secret | `listProviderSecrets()` 能找到刚签发的 secret |
| 6 | 注册服务 | `registerProviderService()` 成功返回 `serviceId` |
| 7 | 查询 owner service list | `listProviderServices()` 包含刚注册服务 |
| 8 | 查询服务状态 | `getProviderServiceStatus()` 返回 lifecycle + runtime 状态 |

---

## 2. 依赖环境

| 组件 | 地址 | 说明 |
|---|---|---|
| Gateway | `http://127.0.0.1:8000` | Synapse gateway |
| Mock Provider | `http://127.0.0.1:9498` | 测试内启动的 HTTP server |

这个 Provider E2E 不依赖链上充值，因此执行速度比 consumer 链更快。

---

## 3. 关键角色

| 角色 | 来源 | 作用 |
|---|---|---|
| Fresh Provider | `ethers.Wallet.createRandom()` | 本次测试主角 |
| Mock Provider Server | test fixture | 对 `/health` 与 invoke 返回 200 |

---

## 4. 测试文件

1. `typescript/tests/e2e/provider.test.ts`

---

## 5. 运行命令

```bash
cd /home/alex/Documents/cliff/Synapse-Network-Sdk/typescript
npm install
npm run lint
npm run test:provider
```

---

## 6. 验收标准

1. TypeScript 编译通过
2. provider onboarding e2e 通过
3. fresh wallet 能拿到 JWT
4. provider secret 创建成功
5. service register 成功返回 `serviceId`
6. `getProviderServiceStatus()` 能查到刚注册服务的状态
