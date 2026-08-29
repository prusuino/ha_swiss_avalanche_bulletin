# Security Policy

## Supported Versions

Only the latest release is supported. Please update to the latest version before reporting an issue.

## Reporting a Vulnerability

This integration only reads publicly published, unauthenticated data from its official Swiss data source, over HTTPS only, from two hosts: `aws.slf.ch` (avalanche bulletin and warning-region lookup) and `measurement-api.slf.ch` (IMIS station list, measurements and daily snow data). The data it sends is limited to the latitude/longitude you configure for a bulletin location — by default your Home Assistant home location — which goes to the warning-region lookup on `aws.slf.ch` so that the SLF can resolve the region, plus the codes of the IMIS stations you selected and the current date, which travel in the request URLs. Nothing else leaves your system; for the IMIS station list, your home location is only used locally to sort the stations by distance. It does not handle credentials, personal data, or write access to any external system. If you still believe you have found a security issue (e.g. in how data is parsed or how entities are exposed), please report it privately via [GitHub Security Advisories](../../security/advisories/new) rather than opening a public issue.

For anything that is not security-sensitive (bugs, feature requests), please use the regular [Issues](../../issues) tab instead.
