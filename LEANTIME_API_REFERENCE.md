# Leantime JSON-RPC API -- Comprehensive Reference

> Derived from direct source-code analysis of the Leantime GitHub repository
> (`Leantime/leantime`, `master` branch, as of 2026-04-01).

---

## Table of Contents

1. [JSON-RPC Protocol & Authentication](#1-json-rpc-protocol--authentication)
2. [Method Routing Convention](#2-method-routing-convention)
3. [Projects API](#3-projects-api)
4. [Tickets / Tasks API](#4-tickets--tasks-api)
5. [Milestones](#5-milestones)
6. [Subtasks](#6-subtasks)
7. [Task Dependencies](#7-task-dependencies)
8. [Users API](#8-users-api)
9. [Clients API](#9-clients-api)
10. [Sprints API](#10-sprints-api)
11. [Comments API](#11-comments-api)
12. [Timesheets API](#12-timesheets-api)
13. [Tags / Labels](#13-tags--labels)
14. [Status Labels (Custom per Project)](#14-status-labels)
15. [Canvas / Lean Features](#15-canvas--lean-features)
16. [Batch Requests](#16-batch-requests)
17. [Practical Import Strategy](#17-practical-import-strategy)

---

## 1. JSON-RPC Protocol & Authentication

### Endpoint

```
POST https://<your-leantime>/api/jsonrpc
```

### Authentication

Use an API key generated from Leantime's admin panel. Pass it as a Bearer token
or via `x-api-key` header (depends on version). The simplest approach:

```
x-api-key: <your-api-key>
```

### Request format (JSON-RPC 2.0 -- mandatory)

```json
{
    "jsonrpc": "2.0",
    "method": "leantime.rpc.<domain>.<method>",
    "id": 1,
    "params": { ... }
}
```

- `jsonrpc` MUST be `"2.0"` (string) -- returns error otherwise.
- `id` should be a unique request identifier (int or string). Returned as-is in response.
- `params` is an object whose keys match the PHP method's parameter names exactly.

### Response format

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": <return-value>
}
```

On error:
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "error": { "code": -32600, "message": "..." }
}
```

### GET requests (alternative)

```
GET /api/jsonrpc?method=leantime.rpc.tickets.addTicket&params=<base64-encoded-json>&jsonrpc=2.0&id=1
```

---

## 2. Method Routing Convention

The method string is parsed as:

```
leantime.rpc.{module}.{method}
     -- OR --
leantime.rpc.{module}.{serviceName}.{method}
```

The 4-segment form assumes `serviceName == module`. So:

| Method string | Resolves to |
|---|---|
| `leantime.rpc.tickets.addTicket` | `Domain\Tickets\Services\Tickets::addTicket()` |
| `leantime.rpc.projects.projects.addProject` | `Domain\Projects\Services\Projects::addProject()` |
| `leantime.rpc.users.users.addUser` | `Domain\Users\Services\Users::addUser()` |

**The routing is case-sensitive.** Module/service names are converted via `Str::studly()`,
method names via `Str::camel()`.

**Only methods marked with `@api` in PHPDoc are intended for API use** (though the current
code does not strictly enforce this -- all public methods on service classes are callable).

Parameters are matched by **name** (not position). Required parameters that are missing
produce an error. Extra parameters are silently ignored.

---

## 3. Projects API

### `leantime.rpc.projects.projects.addProject`

Creates a new project. Returns the new project ID (int) on success.

| Parameter | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | string | **YES** | -- | Project name |
| `clientId` | int | **YES** | -- | Client/Organization ID (FK to zp_clients) |
| `details` | string | no | `""` | HTML description |
| `hourBudget` | numeric | no | `0` | Budgeted hours |
| `dollarBudget` | numeric | no | `0` | Dollar budget |
| `psettings` | string | no | `"restricted"` | Access: `"restricted"`, `"clients"`, `"all"` |
| `start` | string | no | `null` | Start date (user date format, e.g. `"2026-01-15"`) |
| `end` | string | no | `null` | End date |
| `assignedUsers` | array | no | `""` | Array of `{"id": userId, "projectRole": roleKey}` |

**Note:** The service hardcodes `type` to `"project"`. The repository accepts `type` and
`parent` directly, but the service layer does not expose them via `addProject`. To create
sub-projects or set types other than "project", you must use `editProject` after creation
or call the repository through a different path.

### `leantime.rpc.projects.projects.editProject`

| Parameter | Type | Required |
|---|---|---|
| `values` | array | YES |
| `id` | int | YES |

The `values` array is forwarded to the repository and can include all fields from
`addProject` plus: `state`, `menuType`, `type`, `parent`.

### `leantime.rpc.projects.projects.getProject`

| Parameter | Type | Required |
|---|---|---|
| `id` | int | YES |

Returns: associative array with all project fields, or `false`.

### `leantime.rpc.projects.projects.getAll`

| Parameter | Type | Default |
|---|---|---|
| `showClosedProjects` | bool | `false` |

### Project States

| Value | Label |
|---|---|
| `0` | OPEN |
| `1` | CLOSED |
| `null` | OPEN (treated as 0) |

### Project Types

The base system defines `"project"` as the only type. `"strategy"` and `"program"` are
protected/reserved types and filtered out from the public type list. Plugins can add more
via the `filterProjectType` event filter.

### Project Hierarchy (Sub-projects)

The `zp_projects` table has a `parent` column (int, nullable). When a project has
`parent = <another_project_id>`, it is a child project. The service method
`getProjectHierarchyAssignedToUser()` returns the tree structure. However, `addProject`
at the service level does not accept `parent` -- you need to use `editProject` to set it
after creation, or insert via the repository.

### Project Access Settings (`psettings`)

| Value | Meaning |
|---|---|
| `"restricted"` | Only explicitly assigned users (default) |
| `"clients"` | All users in the same client organization |
| `"all"` | All users in the system |

---

## 4. Tickets / Tasks API

### `leantime.rpc.tickets.addTicket`

Creates a new ticket. Returns the new ticket ID (int) on success.

| Parameter | Type | Required | Default | Notes |
|---|---|---|---|---|
| `headline` | string | **YES** | -- | Title (required, returns error if empty) |
| `type` | string | no | `"task"` | One of: `"task"`, `"subtask"`, `"story"`, `"bug"` |
| `description` | string | no | `""` | HTML description body |
| `projectId` | int | no | session project | FK to zp_projects |
| `editorId` | int/string | no | `""` | Assigned user ID (the "editor"/assignee) |
| `status` | int | no | `3` | Status code (see status table below) |
| `priority` | int | no | `""` | Priority code (see priority table below) |
| `dateToFinish` | string | no | `""` | Due date, e.g. `"2026-06-15"` |
| `timeToFinish` | string | no | `""` | Due time, e.g. `"17:00"` |
| `editFrom` | string | no | `""` | Gantt/timeline start date, e.g. `"2026-05-01"` |
| `timeFrom` | string | no | `""` | Start time |
| `editTo` | string | no | `""` | Gantt/timeline end date |
| `timeTo` | string | no | `""` | End time |
| `planHours` | numeric | no | `""` | Planned hours |
| `storypoints` | numeric | no | `""` | Story points / effort |
| `hourRemaining` | numeric | no | `""` | Remaining hours estimate |
| `sprint` | int | no | `""` | Sprint ID (FK to zp_sprints) |
| `tags` | string | no | `""` | Comma-separated tag string (e.g. `"backend,urgent"`) |
| `acceptanceCriteria` | string | no | `""` | Acceptance criteria (HTML) |
| `dependingTicketId` | int | no | `""` | Parent/predecessor ticket ID |
| `milestoneid` | int | no | `""` | Milestone ID (FK: another ticket of type "milestone") |
| `collaborators` | array | no | `[]` | Array of user IDs to add as collaborators |

### `leantime.rpc.tickets.quickAddTicket`

Simpler version with fewer fields. Same parameters as `addTicket` but processes
fewer of them. Accepts `milestone` (not `milestoneid`) as the key name for the
milestone parameter.

| Parameter | Type | Required | Default | Notes |
|---|---|---|---|---|
| `headline` | string | **YES** | -- | |
| `type` | string | no | `"task"` | |
| `description` | string | no | `""` | |
| `projectId` | int | no | session | |
| `editorId` | int | no | session user | |
| `dateToFinish` | string | no | `""` | |
| `status` | int | no | `3` | |
| `storypoints` | int | no | `""` | |
| `planHours` | int | no | `""` | |
| `sprint` | int | no | `""` | |
| `priority` | int | no | `""` | |
| `editFrom` | string | no | `""` | |
| `editTo` | string | no | `""` | |
| `milestone` | int | no | `""` | Note: key is `milestone`, not `milestoneid` |
| `dependingTicketId` | int | no | `""` | |
| `sortIndex` | int | no | `""` | |

### `leantime.rpc.tickets.updateTicket`

Full update (replaces all fields). Requires `id` inside the `values` parameter.

| Parameter | Type | Required |
|---|---|---|
| `values` | array | YES |

The `values` array uses the **exact same keys** as `addTicket` plus `id`.
If `headline` is not provided, it is preserved from the current ticket.

### `leantime.rpc.tickets.patch`

Partial update. Only updates the fields you provide.

| Parameter | Type | Required |
|---|---|---|
| `id` | int | YES |
| `params` | array | YES |

**Patchable fields** (from `PATCHABLE_COLUMNS` constant):

```
headline, type, description, projectId, status, date, dateToFinish,
sprint, storypoints, priority, hourRemaining, planHours, tags, editorId,
userId, editFrom, editTo, acceptanceCriteria, dependingTicketId,
milestoneid, sortIndex, kanbanSortIndex
```

### `leantime.rpc.tickets.getTicket`

| Parameter | Type | Required |
|---|---|---|
| `id` | int | YES |

Returns a `Tickets` model object (serialized as array).

### `leantime.rpc.tickets.getAll`

| Parameter | Type | Required | Default |
|---|---|---|---|
| `searchCriteria` | array | no | `null` |
| `limit` | int | no | `null` |

Search criteria keys: `currentProject`, `users`, `status` (e.g. `"not_done"`),
`sprint`, `type`, `excludeType`, `milestone`, `priority`, `clients`,
`orderBy`, `orderDirection`, `groupBy`, `term`, `effort`, `dateFrom`, `dateTo`.

### `leantime.rpc.tickets.delete`

| Parameter | Type | Required |
|---|---|---|
| `id` | int | YES |

### Ticket Types

```python
TICKET_TYPES = ["task", "subtask", "story", "bug"]
```

There is also `"milestone"` which is used internally -- milestones are tickets with
`type = "milestone"` (see Milestones section).

### Type Icons

| Type | Icon |
|---|---|
| `story` | `fa-book` |
| `task` | `fa-check-square` |
| `subtask` | `fa-diagram-successor` |
| `bug` | `fa-bug` |

### Default Status Codes (Seed Values)

These are the DEFAULT statuses. **Projects can customize statuses** via the settings,
so the actual status labels and codes may differ per project.

| Code | Name | CSS Class | Status Type | Kanban Column | Sort |
|---|---|---|---|---|---|
| `3` | New | `label-info` | `NEW` | yes | 1 |
| `1` | Blocked | `label-important` | `INPROGRESS` | yes | 2 |
| `4` | In Progress | `label-warning` | `INPROGRESS` | yes | 3 |
| `2` | Waiting for Approval | `label-warning` | `INPROGRESS` | yes | 4 |
| `0` | Done | `label-success` | `DONE` | yes | 5 |
| `-1` | Archived | `label-default` | `DONE` | no | 6 |

**Status types** (grouping): `NEW`, `INPROGRESS`, `DONE`.

To get the actual statuses for a project:

```
leantime.rpc.tickets.getStatusLabels
params: { "projectId": 123 }
```

### Priority Values

| Code | Label |
|---|---|
| `1` | Critical |
| `2` | High |
| `3` | Medium |
| `4` | Low |
| `5` | Lowest |

### Effort / Story Point Labels

| Value | Label |
|---|---|
| `0.5` | < 2min |
| `1` | XS |
| `2` | S |
| `3` | M |
| `5` | L |
| `8` | XL |
| `13` | XXL |

### Helper Methods

| Method | Description |
|---|---|
| `leantime.rpc.tickets.getStatusLabels` | Get status codes for a project |
| `leantime.rpc.tickets.getTicketTypes` | Returns `["task","subtask","story","bug"]` |
| `leantime.rpc.tickets.getPriorityLabels` | Returns priority map |
| `leantime.rpc.tickets.getEffortLabels` | Returns effort/storypoint map |
| `leantime.rpc.tickets.getTypeIcons` | Returns type-to-icon map |
| `leantime.rpc.tickets.getKanbanColumns` | Returns visible kanban columns |

---

## 5. Milestones

**Milestones are tickets with `type = "milestone"`.** There is no separate milestones
table or domain. They live in `zp_tickets`.

### `leantime.rpc.tickets.quickAddMilestone`

| Parameter | Type | Required | Default | Notes |
|---|---|---|---|---|
| `headline` | string | **YES** | -- | Milestone name |
| `projectId` | int | no | session | |
| `editorId` | int | no | session user | |
| `dependentMilestone` | int | no | `""` | Parent milestone (sets `milestoneid`) |
| `tags` | string | no | `""` | Color tag for the milestone |
| `editFrom` | string | no | `""` | Start date |
| `editTo` | string | no | `""` | End date |

Returns the new ticket/milestone ID.

### `leantime.rpc.tickets.quickUpdateMilestone`

| Parameter | Type | Required |
|---|---|---|
| `id` | int | YES |
| `headline` | string | YES |
| `editorId` | int | YES |
| `status` | int | YES |
| `dependentMilestone` | int | YES |
| `tags` | string | YES |
| `editFrom` | string | no |
| `editTo` | string | no |

### `leantime.rpc.tickets.getAllMilestones`

| Parameter | Type | Required |
|---|---|---|
| `searchCriteria` | array | YES |
| `sortBy` | string | no (`"standard"`) |

`searchCriteria` must include `currentProject` > 0.

### `leantime.rpc.tickets.deleteMilestone`

| Parameter | Type | Required |
|---|---|---|
| `id` | int | YES |

### Milestone Dates

Milestones use `editFrom` and `editTo` for their date range on the Gantt chart,
just like regular tickets. The `dateToFinish` is typically left empty for milestones.

### Milestone Colors

The `tags` field on milestones is used as the **color** (CSS color value, e.g.
`"var(--blue)"` or a hex value). When a ticket references a milestone via `milestoneid`,
the milestone color is available as `milestoneColor`.

### Linking Tickets to Milestones

Set `milestoneid` on the ticket to the milestone's ticket ID:

```json
{
    "jsonrpc": "2.0",
    "method": "leantime.rpc.tickets.addTicket",
    "id": 1,
    "params": {
        "headline": "Implement login",
        "projectId": 5,
        "milestoneid": 42
    }
}
```

### Milestone Hierarchy

Milestones can have parent milestones via the `milestoneid` field (on the milestone
ticket itself). This creates a milestone hierarchy.

### Milestone Progress

`leantime.rpc.tickets.getMilestoneProgress` -- returns float (0-100 percentage).

| Parameter | Type | Required |
|---|---|---|
| `milestoneId` | int | YES |

---

## 6. Subtasks

Subtasks are tickets with `type = "subtask"` and `dependingTicketId` set to the
parent ticket's ID.

### `leantime.rpc.tickets.upsertSubtask`

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `values` | array | YES | Subtask data |
| `parentTicket` | object | YES | The parent ticket object (from `getTicket`) |

The `values` array:

| Key | Type | Required | Default |
|---|---|---|---|
| `headline` | string | YES | |
| `description` | string | no | `""` |
| `dateToFinish` | string | no | `""` |
| `priority` | int | no | `3` |
| `status` | int | YES | |
| `storypoints` | string | no | `""` |
| `hourRemaining` | numeric | no | `0` |
| `planHours` | numeric | no | `0` |
| `editFrom` | string | no | `""` |
| `editTo` | string | no | `""` |
| `subtaskId` | string | no | `"new"` | Set to existing ID for update |

**Note:** `upsertSubtask` requires a ticket *object* as the second parameter, not just
an ID. This makes it harder to use via JSON-RPC. For subtask creation via API, it is
simpler to use `addTicket` directly:

```json
{
    "jsonrpc": "2.0",
    "method": "leantime.rpc.tickets.addTicket",
    "id": 1,
    "params": {
        "headline": "Write unit tests",
        "type": "subtask",
        "projectId": 5,
        "dependingTicketId": 100
    }
}
```

This creates a subtask under ticket #100.

---

## 7. Task Dependencies -- CRITICAL SECTION

### How Dependencies Work

Leantime uses a **single field** for dependencies: `dependingTicketId` on the
`zp_tickets` table. This is a single integer foreign key.

**A ticket can have exactly ONE dependency (predecessor).** There is no many-to-many
dependency table. The field represents "this ticket depends on ticket X" (predecessor
relationship).

### Setting Dependencies

When creating a ticket:
```json
{
    "params": {
        "headline": "Deploy to production",
        "dependingTicketId": 55
    }
}
```

This means: ticket "Deploy to production" depends on (comes after) ticket #55.

When updating via patch:
```json
{
    "method": "leantime.rpc.tickets.patch",
    "params": {
        "id": 60,
        "params": { "dependingTicketId": 55 }
    }
}
```

### Limitations

- **Only ONE predecessor per ticket.** There is no mechanism for multiple dependencies.
- The `dependingTicketId` serves dual purpose:
  - For `type = "subtask"`: it means "parent task" (the task this is a subtask of)
  - For other types: it means "predecessor" (Gantt dependency)
- On the Gantt chart, dependency arrows are drawn from `dependingTicketId` -> current ticket.
- Sorting within milestones respects dependency order.

### Workaround for Multiple Dependencies

Since Leantime only supports one predecessor, if you need multiple:
- Chain them linearly: A -> B -> C (B depends on A, C depends on B)
- Use milestones as aggregation points

---

## 8. Users API

### `leantime.rpc.users.users.addUser`

| Parameter | Type | Required | Default | Notes |
|---|---|---|---|---|
| `user` or `username` | string | **YES** | -- | Email address (used as username) |
| `role` | int | **YES** | -- | Role key (see table below) |
| `password` | string | **YES** | -- | Will be hashed with `password_hash()` |
| `firstname` | string | no | `""` | |
| `lastname` | string | no | `""` | |
| `phone` | string | no | `""` | |
| `clientId` | int | no | `""` | Client/org ID |
| `notifications` | int | no | `1` | `1` = receive notifications |
| `source` | string | no | `""` | Auth source (e.g. `"ldap"`) |
| `pwReset` | string | no | `""` | Password reset token |
| `status` | string | no | `""` | `"a"` = active, `"i"` = inactive |
| `createdOn` | string | no | `""` | Date string |
| `jobTitle` | string | no | `""` | |
| `jobLevel` | string | no | `""` | |
| `department` | string | no | `""` | |

Returns the new user ID.

### User Roles

| Key | Role Name | Legacy Name |
|---|---|---|
| `5` | readonly | none |
| `10` | commenter | client |
| `20` | editor | developer |
| `30` | manager | clientmanager |
| `40` | admin | manager |
| `50` | owner | admin |

### `leantime.rpc.users.users.getAll`

| Parameter | Type | Default |
|---|---|---|
| `activeOnly` | bool | `false` |

### `leantime.rpc.users.users.getUser`

| Parameter | Type | Required |
|---|---|---|
| `id` | int | YES |

### `leantime.rpc.users.users.editUser`

| Parameter | Type | Required |
|---|---|---|
| `values` | array | YES |
| `id` | int | YES |

### `leantime.rpc.users.users.getUserByEmail`

| Parameter | Type | Required |
|---|---|---|
| `email` | string | YES |
| `status` | string | `"a"` |

### `leantime.rpc.users.users.usernameExist`

| Parameter | Type | Required |
|---|---|---|
| `username` | string | YES |

### Assigning Users to Tickets

The `editorId` field on a ticket is the primary assignee. Set it when creating or
updating a ticket:

```json
{
    "method": "leantime.rpc.tickets.addTicket",
    "params": {
        "headline": "Fix bug #123",
        "editorId": 7,
        "projectId": 5
    }
}
```

**Important:** `editorId` is stored as a string in the database, and the JOIN uses
a CAST. The value can be a user ID integer.

For multiple assignees, use the `collaborators` field (array of user IDs) available
in `addTicket` and `updateTicket`.

### Assigning Users to Projects

Use `assignedUsers` in `addProject`:
```json
{
    "params": {
        "name": "My Project",
        "clientId": 1,
        "assignedUsers": [
            { "id": 3, "projectRole": "" },
            { "id": 5, "projectRole": "20" }
        ]
    }
}
```

---

## 9. Clients API

### `leantime.rpc.clients.clients.create`

| Parameter | Type | Required | Default |
|---|---|---|---|
| `name` | string | **YES** | -- |
| `street` | string | no | `""` |
| `zip` | string | no | `""` |
| `city` | string | no | `""` |
| `state` | string | no | `""` |
| `country` | string | no | `""` |
| `phone` | string | no | `""` |
| `internet` | string | no | `""` |
| `email` | string | no | `""` |

Returns client ID (string).

### `leantime.rpc.clients.clients.get`

| Parameter | Type | Required |
|---|---|---|
| `id` | int | YES |

### `leantime.rpc.clients.clients.getAll`

| Parameter | Type | Default |
|---|---|---|
| `searchparams` | array | `null` |

### `leantime.rpc.clients.clients.patch`

| Parameter | Type | Required |
|---|---|---|
| `id` | int | YES |
| `params` | array | YES |

### `leantime.rpc.clients.clients.delete`

| Parameter | Type | Required |
|---|---|---|
| `id` | int | YES |

---

## 10. Sprints API

### `leantime.rpc.sprints.sprints.addSprint`

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `name` | string | YES | Sprint name |
| `startDate` | string | YES | Start date |
| `endDate` | string | YES | End date |
| `projectId` | int | no | Defaults to session project |

Returns the new sprint ID (int).

All parameters are passed as a single `$params` array -- specify them directly in
the `params` object of the JSON-RPC request.

### `leantime.rpc.sprints.sprints.editSprint`

Same parameters as `addSprint` plus `id`.

### `leantime.rpc.sprints.sprints.getSprint`

| Parameter | Type | Required |
|---|---|---|
| `id` | int | YES |

### `leantime.rpc.sprints.sprints.getAllSprints`

| Parameter | Type | Default |
|---|---|---|
| `projectId` | int | `null` (session) |

### `leantime.rpc.sprints.sprints.getCurrentSprintId`

| Parameter | Type | Required |
|---|---|---|
| `projectId` | int | YES |

### Linking Tickets to Sprints

Set the `sprint` field on a ticket to the sprint ID:

```json
{
    "method": "leantime.rpc.tickets.addTicket",
    "params": {
        "headline": "Task in sprint",
        "sprint": 3,
        "projectId": 5
    }
}
```

---

## 11. Comments API

### `leantime.rpc.comments.comments.addComment`

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `values` | array | YES | `{"text": "...", "father": 0}` |
| `module` | string | YES | `"ticket"`, `"project"`, or other module name |
| `entityId` | int | YES | ID of the entity (ticket ID, project ID, etc.) |
| `entity` | object | YES | The entity object itself |

The `values` array:

| Key | Type | Required | Notes |
|---|---|---|---|
| `text` | string | YES | Comment body (HTML supported) |
| `father` | int | YES | Parent comment ID (`0` for top-level) |
| `status` | string | no | Optional status |

**Important:** The `entity` parameter requires the actual entity object (e.g., a
Ticket model). This makes direct JSON-RPC usage complex. You would need to pass
the entity's data as a serializable structure. For ticket comments:

```json
{
    "method": "leantime.rpc.comments.comments.addComment",
    "params": {
        "values": {
            "text": "This looks good!",
            "father": 0
        },
        "module": "ticket",
        "entityId": 42,
        "entity": {
            "id": 42,
            "headline": "Fix login",
            "type": "task"
        }
    }
}
```

### `leantime.rpc.comments.comments.getComments`

| Parameter | Type | Required | Default |
|---|---|---|---|
| `module` | string | YES | |
| `entityId` | int | YES | |
| `commentOrder` | int | no | `0` |
| `parent` | int | no | `0` |

### `leantime.rpc.comments.comments.editComment`

| Parameter | Type | Required |
|---|---|---|
| `values` | array | YES (`{"text": "..."}`) |
| `id` | int | YES |

### `leantime.rpc.comments.comments.deleteComment`

| Parameter | Type | Required |
|---|---|---|
| `commentId` | int | YES |

---

## 12. Timesheets API

### `leantime.rpc.timesheets.timesheets.logTime`

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `ticketId` | int | YES | Ticket to log time against |
| `params` | array | YES | Time entry details |

The `params` array:

| Key | Type | Required | Notes |
|---|---|---|---|
| `hours` | numeric | YES | Number of hours |
| `kind` | string | YES | Timesheet type (e.g. `"general"`) |
| `date` | string | conditional | Date string (user format) |
| `time` | string | no | Time string (used with `date`) |
| `dateString` | string | conditional | Alternative date format |
| `timestamp` | int | conditional | Unix timestamp |
| `description` | string | no | Description of work |
| `userId` | int | no | Defaults to session user |

One of `date`, `dateString`, or `timestamp` is required.

### `leantime.rpc.timesheets.timesheets.upsertTime`

Same parameters as `logTime`. Updates existing entry if found for the same
ticket + user + date, otherwise creates new.

### `leantime.rpc.timesheets.timesheets.getLoggedHoursForTicketByDate`

| Parameter | Type | Required |
|---|---|---|
| `ticketId` | int | YES |

### `leantime.rpc.timesheets.timesheets.getSumLoggedHoursForTicket`

| Parameter | Type | Required |
|---|---|---|
| `ticketId` | int | YES |

### `leantime.rpc.timesheets.timesheets.punchIn`

| Parameter | Type | Required |
|---|---|---|
| `ticketId` | int | YES |

### `leantime.rpc.timesheets.timesheets.punchOut`

| Parameter | Type | Required |
|---|---|---|
| `ticketId` | int | YES |

### `leantime.rpc.timesheets.timesheets.getLoggableHourTypes`

No parameters. Returns the configured hour types.

### `leantime.rpc.timesheets.timesheets.deleteTime`

| Parameter | Type | Required |
|---|---|---|
| `id` | int | YES |

---

## 13. Tags / Labels

Tags are **plain comma-separated strings** stored in the `tags` column of `zp_tickets`.

```json
{
    "tags": "backend,frontend,urgent"
}
```

There is no separate tags table or tags API. Tags are simply string values.
When reading tickets, `tags` comes back as a string you must split on commas.

For milestones, the `tags` field is repurposed as the **color** value (e.g., a CSS
color or variable like `"var(--blue)"`).

---

## 14. Status Labels

### Default Statuses (Repeated for Convenience)

```python
DEFAULT_STATUSES = {
    3:  {"name": "New",                    "type": "NEW",        "kanban": True,  "sort": 1},
    1:  {"name": "Blocked",                "type": "INPROGRESS", "kanban": True,  "sort": 2},
    4:  {"name": "In Progress",            "type": "INPROGRESS", "kanban": True,  "sort": 3},
    2:  {"name": "Waiting for Approval",   "type": "INPROGRESS", "kanban": True,  "sort": 4},
    0:  {"name": "Done",                   "type": "DONE",       "kanban": True,  "sort": 5},
    -1: {"name": "Archived",               "type": "DONE",       "kanban": False, "sort": 6},
}
```

### Custom Statuses per Project

Statuses can be fully customized per project. Use:

```
leantime.rpc.tickets.getStatusLabels
params: { "projectId": 5 }
```

To SAVE custom statuses:

```
leantime.rpc.tickets.saveStatusLabels
params: {
    "params": {
        "labelKeys": [3, 1, 4, 2, 0, -1],
        "label-3": "To Do",
        "labelClass-3": "label-info",
        "labelType-3": "NEW",
        "labelKanbanCol-3": true,
        "labelSort-3": 1,
        ...
    }
}
```

### Status Type Classification

When querying, `status = "not_done"` means all statuses where statusType != "DONE".

---

## 15. Canvas / Lean Features

Leantime includes several canvas/board features. These have limited API exposure:

### Goal Canvas

- `leantime.rpc.goalcanvas.goalcanvas.getCanvasItemsById`
- `leantime.rpc.goalcanvas.goalcanvas.createGoalboard`
- `leantime.rpc.goalcanvas.goalcanvas.createGoal`
- `leantime.rpc.goalcanvas.goalcanvas.pollGoals`
- `leantime.rpc.goalcanvas.goalcanvas.getParentKPIs`

### Ideas

- `leantime.rpc.ideas.ideas.pollForNewIdeas`
- `leantime.rpc.ideas.ideas.pollForUpdatedIdeas`

### Other Domains (limited or no `@api` methods)

The codebase includes these domains, but many lack public `@api`-tagged service methods:

- **Leancanvas** (Lean Canvas boards)
- **Retroscanvas** / **Retrospectives** (retrospective boards)
- **Wiki** (documentation/wiki pages)
- **Files** (file attachments)
- **Calendar** (events)
- **Reports** (reporting)
- **Notifications** (notification management)
- **Setting** (system/project settings)
- **Connector** (integrations)

---

## 16. Batch Requests

The JSON-RPC endpoint supports batch requests per the JSON-RPC 2.0 spec. Send an
array of request objects:

```json
[
    {
        "jsonrpc": "2.0",
        "method": "leantime.rpc.tickets.addTicket",
        "id": 1,
        "params": { "headline": "Task 1", "projectId": 5 }
    },
    {
        "jsonrpc": "2.0",
        "method": "leantime.rpc.tickets.addTicket",
        "id": 2,
        "params": { "headline": "Task 2", "projectId": 5 }
    }
]
```

Returns an array of responses. **Note:** batch requests are processed sequentially
(each sub-request calls `executeApiRequest` in a loop), not in parallel.

---

## 17. Practical Import Strategy

### Recommended Import Order

1. **Create Client** (`clients.clients.create`) -- get `clientId`
2. **Create Users** (`users.users.addUser`) -- get user IDs, note the `editorId` mapping
3. **Create Project** (`projects.projects.addProject`) -- use `clientId`, get `projectId`
4. **Assign Users to Project** (via `assignedUsers` in `addProject`, or via `editProject`)
5. **Create Sprints** (`sprints.sprints.addSprint`) -- if using sprints, get sprint IDs
6. **Create Milestones** (`tickets.quickAddMilestone`) -- get milestone IDs
7. **Create Tickets** (`tickets.addTicket`) -- use `projectId`, `milestoneid`, `sprint`, `editorId`, `dependingTicketId`
   - Create tickets **in dependency order**: create predecessors first, then dependents
   - For subtasks: create parent first, then subtask with `type: "subtask"` and `dependingTicketId: parentId`
8. **Add Comments** (`comments.comments.addComment`) -- reference ticket IDs
9. **Log Time** (`timesheets.timesheets.logTime`) -- reference ticket IDs

### Important Gotchas

1. **Session dependency:** Many methods fall back to `session('currentProject')` or
   `session('userdata.id')`. When using the API, ALWAYS explicitly pass `projectId`
   and `userId`/`editorId` -- do not rely on session defaults.

2. **User project access:** The API checks `isUserAssignedToProject`. If the API user
   is not assigned to the target project, ticket creation will fail. Make sure the
   API user (or the user whose key you use) is assigned to all relevant projects.

3. **Date formats:** The service layer uses `dtHelper()->parseUserDateTime()` which
   expects dates in the user's configured format. ISO 8601 (`"2026-01-15"` or
   `"2026-01-15T00:00:00"`) is generally safe.

4. **One dependency per ticket:** You cannot set multiple predecessors. Plan your
   dependency chain accordingly.

5. **Milestones are tickets:** Always remember that milestones live in the tickets table.
   Create them with `quickAddMilestone` or `addTicket` with `type: "milestone"`.

6. **Tags for milestones = colors:** The `tags` field on milestone tickets is used
   for the milestone color display, not as actual tags.

7. **editorId type:** The `editorId` is stored as text and JOINed via CAST. Pass it
   as an integer or string representation of the user ID.

### Example: Complete Ticket Creation

```json
{
    "jsonrpc": "2.0",
    "method": "leantime.rpc.tickets.addTicket",
    "id": 1,
    "params": {
        "headline": "Implement OAuth2 login",
        "type": "story",
        "description": "<p>As a user, I want to log in with Google OAuth2.</p>",
        "projectId": 5,
        "editorId": 7,
        "status": 3,
        "priority": 2,
        "storypoints": "5",
        "planHours": "16",
        "tags": "authentication,backend",
        "dateToFinish": "2026-03-15",
        "editFrom": "2026-02-01",
        "editTo": "2026-03-15",
        "milestoneid": 42,
        "sprint": 3,
        "dependingTicketId": 55,
        "acceptanceCriteria": "<ul><li>Google login works</li><li>Token refresh works</li></ul>"
    }
}
```

### Example: Create Milestone

```json
{
    "jsonrpc": "2.0",
    "method": "leantime.rpc.tickets.quickAddMilestone",
    "id": 2,
    "params": {
        "headline": "MVP Release",
        "projectId": 5,
        "editFrom": "2026-01-01",
        "editTo": "2026-03-31",
        "tags": "#3b82f6"
    }
}
```

### Example: Create Subtask

```json
{
    "jsonrpc": "2.0",
    "method": "leantime.rpc.tickets.addTicket",
    "id": 3,
    "params": {
        "headline": "Write OAuth2 unit tests",
        "type": "subtask",
        "projectId": 5,
        "dependingTicketId": 100,
        "status": 3,
        "editorId": 7
    }
}
```
