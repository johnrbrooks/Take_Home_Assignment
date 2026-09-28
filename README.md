# Oxalis Confluence Provisioning Toolkit

A small Python CLI for provisioning the Confluence Cloud environment required by the Oxalis Senior Technical Specialist take-home exercise.

The toolkit is intentionally modular: each provisioning task can be run independently, or the full workflow can be executed in sequence.

## What the toolkit configures

The toolkit can:

- Resolve Atlassian `accountId` values from user email addresses.
- Invite standard users to the Confluence site.
- Create and populate a standard-users group.
- Create the required Confluence spaces.
- Configure space access using Confluence Cloud role-based access control (RBAC).
- Create the required page in the Collaborative Workspace.
- Upload and embed an image on the page.
- Apply a page-level read restriction.
- Verify the resulting users, groups, roles, spaces, content, and restrictions.

It does **not**:

- Create or manage Atlassian billing/subscriptions.
- Require the invited test users to log in.
- Authenticate as the standard users.
- Replace an enterprise identity-management or SCIM provisioning solution.
- Delete unrelated users, groups, spaces, roles, or permissions from the site.

---

## Requirements

- Python 3.11+
- A Confluence Cloud site with permission to:
  - invite users
  - create groups
  - create spaces
  - manage space roles
  - create and restrict content
- An Atlassian API token for the site administrator.
- An Atlassian Organization API key with access to resolve organization users.
- The five exercise users listed in `users.csv`.

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

---

## User input

Populate `users.csv` before running the toolkit.

Example:

```csv
user_key,email,account_id,site_role,collaborative_role
admin-user,admin@example.com,,admin,site_admin
user-1,user1@example.com,,standard,space_admin
user-2,user2@example.com,,standard,editor
user-3,user3@example.com,,standard,editor
user-4,user4@example.com,,standard,editor
```

`account_id` can be left blank initially. The **Resolve user account IDs** task updates it automatically.

For test users, valid email aliases such as Gmail `+` aliases can be used. The users do not need to log in for the toolkit to configure their group membership and permissions once an Atlassian `accountId` exists.

---

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

The toolkit resolves values in this order:

1. Environment variable / `.env`
2. Interactive prompt
3. A displayed default, where one exists

If a resource value is not configured in `.env`, the CLI asks for it when that task first needs it.

Typical `.env` values:

```text
ATLASSIAN_SITE_URL=https://your-site.atlassian.net
ATLASSIAN_USER_EMAIL=
ATLASSIAN_API_TOKEN=

ATLASSIAN_ORG_ID=
ATLASSIAN_ORG_API_KEY=
ATLASSIAN_DIRECTORY_ID=

USERS_CSV_PATH=users.csv

STANDARD_USERS_GROUP=
COLLAB_SPACE_NAME=
COLLAB_SPACE_KEY=
RESTRICT_SPACE_NAME=
RESTRICT_SPACE_KEY=
RESTRICTED_READ_ONLY_ROLE_NAME=
RESTRICTED_PAGE_TITLE=
RESTRICTED_PAGE_USER_KEY=
WORKSPACE_IMAGE_PATH=
```

Secrets entered interactively are hidden from the terminal.

Values entered during one interactive CLI session are reused by later tasks in that same session.

---

## Running the toolkit

Start the interactive CLI:

```bash
python cli.py
```

The menu provides the following operations.

### 1. Resolve user account IDs

Looks up each CSV email address in the Atlassian organization directory and writes the resolved `accountId` back to `users.csv`.

**Does:** resolve existing Atlassian identities.

**Does not:** create users that do not yet exist.

If a user is unresolved, run **Invite / add users to Confluence**, allow Atlassian provisioning to complete, then run this step again.

---

### 2. Invite / add users to Confluence

Submits the four standard-user email addresses to the Confluence site invitation API.

Existing users are safe to submit again; Atlassian ignores addresses that already have site access.

**Does:** request Confluence site access for the four standard users.

**Does not:** require the users to log in, resolve their `accountId`, or assign the exercise-specific group.

Invitation processing is asynchronous. Run **Resolve user account IDs** again afterward.

---

### 3. Create / update standard-users group

Creates the exercise-specific group and adds all four standard users.

If `STANDARD_USERS_GROUP` is not set, the CLI asks for the group name.

The administrator is intentionally excluded.

**Does:** create/reuse the group and reconcile its four expected members.

**Does not:** grant space access by itself.

---

### 4. Create required spaces

Creates:

- Collaborative Workspace
- Restricted Workspace

If the space names or keys are not configured, the CLI asks for them.

The assignment-friendly default keys are:

```text
COLLAB
RESTRICT
```

**Does:** create/reuse the spaces.

**Does not:** configure their final access model. Run **Configure space permissions** next.

---

### 5. Configure space permissions

Detects the site's Confluence space-access mode.

For modern role-based sites, the toolkit uses Confluence RBAC.

#### Collaborative Workspace

The toolkit assigns:

```text
standard-users group -> Collaborator
designated user-1    -> Admin
```

This gives all four standard users collaborative read/write access while giving one standard user space-administrator access.

#### Restricted Workspace

The toolkit assigns:

```text
standard-users group -> custom read-only role
site administrator   -> Admin
```

The custom role contains `View content` access only. It is used instead of the built-in Viewer role because the built-in Viewer role also permits commenting.

**Does:** reconcile the required assignment-specific space roles.

**Does not:** remove unrelated roles or permissions belonging to other site configuration.

---

### 6. Create restricted page and embedded image

Creates the required page in **Collaborative Workspace**.

The task:

1. Creates or reuses the page.
2. Adds the required body content.
3. Uploads the configured image as a Confluence attachment.
4. Embeds the attachment in the page.
5. Applies a page-level read restriction.

The selected standard user is the only one of the four standard users permitted to read the page.

The authenticated administrator is also retained in the read restriction because Confluence does not allow the requesting user to apply a restriction that immediately removes their own access.

**Does:** implement the assignment's page-level restriction.

**Does not:** create this page inside Restricted Workspace.

---

### 7. Verify configuration

Reads the resulting Confluence configuration and validates the expected state.

Checks include:

- all five users have resolved `accountId` values
- all users are visible to Confluence
- the standard-users group exists
- all four standard users belong to the group
- the administrator is not in the group
- both spaces exist
- Collaborative Workspace has the expected Collaborator/Admin role assignments
- Restricted Workspace has the expected read-only/Admin assignments
- the required page exists
- the image attachment exists
- the intended standard user can read the restricted page
- the other three standard users cannot read it
- the administrator retains access

This task does not modify configuration.

---

### 8. Run complete provisioning workflow

Runs the tasks in dependency order:

```text
Resolve existing users
        ↓
Invite standard users
        ↓
Resolve users again
        ↓
Create/update group
        ↓
Create spaces
        ↓
Configure roles
        ↓
Create content and restriction
        ↓
Verify
```

The workflow pauses between steps during interactive execution.

If Atlassian has not finished provisioning invited users, the workflow stops before group/permission operations that require `accountId` values.

---

## Recommended first-time workflow

For a clean test site:

```text
1. Populate users.csv
2. Run Option 1
3. Run Option 2
4. Run Option 1 again until all five accountIds resolve
5. Run Option 3
6. Run Option 4
7. Run Option 5
8. Run Option 6
9. Run Option 7
```

Once the workflow has been validated, Option 8 can be used to run the suite end-to-end.

---

## Re-running tasks

The toolkit is designed to be safely rerunnable where practical.

Existing resources are generally reused and reconciled instead of blindly recreated.

Examples:

- existing groups are reused
- existing group members are skipped
- existing spaces are reused
- existing role assignments are checked before updating
- existing pages and attachments are updated/reused

The toolkit intentionally avoids deleting unrelated site configuration.

---

## Current Atlassian API model

This implementation uses current Confluence Cloud APIs, including:

- Confluence REST API v2 for site invitations, spaces, pages, space roles, and role assignments
- Confluence REST API v1 where still required for supported content/attachment/restriction operations
- Atlassian Organizations REST API v2 for exact email-to-`accountId` resolution

Relevant documentation:

- Confluence REST API v2: https://developer.atlassian.com/cloud/confluence/rest/v2/
- Confluence REST API v1: https://developer.atlassian.com/cloud/confluence/rest/v1/
- Atlassian Organizations REST API: https://developer.atlassian.com/cloud/admin/organization/rest/
- Confluence role-based access: https://support.atlassian.com/confluence-cloud/docs/what-are-confluences-roles/

---

## AI attribution

This toolkit was developed collaboratively with ChatGPT.

See `ATTRIBUTION.md` for:

- AI-generated portions of the implementation
- changes made during live tenant testing
- reasons for those changes
- Atlassian API constraints discovered during implementation

This documentation should be kept with the submitted source code.
