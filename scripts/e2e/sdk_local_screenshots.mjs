#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import crypto from "node:crypto";

const sdkRoot = path.resolve(process.env.SDK_ROOT || process.cwd());
const productRoot = path.resolve(process.env.PRODUCT_ROOT || "/Users/cliff/workspace/agent/Synapse-Network");
const requireFromProduct = createRequire(path.join(productRoot, "package.json"));
const { chromium } = requireFromProduct("playwright");

const outDir = path.resolve(process.env.E2E_OUT_DIR || path.join(sdkRoot, "output/e2e/sdk-local/manual"));
const screenshotDir = path.join(outDir, "screenshots");
const gatewayUrl = (process.env.SYNAPSE_GATEWAY_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const adminFrontUrl = (process.env.ADMIN_FRONT_URL || "http://localhost:4000").replace(/\/+$/, "");
const adminGatewayUrl = (process.env.ADMIN_GATEWAY_URL || "http://127.0.0.1:8300").replace(/\/+$/, "");
const adminCookieName = process.env.ADMIN_SESSION_COOKIE_NAME || "synapse_admin_session";
const adminTotpSecret = process.env.ADMIN_TOTP_SECRET || "JBSWY3DPEHPK3PXP";

fs.mkdirSync(screenshotDir, { recursive: true });

function base32ToBuffer(secret) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const char of String(secret).replace(/=+$/g, "").replace(/\s+/g, "").toUpperCase()) {
    const value = alphabet.indexOf(char);
    if (value < 0) throw new Error(`Invalid ADMIN_TOTP_SECRET character: ${char}`);
    bits += value.toString(2).padStart(5, "0");
  }
  const bytes = [];
  for (let index = 0; index + 8 <= bits.length; index += 8) {
    bytes.push(Number.parseInt(bits.slice(index, index + 8), 2));
  }
  return Buffer.from(bytes);
}

function generateTotpCode(secret, nowMs = Date.now()) {
  const counter = Math.floor(nowMs / 1000 / 30);
  const counterBuffer = Buffer.alloc(8);
  counterBuffer.writeBigUInt64BE(BigInt(counter));
  const digest = crypto.createHmac("sha1", base32ToBuffer(secret)).update(counterBuffer).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  const binary = ((digest[offset] & 0x7f) << 24)
    | ((digest[offset + 1] & 0xff) << 16)
    | ((digest[offset + 2] & 0xff) << 8)
    | (digest[offset + 3] & 0xff);
  return String(binary % 1_000_000).padStart(6, "0");
}

function parseSessionCookie(setCookieHeader) {
  const header = Array.isArray(setCookieHeader) ? setCookieHeader.join(",") : String(setCookieHeader || "");
  const match = header
    .split(/,(?=\s*[^;,]+=)/)
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${adminCookieName}=`));
  return match ? match.split(";")[0].slice(adminCookieName.length + 1) : "";
}

async function loginAdmin() {
  if (process.env.ADMIN_SESSION_TOKEN) {
    return { sessionToken: process.env.ADMIN_SESSION_TOKEN, csrfToken: process.env.ADMIN_CSRF_TOKEN || "" };
  }
  const response = await fetch(`${adminGatewayUrl}/api/admin/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: process.env.ADMIN_EMAIL || "super@synapse.network",
      password: process.env.ADMIN_PASSWORD || "qwer@1234",
      otpCode: process.env.ADMIN_OTP_CODE || generateTotpCode(adminTotpSecret),
    }),
  });
  const body = await response.json().catch(() => ({}));
  const setCookie = typeof response.headers.getSetCookie === "function"
    ? response.headers.getSetCookie()
    : response.headers.get("set-cookie");
  const sessionToken = parseSessionCookie(setCookie);
  if (!response.ok || !body.success || !sessionToken) {
    throw new Error(`Admin login failed: ${response.status} ${JSON.stringify(body).slice(0, 800)}`);
  }
  return { sessionToken, csrfToken: body.data?.csrfToken || "" };
}

async function screenshot(page, name, url, expectedTexts = []) {
  await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
  const bodyText = String(await page.textContent("body") || "");
  if (bodyText.includes("Login") && bodyText.includes("Password")) {
    throw new Error(`${name} appears to be unauthenticated`);
  }
  if (expectedTexts.length > 0) {
    if (!expectedTexts.some((text) => bodyText.includes(text))) {
      throw new Error(`${name} did not contain expected text: ${expectedTexts.join(" | ")}`);
    }
  }
  const filePath = path.join(screenshotDir, `${name}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  return { name, path: filePath, url };
}

async function main() {
  const screenshots = [];
  const browser = await chromium.launch({ headless: true });
  try {
    const publicContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const publicPage = await publicContext.newPage();
    screenshots.push(await screenshot(publicPage, "gateway-health", `${gatewayUrl}/health`, ["ok"]));
    await publicContext.close();

    const auth = await loginAdmin();
    const adminContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await adminContext.addCookies([
      {
        name: adminCookieName,
        value: auth.sessionToken,
        url: adminFrontUrl,
        httpOnly: true,
        sameSite: "Lax",
      },
      {
        name: adminCookieName,
        value: auth.sessionToken,
        url: "http://127.0.0.1:4000",
        httpOnly: true,
        sameSite: "Lax",
      },
      {
        name: adminCookieName,
        value: auth.sessionToken,
        url: adminGatewayUrl,
        httpOnly: true,
        sameSite: "Lax",
      },
      {
        name: adminCookieName,
        value: auth.sessionToken,
        url: "http://localhost:8300",
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);
    if (auth.csrfToken) {
      await adminContext.addInitScript((csrfToken) => {
        window.sessionStorage.setItem("synapse.admin.csrfToken", csrfToken);
      }, auth.csrfToken);
    }
    const adminPage = await adminContext.newPage();
    screenshots.push(await screenshot(
      adminPage,
      "admin-invocation-revenue",
      `${adminFrontUrl}/dashboard/analytics/invocation-revenue`,
      ["调用与收入", "Invocation", "Revenue", "Analytics"],
    ));
    screenshots.push(await screenshot(
      adminPage,
      "admin-money-flow",
      `${adminFrontUrl}/dashboard/analytics/money-flow`,
      ["资金流", "Money", "Flow", "Analytics"],
    ));
    await adminContext.close();

    const reportPath = path.join(outDir, "report.html");
    if (fs.existsSync(reportPath)) {
      const reportContext = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
      const reportPage = await reportContext.newPage();
      screenshots.push(await screenshot(reportPage, "evidence-report", pathToFileURL(reportPath).href, ["SDK Local E2E Evidence"]));
      await reportContext.close();
    }
  } finally {
    await browser.close();
  }
  fs.writeFileSync(path.join(outDir, "screenshots.json"), JSON.stringify(screenshots, null, 2));
  console.log(JSON.stringify(screenshots, null, 2));
}

main().catch((error) => {
  console.error(`[sdk-local-screenshots] ${error.stack || error.message || String(error)}`);
  process.exit(1);
});
