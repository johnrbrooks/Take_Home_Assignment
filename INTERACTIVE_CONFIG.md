# Interactive configuration behavior

Resource configuration is resolved lazily. A task only requests the values it
actually needs.

Resolution order:

1. Existing runtime override (if present)
2. Environment variable / `.env`
3. Interactive prompt
4. Suggested default when Enter is pressed

Examples:

- `manage-group` asks for `Standard users group name` only when
  `STANDARD_USERS_GROUP` is not already configured.
- `create-spaces` asks for the Collaborative and Restricted space names/keys
  only when the corresponding environment variables are absent.
- `permissions` reuses values already entered earlier in the same interactive
  CLI session because configuration values are cached for that process.
- `create-content` asks for the page title/image path when their environment
  variables are absent. The restricted user remains selectable interactively.

Example:

```text
Create / reconcile standard-users group
========================================
Standard users group name [oxalis-standard-users]: oxalis-engineering-users
```

If `.env` contains:

```text
STANDARD_USERS_GROUP=oxalis-standard-users
```

the prompt is skipped and that value is used automatically.

The same pattern applies to:

```text
COLLAB_SPACE_NAME
COLLAB_SPACE_KEY
RESTRICT_SPACE_NAME
RESTRICT_SPACE_KEY
RESTRICTED_PAGE_TITLE
RESTRICTED_PAGE_USER_KEY
WORKSPACE_IMAGE_PATH
```

`USERS_CSV_PATH` intentionally retains `users.csv` as a quiet project default.
