# Image publication schema bundle v1

This directory is the stable machine-readable bundle path for the
`image-publish-v1` contract. The directory version identifies the bundle
entrypoint consumed by callers; it does not force every document kind to use
`schema_version: 1`.

Each schema declares its concrete version in both `title` and
`schema_version`. In the current bundle:

| Document family | Concrete version |
| --- | ---: |
| Image build request and PVE publish request | 2 |
| Image build result, image test request/result, artifact, cleanup request and retire request | 1 |
| PVE template preview, template record and template result | 3 |

Keep the directory path, schema `$id` URLs and filenames stable when consuming
this bundle. Validate the document's `kind` and its declared `schema_version`
against the individual schema; do not infer the concrete version from the
directory name alone.

The current build request requires `disk_size_gib` and accepts boolean
`customization.package_upgrade`. Publication requires `hardware.bridge`, with
explicit null selecting no NIC. Cross-field capacity, firmware and network
relationships are also validated by the offline `check` implementation.
