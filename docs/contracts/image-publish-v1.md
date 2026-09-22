# Image build and PVE publication contract v1

This is the stable consumer entrypoint for the image/PVE handoff. The
normative OpenSpec source is
[`contracts/image-publish-v1.md`](../../openspec/changes/separate-image-build-and-pve-publish/contracts/image-publish-v1.md);
the JSON schemas shipped below are the machine-readable subset of that
contract.

The stable schemas live under `automation/schemas/image-publish/v1/`:

- `image-build-request.schema.json` and `image-test-request.schema.json`
- `image-artifact.schema.json` and `image-test-result.schema.json`
- `pve-template-publish-request.schema.json`, `pve-template-preview.schema.json`, and `pve-template-record.schema.json`

The shared launcher validates these documents with the same normalized
contract code at `automation/src/iaas_automation/image/contracts.py` and
writes `diagnostics/normalized.json` for `image check`. The file contains the
normalized document and `input_digest`; callers should bind that digest rather
than JSON formatting or object-key order.

Concrete cross-repository fixtures live under `docs/examples/image-publish/`:
the inline artifact, publish request, preview, complete execution admission and
successful publisher result are all valid inputs. The PVE admission uses the
existing full `validate_execution_admission` contract; its `plan_digest` is the
lowercase digest without the `sha256:` display prefix used by the native
preview digest.

Image operations are direct local tasks:

```text
iaas runtime --component image --operation check|build|test|read|verify|clean
```

PVE template publication remains an admitted plan/apply lifecycle:

```text
iaas runtime --component pve-template --operation check|read|plan|apply|verify
```

Publication consumes a protected `PVE_ARTIFACT_URL` only in the publisher,
verifies the disk SHA-256 before the first PVE write, and never sends the
locator to PVE. Build history, template publication, guest acceptance and
caller promotion remain separate results.
