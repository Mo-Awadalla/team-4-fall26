# Communities

The static `/communities` page discovers public groups through the Django API. Anyone can create a community without signing in. A group has an owner, members, text-channel names, optional school and course, and shareable invitations. Channel discussions, direct messages, live delivery, and message search are deferred.

All community paths have no trailing slash. Public `GET /communities?q=&limit=&offset=`, `GET /communities/{id}`, `GET /communities/{id}/members`, and `GET /communities/{id}/channels` need no account. The list returns `{items, has_more}` with a default page size of 20 and maximum of 50. `mine=true` shows account memberships and communities owned in this browser session.

Community creation and management use browser sessions for guest owners and Auth0 bearer tokens for signed-in accounts. The public list request sets a CSRF cookie; guest writes send it back. Visitors own up to five communities through their browser session. Clearing site cookies loses guest management access; a future claim flow can transfer guest communities to an account before that happens. Guest communities have no account owner or initial member; their owner can manage channels, invitations and moderation through the same permissions policy. Auth0 authentication supplies `request.user` for account actions; foreign keys use `settings.AUTH_USER_MODEL`. StudySpot admins must be marked `is_staff` by that implementation. No client-supplied actor or role is trusted. Local development can use `python manage.py createsuperuser` and sign in at `http://localhost:7501/admin/` for Django session-based account-only actions.

| Route | Method | Rule |
|---|---|---|
| `/communities` | POST | Create a group and `general` channel; account owners also get a membership. |
| `/communities/{id}` | PATCH, DELETE | Owner edits or deletes. |
| `/communities/{id}/join`, `/leave` | POST | Join once or leave; owners transfer first. |
| `/communities/{id}/members/{user_id}` | PATCH, DELETE | Owner appoints moderators; owner or moderator kicks eligible members. |
| `/communities/{id}/transfer` | POST | Owner transfers to a current member. |
| `/communities/{id}/channels` | POST | Owner creates a channel. |
| `/communities/{id}/channels/{channel_id}` | PATCH | Owner renames, reorders, archives or restores a channel. |
| `/communities/{id}/invites` | GET, POST | Owner or moderator lists or creates links. |
| `/communities/{id}/invites/{invite_id}` | DELETE | Owner or moderator revokes a link. |
| `/communities/invites/{token}/redeem` | POST | Join through a valid link. |
| `/communities/{id}/moderation` | GET, POST | Owner or moderator reads events and bans, or kicks, bans and unbans. |
| `/communities/{id}/admin` | DELETE | StudySpot admin removes a group. |

The owner is stored on the community; membership records store `member` or `moderator`. A moderator cannot act against an owner or another moderator. A ban prevents joining, including through an invite, while public content remains readable. Invitation tokens are returned once at creation; only their SHA-256 hashes are stored. A maximum-use link increments only for a newly joined user.

The current limits are five owned and 100 joined communities per account, 1,000 members, 20 channels and ten active invites per community. Channel names are lowercase letters, digits and hyphens. Invites may expire after one to 720 hours and may cap successful joins at 1,000. These limits live in `communities/services.py` and serializers.

Community creation, membership changes, invite redemption, moderation, and ownership transfers use database transactions. The account implementation should choose its `AUTH_USER_MODEL` before applying these migrations. Owners must transfer or delete their communities before account deletion. Other account deletion does not depend on historical invite or moderation actor rows.

On AWS, session-authenticated writes require the public CloudFront origin in Terraform's `django_csrf_trusted_origins`. The distribution domain is known only after the first apply, so set this variable to its printed `https://...cloudfront.net` origin before enabling community writes. The current deployment has no account flow or session UI; this step belongs to the account integration.
