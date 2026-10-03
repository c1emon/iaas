## 1. Current contracts and build

- [x] 1.1 Implement current build request/v2 explicit disk_size_gib and package_upgrade; synchronize schema and representative inputs.
- [x] 1.2 Reject undersized/unsupported shrink requests before provisioning and verify final capacity before success.
- [x] 1.3 Implement build-time upgrade, requested base software, agent/cloud-init/growth support and clone-ready cleanup; cover failure paths.

## 2. Publication and offline check

- [x] 2.1 Support explicit no-NIC publication through check/plan/create/verify/record with strict relationship checks.
- [x] 2.2 Complete offline build/publication/clone validation and safe file/field/reason diagnostics; cover unsupported parameters and zero external effects.
- [x] 2.3 Verify existing full clone/network/identity/disk growth paths and fix only required gaps, including bounded acceptance DNS/growth when selected.

## 3. Delivery and representative acceptance

- [ ] 3.1 Run relevant regressions and OpenSpec/schema checks, review diff/graph impacts and commit staged delivery.
- [ ] 3.2 Publish immutable fixed runtime/image-builder and launcher artifacts with normal CI checksums/digests.
- [ ] 3.3 Build and publish retained template 9000 with requested software, sources, 2 CPU/1 GiB/8 GiB and no NIC.
- [ ] 3.4 Full-clone a temporary VM in the existing dedicated pool, configure independent network/identity before first boot, expand to 128 GiB and verify actual guest growth/network/cloud-init/agent.
- [ ] 3.5 Recheck unchanged source, clean only this execution's temporary resources and record real evidence or explicit blockers.
- [ ] 3.6 Update current contracts/docs and infra-ops adaptation guidance; separate offline, real template and caller deployment conclusions.
