# Security policy

## Reporting

Do not open a public issue for a parser bypass, resource-exhaustion vector,
unsafe template behavior, dependency vulnerability, credential exposure, or
production data found in a fixture. Use GitHub's private vulnerability
reporting / Security Advisory workflow for this repository.

Use only synthetic reproduction data. If private reporting is unavailable,
contact an OpenNV organization owner privately and request a secure channel
before sharing details.

## Supported versions

Until the first stable release, fixes are applied to the latest `main`
revision. Consumers should pin an immutable commit or release tag and validate
it with the exact engine versions used in their deployment.

## Trust model

Definitions are reviewed configuration, not inherently trusted input. A
consumer must strictly decode the documented schema, reject unknown or
duplicate identities, constrain file and output sizes, use an allow-list of
pure generators, prevent filesystem/network/host-language access, and activate
only complete validated snapshots.

Synthetic fixtures may still resemble sensitive operational evidence. Never
contribute production CLI output, credentials, routable management addresses,
customer names, serial numbers, or proprietary vendor documentation examples.
