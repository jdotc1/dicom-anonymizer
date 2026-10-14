# Publication preparation

## Project owner

Proposed display identity: DICOM Anonymizer Project. Proposed organization handle: `dicom-anonymizer-project`. This is a recommendation, not an organization claimed to exist or a reserved name. The authenticated maintainer currently has no visible organization memberships. If an existing organization is preferred, provide its exact handle and make appropriate repository-admin access available.

Create a GitHub Free organization through GitHub Settings > Organizations > New organization. The owner completes the account/organization prompts and any required terms. Use the project display name, keep optional public personal/contact fields empty, review membership visibility and public activity, and avoid adding personal affiliation to the public organization profile. This does not promise anonymity: GitHub account activity and administration can still associate people with a project.

The public Git author and committer display name remains DICOM Anonymizer Project. The non-deliverable `maintainers@dicom-anonymizer.invalid` address is commit metadata, not the security contact. A GitHub organization does not itself supply a user noreply identity. Retain neutral metadata unless a dedicated project/bot identity is chosen; do not insert a personal noreply address if its account linkage is unwanted. Preserve legally required copyright attribution.

## Private staging after the owner exists

Keep Actions disabled during private staging; the source workflow itself is manual-only. Do not create GitHub Pages, releases, public discussions or sponsorship/contact links during staging. No test execution, build, artifact hash or baseline verification is authorized by creating the repository.

## Security contact

Use GitHub private vulnerability reporting; no dedicated email has been requested. SECURITY.md and `.github/VULNERABILITY_REPORT.yml` are prepared. GitHub exposes this reporting feature for public repositories, so it cannot be claimed active while this staging repository remains private.

At the approved public launch, enable private vulnerability reporting and confirm the reporting status and form. Configure the actual maintainer account to receive Security alerts/private-report notifications. Do not expose notification email addresses in repository content. If an active contact is required before public launch, the owner must supply a real project mailbox; none is invented here.

## Final approval package

Present the actual organization/repository identity, PRIVATE visibility, source commit, MIT license, documentation and synthetic examples for approval. Record that the export-specific native/runtime changes remain unexecuted and the release is a source preview. Confirm ownership/redistribution rights and private security-notification responsibility.

## References

[Create an organization](https://docs.github.com/en/organizations/collaborating-with-groups-in-organizations/creating-a-new-organization-from-scratch)

[Configure private vulnerability reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository)
