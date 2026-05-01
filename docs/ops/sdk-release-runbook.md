# SDK Package Release Runbook

- Status: Public Preview
- Last verified against code: 2026-05-01

This runbook covers SynapseNetwork SDK package publishing. SDKs are **published** to language registries; they are not deployed to staging or production runtime environments.

## Release Model

- `release_train_version` is the human-facing SDK train, for example `0.1.0`.
- `package_version` is the actual language package version.
- New trains initialize all package versions to the train version.
- A single language can hotfix forward, for example train `0.1.0` with Python package `0.1.1`.
- Published package versions are immutable. Do not overwrite or republish the same version; publish a higher patch version instead.
- SDK examples may default to `environment="staging"`, but package release channels are registry channels, not Gateway environments.

## Package Platforms

| Language | Package | Registry | Publish notes |
| --- | --- | --- | --- |
| Python | `synapse-client` | PyPI | Optional TestPyPI dry-run before public release. |
| TypeScript | `@synapse-network/sdk` | npm | Use npm dist-tags such as `preview`, `next`, or `latest`. |
| Go | `github.com/cliff-personal/Synapse-Network-Sdk/go` | Go module via GitHub | Because the module is in `/go`, tags must use `go/vX.Y.Z`. |
| Java | `ai.synapsenetwork:synapse-network-sdk` | Maven Central | If Central is not ready, publish preview artifacts to GitHub Packages Maven. |
| .NET | `SynapseNetwork.Sdk` | NuGet.org | Use NuGet package versions and never overwrite an existing version. |
| All | GitHub Release | GitHub | One release page per train with links to all language packages. |

## Preflight

Run the full SDK quality gate:

```bash
bash scripts/ci/pr_checks.sh
```

Build/package checks:

```bash
python -m build python
python -m twine check python/dist/*

cd typescript
npm ci
npm run build
npm pack

cd ../go
go test ./...
go list ./...

cd ../java
mvn -B package

cd ../dotnet
dotnet test tests/SynapseNetwork.Sdk.Tests/SynapseNetwork.Sdk.Tests.csproj
dotnet pack src/SynapseNetwork.Sdk/SynapseNetwork.Sdk.csproj -c Release
```

## GitHub Actions Publishing

Use `.github/workflows/publish-sdk.yml` for controlled package publishing.

Inputs:

- `release_train_version`
- `package`
- `package_version`
- `channel`
- `dry_run`

Dry-run first:

```bash
gh workflow run publish-sdk.yml \
  --ref main \
  -f release_train_version=0.1.0 \
  -f package=python \
  -f package_version=0.1.0 \
  -f channel=preview \
  -f dry_run=true
```

Publish only after dry-run succeeds:

```bash
gh workflow run publish-sdk.yml \
  --ref main \
  -f release_train_version=0.1.0 \
  -f package=python \
  -f package_version=0.1.0 \
  -f channel=preview \
  -f dry_run=false
```

## Registry Secrets

Registry credentials must stay in GitHub Actions secrets. Do not store them in Synapse-Network-Growing or any repo file.

- `PYPI_API_TOKEN`
- `NPM_TOKEN`
- `NUGET_API_KEY`
- Maven Central or GitHub Packages credentials
- GPG signing secrets if Maven Central requires signing

## Go Tag Rule

The Go module lives in a subdirectory:

```text
go/go.mod -> module github.com/cliff-personal/Synapse-Network-Sdk/go
```

Therefore Go package publishing uses subdirectory tags:

```bash
git tag go/v0.1.0
git push origin go/v0.1.0
```

Do not rely on a root `v0.1.0` tag for the Go module.

## Growing Release Center

Use `http://localhost:9700/releases` -> `SDK Packages`.

Recommended flow:

1. Click `Initialize Release Train`.
2. Enter train version, channel, release notes, and selected packages.
3. Run `Dry Run` for each package.
4. Publish packages after dry-runs pass.
5. Sync statuses until every package is `published` or explicitly `failed`.
6. Create or update the GitHub Release with package URLs.

## Post-Publish Verification

Verify install and one minimal staging invocation per language where practical:

- Install package from the public registry.
- Search for a free or smoke service.
- Invoke with an Agent Key.
- Fetch receipt.
- Confirm docs link back to the published version.

## Rollback Policy

SDK registries generally do not support safe rollback by overwriting a version. If a published package is bad:

1. Mark the package release failed or superseded in the release center notes.
2. Publish a higher patch version.
3. Update GitHub Release notes and docs with the fixed version.
