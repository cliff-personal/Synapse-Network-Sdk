# Java/JVM SDK Integration Guide

The Java SDK is a Wave 1 consumer runtime SDK targeting Java 17 and newer. Kotlin and other JVM languages can call the Java SDK directly.

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

## Verification

```bash
bash scripts/ci/java_checks.sh
mvn -q -f java/pom.xml test package
mvn -q -f java/examples/pom.xml compile
SYNAPSE_AGENT_KEY=agt_xxx mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.FreeServiceSmoke
SYNAPSE_AGENT_KEY=agt_xxx mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.LlmSmoke
SYNAPSE_AGENT_KEY=agt_xxx mvn -q -f java/examples/pom.xml exec:java -Dexec.mainClass=ai.synapsenetwork.sdk.examples.E2eSmoke
```
