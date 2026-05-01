# Java/JVM SDK Integration Guide

The Java SDK targets Java 17 and newer. Kotlin and other JVM languages can call it directly. It supports the full public Synapse SDK surface: `SynapseClient` agent runtime, `SynapseAuth` owner wallet auth, credential and finance helpers, and `SynapseProvider` publishing/withdrawal helpers.

## Install

The preview Maven artifact is defined in `java/pom.xml`:

```xml
<dependency>
  <groupId>ai.synapsenetwork</groupId>
  <artifactId>synapse-network-sdk</artifactId>
  <version>0.1.0-SNAPSHOT</version>
</dependency>
```

## Fixed-Price API Invoke

```java
import ai.synapsenetwork.sdk.SynapseClient;
import java.util.Map;

SynapseClient client = new SynapseClient(
    SynapseClient.options(System.getenv("SYNAPSE_AGENT_KEY")).environment("staging"));

var services = client.search("free", new SynapseClient.SearchOptions());
var service = services.get(0);

SynapseClient.InvokeOptions options = new SynapseClient.InvokeOptions();
options.costUsdc = service.pricing().path("amount").asText("0");

var result = client.invoke(service.serviceId(), Map.of("prompt", "hello"), options);
System.out.println(result.invocationId() + " " + result.status() + " " + result.chargedUsdc());
```

## Token-Metered LLM Invoke

```java
SynapseClient.LlmInvokeOptions options = new SynapseClient.LlmInvokeOptions();
options.maxCostUsdc = "0.010000";

var result = client.invokeLlm(
    "svc_deepseek_chat",
    Map.of("messages", java.util.List.of(Map.of("role", "user", "content", "hello"))),
    options);
```

Do not pass fixed-price `costUsdc` to LLM services. Use `maxCostUsdc` as an optional cap or omit it to let the Gateway compute the hold.

## Owner Auth and Provider Control

Use owner auth only in backend or operator tooling. Agent runtime code should keep using `SynapseClient` with `SYNAPSE_AGENT_KEY`.

```java
SynapseAuth.Options authOptions = new SynapseAuth.Options();
authOptions.environment = "staging";

SynapseAuth auth = SynapseAuth.fromPrivateKey(
    System.getenv("SYNAPSE_OWNER_PRIVATE_KEY"),
    authOptions);

String token = auth.getToken();

SynapseAuth.CredentialOptions credentialOptions = new SynapseAuth.CredentialOptions();
credentialOptions.name = "agent-runtime";
credentialOptions.maxCalls = 100;
credentialOptions.rpm = 60;
credentialOptions.expiresInSec = 3600;

var credential = auth.issueCredential(credentialOptions);
var balance = auth.getBalance();
var guide = auth.provider().getRegistrationGuide();

System.out.println(token + " " + credential.token() + " " + guide.steps().size());
```

Public owner/provider methods return named Java records/classes. Do not expose `JsonNode` or `Map` as a top-level public result; reserve them for request payloads, schemas, patches, and dynamic nested fields.

## Verification

```bash
bash scripts/ci/java_checks.sh
mvn -q -f java/pom.xml test package
mvn -q -f java/examples/pom.xml compile
SYNAPSE_AGENT_KEY=agt_xxx mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.FreeServiceSmoke
SYNAPSE_AGENT_KEY=agt_xxx mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.LlmSmoke
SYNAPSE_AGENT_KEY=agt_xxx mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.E2eSmoke
SYNAPSE_OWNER_PRIVATE_KEY=0x... bash scripts/e2e/sdk_parity_e2e.sh --languages java --env staging
```
