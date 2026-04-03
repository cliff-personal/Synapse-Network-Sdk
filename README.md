# Synapse Network SDK 🔌

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" />
  <img src="https://img.shields.io/badge/TypeScript-Coming%20Soon-yellow.svg" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" />
</p>

Official Client SDK for [Synapse Network](../Synapse-Network) – the "Stripe for AI Agents". 

This SDK allows developers and Autonomous AI Agents (via MCP) to seamlessly discover, invoke, and pay for external APIs and services with zero friction. It handles programmatic wallet generation, zero-gas microtransactions over state channels, and verifiable audit trails out of the box.

## 🌟 Why Synapse SDK?

- **Built for AI Agents**: Native support for **Model Context Protocol (MCP)** tools. AI agents can natively discover tools and spend budgets you allocate without credit cards.
- **Zero-Gas Micropayments**: Service interactions lock micro-amounts (down to $0.01) instantly. No waiting for blockchain confirmations, no massive upfront fees.
- **Unified Identity**: Every instantiation automatically creates or loads an `AgentWallet`, unifying identity for billing and API invocation.

---

## 🚀 Quickstart (Python)

### 1. Installation

```bash
pip install synapse-client
```

### 2. Initialization & Budget Allocation

Create a new Agent identity and allocate a budget (in USDC):

```python
from synapse_client import AgentWallet

# Connect to the Gateway & allocate $5.00 for the agent session
wallet = AgentWallet.connect(budget=5.00)

print(f"Agent Wallet Address: {wallet.address}")
print(f"Available Balance: {wallet.balance} USDC")
```

### 3. Agent Tool Invocation (MCP)

Pass the Synapse tools directly to your favorite Agent framework (e.g., `smolagents`, `LangChain`):

```python
from smolagents import CodeAgent

# Convert paid APIs into MCP tools the agent can use
tools = [
    wallet.mcp_tool("market_data_api"),
    wallet.mcp_tool("image_generation_service")
]

agent = CodeAgent(tools=tools)

# The agent executes the request, auto-deducting $0.05 from the wallet per call
agent.run("Get me the precise sentiment data for AAPL today.")
```

## 📚 Ecosystem & Documentation

- `python/`: Python SDK implementation and examples.
- `typescript/`: TypeScript/Node.js SDK (In Progress).
- `docs/`: Detailed internal guides, architecture specs, and cold-start flows.

For Server-Side Service Providers (selling APIs), please see the [Synapse-Network-Provider](../Synapse-Network-Provider) repository.

## 🛡️ License
MIT License. See `LICENSE` for more information.
