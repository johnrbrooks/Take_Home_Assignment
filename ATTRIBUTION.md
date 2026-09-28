# Code Attribution

This project was developed collaboratively with **OpenAI ChatGPT (GPT-5.6 Sol)** on September 27, 2026.

The take-home exercise explicitly permits AI-assisted development but requires clear disclosure of what was generated, what was directed or modified by the candidate, and what changes were required to make generated code functional.

## Candidate contribution

The candidate defined and refined the implementation strategy, including:

- Using Python for the provisioning utility.
- Using CSV as the source of user input.
- Resolving Atlassian `accountId` values programmatically rather than storing them manually.
- Building a modular CLI with independently runnable provisioning steps.
- Supporting environment variables with interactive prompting when values are not configured.
- Keeping group names, space names, keys, page configuration, and other resource values configurable.
- Requiring tasks to be safely rerunnable where practical.
- Testing each provisioning stage against the live Confluence Cloud tenant before proceeding.
- Choosing synthetic Gmail aliases for test identities so Atlassian users could be provisioned without requiring separate real mailboxes.
- Reviewing API behavior and reporting live failures that drove the corrections documented below.

The candidate also supplied the real environment configuration, user data, credentials, resource names, and final test-site configuration.

No source file should be represented as entirely candidate-authored unless the candidate independently rewrites that file before submission.

## LLM-generated implementation

ChatGPT generated the initial implementation and subsequent patches for:

- Repository and package structure.
- Interactive CLI orchestration.
- Environment/configuration handling.
- CSV parsing, validation, and `accountId` persistence.
- Confluence REST client.
- Atlassian Organizations REST client.
- User invitation workflow.
- Group creation and membership reconciliation.
- Space creation.
- Space role / permission configuration.
- Page creation and update logic.
- Attachment upload and embedding.
- Page-level content restriction logic.
- Verification workflow.
- Error handling and retry behavior.
- Unit tests.
- README and supporting documentation.

All generated code was reviewed and exercised against the live test tenant before being treated as complete.

## Changes required after live tenant testing

The initial AI-generated implementation required several changes once tested against the actual Atlassian Cloud environment.

| Issue observed | Initial generated behavior | Final change | Reason |
| --- | --- | --- | --- |
| User access check reported all test emails as already having site access even though Atlassian Administration showed only one licensed user | `check-access-by-email` was treated as authoritative before sending invitations | Removed the pre-check and submit the four standard-user emails directly to Confluence `invite-by-email` | The experimental access-check result did not match the actual licensed-user state in the tenant |
| Organization v2 invitation returned HTTP `402 payment-required` | Used `POST /admin/v2/orgs/{orgId}/users/invite` to provision users and product access | Reverted invitations to Confluence `POST /wiki/api/v2/user/access/invite-by-email`; retained Organizations v2 only for directory lookup and email-to-`accountId` resolution | The temporary Premium trial was not treated as a paid subscription by the Organization invitation endpoint |
| Group and space values needed to be reusable but not hardcoded | Initial configuration contained assignment-oriented defaults | Added lazy interactive prompting whenever relevant environment variables are absent; values are cached for the current CLI session | Allows the same utility to be configured interactively without requiring command-line arguments |
| Legacy space permission request initially failed because `read / space` had not been added first | Missing granular permissions were added from an unordered set | Added explicit ordering so `read / space` is applied before dependent permissions | Confluence requires direct read permission before adding other legacy permissions for the same user/group |
| Legacy permission API then failed with `InvalidRbacOperationException` | Used `POST /wiki/rest/api/space/{spaceKey}/permission` | Added space-role-mode detection and switched role-enabled tenants to Confluence v2 RBAC space-role APIs; legacy behavior remains only for `PRE_ROLES` tenants | The test tenant operates in roles-only mode and rejects non-RBAC permission updates |
| Built-in Viewer role was not strictly read-only | Initial permission model considered using standard Confluence roles | Created/reused a custom role containing `View content` only for Restricted Workspace | The built-in Viewer role also permits commenting, while the exercise requires read-only access |
| Page restriction request returned HTTP 400 because it would remove the API caller's own read access | Cleared restrictions and added the selected standard user first | Add the authenticated administrator to the read restriction first, then the selected standard user; verification ensures only one of the four standard users can read the page | Confluence prevents a requesting user from applying a restriction that immediately evicts that same user |
| Page placement needed to match the exercise exactly | Terminology around "restricted page" could imply Restricted Workspace | Final implementation creates the page in Collaborative Workspace and applies a page-level restriction there | The exercise specifically requires the restricted page to be created in the first space |

## Final permission model

The final implementation uses Confluence role-based access control where supported.

### Collaborative Workspace

- Standard-user group → **Collaborator**
- Designated standard user → **Admin**
- Site administrator retains administrative access

### Restricted Workspace

- Standard-user group → custom **view-only** role
- Site administrator → **Admin**

### Restricted page

- Created in **Collaborative Workspace**
- One selected standard user is granted page-level read access
- The authenticated/site administrator is also retained so the API caller does not lock itself out
- The remaining three standard users are verified as unable to read the page

## AI usage during development

ChatGPT was used for:

- architecture discussion
- API research and interpretation
- code generation
- refactoring
- debugging live API errors
- test generation
- documentation

The candidate did not blindly accept generated code. Each major workflow was executed against the live Atlassian tenant, observed failures were reported, and the implementation was revised based on actual behavior.

## External documentation used

Current Atlassian documentation was consulted throughout development, including:

- Confluence REST API v2  
  https://developer.atlassian.com/cloud/confluence/rest/v2/
- Confluence REST API v1  
  https://developer.atlassian.com/cloud/confluence/rest/v1/
- Atlassian Organizations REST API  
  https://developer.atlassian.com/cloud/admin/organization/rest/
- Confluence role-based access documentation  
  https://support.atlassian.com/confluence-cloud/docs/what-are-confluences-roles/
- Confluence custom role documentation  
  https://support.atlassian.com/confluence-cloud/docs/create-and-manage-custom-roles/

## Submission note

The candidate should be prepared to explain:

- why the solution is split into independently runnable CLI tasks
- why CSV was used as the input format
- why email addresses are resolved to immutable Atlassian `accountId` values
- why Confluence site invitation and Organizations directory lookup use different APIs
- why the final permission implementation uses RBAC space roles
- why a custom read-only role was required
- why the administrator remains included in the page-level read restriction
- what changed after live API testing and why
