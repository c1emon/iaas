# runtime-network-proxy Specification

## Purpose
Define the controlled HTTP/HTTPS proxy environment channel for network-enabled runtime operations, including normalization, launcher/runtime propagation, Basic authentication protection, offline isolation, and supported transport boundaries.

## Requirements

### Requirement: Explicit normalized proxy environment
IaaS SHALL accept HTTP_PROXY/http_proxy, HTTPS_PROXY/https_proxy and NO_PROXY/no_proxy as a controlled network configuration channel independent of facility credentials. Each pair SHALL use its non-empty trimmed value, SHALL reject unequal non-empty values, and SHALL reach supported tools with identical upper/lowercase values. HTTP and HTTPS settings SHALL remain independent.

#### Scenario: Lowercase-only or matching proxy settings
- **WHEN** a network-enabled operation receives one non-empty spelling or equal non-empty values for a pair
- **THEN** the runtime and its actual networking subprocess SHALL receive the same effective value in both spellings
- **AND** an empty value SHALL be treated as unconfigured without inferring the other protocol's proxy

#### Scenario: Conflicting pair or invalid endpoint
- **WHEN** an online operation receives conflicting values, an unsupported URL, or malformed URL authentication
- **THEN** execution SHALL reject the proxy configuration before starting the networking tool
- **AND** errors SHALL identify the category or variable names without echoing values or authentication material

### Requirement: Bounded network-only propagation
The runtime SHALL extend its existing environment allowlist only for supported proxy variables on operations whose effective effects permit networking. It SHALL preserve operation-specific credentials, file selection and offline isolation, and SHALL NOT forward arbitrary host environment variables. Supported proxy names and neutralized ALL_PROXY/FTP_PROXY names SHALL be reserved independently of facility credentials and SHALL NOT be selected by dynamic cloud-init credential declarations, using case-insensitive name matching.

#### Scenario: Proxy name used as a guest credential
- **WHEN** a cloud-init password_env, public_key_env or equivalent dynamic credential declaration selects a reserved proxy name
- **THEN** discovery SHALL reject the conflict before returning credential names, reading the value or rendering guest material
- **AND** proxy configuration SHALL NOT become guest credentials or enter rendered plan material

#### Scenario: Container proxy reaches OpenTofu
- **WHEN** a valid network proxy is configured for PVE prepare-dependencies
- **THEN** OpenTofu init SHALL receive that proxy through the runtime's filtered subprocess environment
- **AND** preparation SHALL retain backend-disabled, state-free, facility-credential-free semantics

#### Scenario: Offline invocation with host proxy settings
- **WHEN** an offline operation is invoked while host or image proxy settings exist
- **THEN** its runtime container SHALL remain network-isolated and its tool environment SHALL omit usable proxy configuration
- **AND** proxy configuration SHALL NOT enable network access, trigger dependency installation or introduce unrelated credentials

### Requirement: Explicit supported networking paths
The proxy capability SHALL guarantee normalized environment delivery to network-enabled tool subprocesses, with OpenTofu dependency download as a required consumption path, and consistent configuration for existing environment-proxy-aware in-process clients. It SHALL NOT imply that every HTTP client uses a proxy. The documented support boundary SHALL identify explicitly direct PVE API clients, direct HTTPS uploads and template artifact downloads, whose existing transport choice SHALL remain unchanged by this change.

#### Scenario: Existing environment-aware in-process download
- **WHEN** an existing environment-proxy-aware client such as the image base urllib downloader runs in a network-enabled operation
- **THEN** it SHALL use the same normalized proxy configuration and protect authentication in public errors
- **AND** its existing TLS and checksum rules SHALL remain enforced

#### Scenario: Explicitly direct facility or artifact client
- **WHEN** execution uses a PVE client or template artifact download whose transport explicitly bypasses environment proxies
- **THEN** this change SHALL preserve that transport and disclose it as outside the environment proxy support boundary
- **AND** operation network permission or network_proxy_version SHALL NOT be reported as proof that the connection used a proxy

### Requirement: Native bypass and truthful proxy failures
NO_PROXY SHALL be passed consistently to supported tools and retain their documented native target-matching semantics. Unconfigured protocols SHALL retain direct behavior. IaaS SHALL NOT retry a failed proxied request by removing the proxy or weakening TLS validation.

#### Scenario: Target explicitly bypasses the proxy
- **WHEN** an actual runtime networking tool requests a non-loopback target matched by NO_PROXY
- **THEN** the target SHALL be contacted directly under that tool's native semantics
- **AND** removing the matching entry SHALL permit the configured proxy route to be observed

#### Scenario: Configured proxy cannot connect or establish TLS
- **WHEN** the networking tool fails because its proxy is unavailable or invalid for the connection
- **THEN** the operation SHALL return a non-zero failure with the tool phase, whether proxy configuration was active, and a protected diagnostic location
- **AND** it SHALL NOT silently use direct networking or disable TLS validation
- **AND** a generic download failure SHALL NOT be asserted to be caused by the proxy without supporting evidence

### Requirement: Proxy configuration stays outside execution artifacts
The proxy contract SHALL support unauthenticated HTTP/HTTPS endpoints and Basic username/password authentication supplied through valid URL userinfo, including legal percent-encoding. The username SHALL be non-empty and the password MAY be empty. Authentication SHALL be injected through the controlled environment, never as command-line values or facility credential discovery. Proxy values SHALL NOT enter ordinary logs, error output, summaries, provenance, input maps, request/admission or saved-plan metadata, or dependency archives. IaaS SHALL preserve existing sensitive raw recovery handling without exposing raw output as a public failure fallback.

#### Scenario: Valid authenticated proxy
- **WHEN** a caller supplies a valid Basic-authenticated proxy URL for a supported networking path
- **THEN** the actual client SHALL receive the configured proxy authentication through controlled environment injection
- **AND** launcher/runtime SHALL NOT resolve additional credentials or serialize the proxy URL into plan or public artifacts

#### Scenario: Invalid configuration, authentication rejection or reflected error
- **WHEN** authenticated proxy configuration is invalid, authentication is rejected, or a client error reflects authentication material
- **THEN** public errors and published diagnostics SHALL omit the authenticated URL, userinfo, username/password, their URL-encoded forms and Basic Authorization representation
- **AND** configuration rejection or tool failure SHALL remain non-zero without direct fallback or TLS weakening
- **AND** proxy-error authentication SHALL be redacted before diagnostic or error-capture persistence, even within protected recovery directories
- **AND** other protected tool captures SHALL retain existing sensitive recovery handling and SHALL NOT be published as raw errors
- **AND** authentication redaction SHALL NOT delete or rewrite infrastructure state/recovery data

### Requirement: Locked dependency integrity through a proxy
Proxy use SHALL preserve provider version locks, readonly lockfile checks, provider checksum validation, and existing dependency archive member and lock matching checks. Proxy configuration SHALL NOT configure unverified mirrors, change provider packaging, or grant backend/state access.

#### Scenario: Prepare and restore proxied dependencies
- **WHEN** a locked package is downloaded through the configured proxy and archived
- **THEN** the caller lockfile SHALL remain byte-identical, package checksums SHALL pass, and the archive SHALL retain the matching lock and valid provider content
- **AND** restore SHALL enforce existing archive member safety and lockfile matching independently of provider checksum verification

#### Scenario: Restored provider content is modified without changing its lock
- **WHEN** acceptance verifies a restored dependency archive whose provider content is tampered while the lockfile remains unchanged
- **THEN** backend-disabled OpenTofu initialization with readonly lockfile and the restored plugin directory SHALL reject the provider checksum
- **AND** the corresponding valid archive SHALL pass that native checksum check without facility credentials or backend/state access
- **AND** successful archive extraction alone SHALL NOT be reported as checksum validation
