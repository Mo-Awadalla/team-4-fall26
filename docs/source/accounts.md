# Accounts

Students and business owners can sign up, verify their email, log in, log out and reset a forgotten password. [Auth0](https://auth0.com) handles all of that on its own hosted pages. StudySpot keeps an `Account` row per person, recording whether they are a student or a business owner.

Accounts are optional for running the site. With no Auth0 settings, `GET /auth/config` reports `{"enabled": false}`, the header shows no log-in controls, and search works exactly as before.

## How it fits together

```text
Browser ──(1) log in / sign up / reset password──▶ Auth0 hosted page
   ◀──(2) redirect to /callback with a one-time code─┘
   │
   ├──(3) exchange code for an access token (Auth0 SPA SDK)
   │
   └──(4) GET /api/account   Authorization: Bearer <token> ──▶ Django
                                   verifies the RS256 signature against the
                                   tenant's public keys; no call to Auth0
```

The API never calls Auth0 at request time. It verifies each token's signature against the tenant's public keys (JWKS), its issuer, its audience and its expiry. The deployed API has no route to the internet (see `infra/terraform/network.tf`), so Terraform passes those public keys in as `AUTH0_JWKS`. Locally, leave `AUTH0_JWKS` blank and the API fetches them.

The first `GET /account` after a sign-up creates the account. Its `account_type` stays `null` until the person finishes sign-up on `/account`:

- **Student:** needs a verified email at a university domain (anything ending in `.edu` by default; set `STUDENT_EMAIL_DOMAINS` to change it) and a username.
- **Business:** needs a verified email and a business name.

The choice is made once.

## Setting up Auth0

Auth0's free plan covers this project. Do this once per team; everyone shares the tenant.

1. **Create a tenant** at <https://manage.auth0.com>. Its domain looks like `studyspot.us.auth0.com`.

2. **Create an API** (Applications → APIs → Create API).
   - Identifier: `https://api.studyspot.app`. This becomes `AUTH0_AUDIENCE`; it does not need to resolve.
   - Signing algorithm: RS256.
   - Under its settings, turn on **Allow Offline Access**, so the browser gets refresh tokens.

3. **Create an application** (Applications → Create Application → *Single Page Web Applications*). Its Client ID becomes `AUTH0_CLIENT_ID`. Under Settings, list both the local and the deployed origin:

   | Setting | Value |
   |---|---|
   | Allowed Callback URLs | `http://localhost:7500/callback, https://d1ulyrfyi06kwp.cloudfront.net/callback` |
   | Allowed Logout URLs | `http://localhost:7500, https://d1ulyrfyi06kwp.cloudfront.net` |
   | Allowed Web Origins | `http://localhost:7500, https://d1ulyrfyi06kwp.cloudfront.net` |
   | Allowed Origins (CORS) | the same two origins |
   | Refresh Token Rotation | on |

4. **Configure the database connection** (Authentication → Database → Username-Password-Authentication).
   - Turn on **Requires Username**, so students can log in with a username as well as an email.
   - Enable the connection for the application from step 3.
   - Auth0 sends verification and password-reset emails from this connection. The built-in email provider is rate-limited and meant for testing, which is fine for a demo. Connect a real provider under Branding → Email Provider before real users arrive.

5. **Add the claims Action** (Actions → Library → Create Action → *Login / Post Login*). An Auth0 access token leaves out the email by default, and the API needs the email, whether it is verified, and the username:

   ```js
   exports.onExecutePostLogin = async (event, api) => {
   	const namespace = 'https://studyspot.app/';
   	api.accessToken.setCustomClaim(`${namespace}email`, event.user.email ?? '');
   	api.accessToken.setCustomClaim(`${namespace}email_verified`, event.user.email_verified === true);
   	api.accessToken.setCustomClaim(`${namespace}username`, event.user.username ?? '');
   };
   ```

   Deploy it, then add it to the Login flow (Actions → Triggers → post-login). The namespace must match `AUTH0_CLAIM_NAMESPACE`, which defaults to the value above.

## Configuration

| Variable | Where | Meaning |
|---|---|---|
| `AUTH0_DOMAIN` | API | The tenant domain. Blank switches accounts off. |
| `AUTH0_CLIENT_ID` | API | The SPA's Client ID. Public: the browser reads it from `GET /auth/config`. |
| `AUTH0_AUDIENCE` | API | The API identifier from step 2. |
| `AUTH0_JWKS` | API | The JSON from `https://<domain>/.well-known/jwks.json`. Required when deployed; optional locally. |
| `AUTH0_CLAIM_NAMESPACE` | API | Prefix of the Action's claims. Defaults to `https://studyspot.app/`. |
| `STUDENT_EMAIL_DOMAINS` | API | Comma-separated domain suffixes a student email may end in. Defaults to `edu`. |

The frontend build needs none of these: it asks the API at runtime. Locally, put them in `.env`; `docker compose` and `just dev-backend` both read it. For a deployment, set `auth0_domain`, `auth0_client_id`, `auth0_audience` and `auth0_jwks` in `infra/terraform/terraform.tfvars`:

```shell
curl -s https://studyspot.us.auth0.com/.well-known/jwks.json
```

Auth0 changes these keys only when someone rotates the signing key in the dashboard. If that happens, re-apply with the new document, or every log-in will be refused with a 401.

## Routes

### `GET /auth/config`

Public. Returns either `{"enabled": false}`, or:

```json
{
  "enabled": true,
  "domain": "studyspot.us.auth0.com",
  "client_id": "abc123",
  "audience": "https://api.studyspot.app"
}
```

### `GET /account`

Needs `Authorization: Bearer <access token>`. Creates the account on first use, and copies the email, its verification and the username from the token each time.

```json
{
  "email": "ada@nyu.edu",
  "email_verified": true,
  "username": "ada",
  "account_type": null,
  "business_name": "",
  "created_at": "2026-10-27T12:00:00-04:00"
}
```

### `POST /account`

Needs a bearer token. Finishes sign-up, once:

```json
{ "account_type": "student" }
```

```json
{ "account_type": "business", "business_name": "Grumpy Coffee" }
```

Returns the account with `201`. Possible errors:

- `401` without a valid token.
- `409 conflict` when sign-up is already finished.
- `422 validation_error` with one of these in `details`:

| `field` | `type` | Meaning |
|---|---|---|
| `body.email` | `email_unverified` | Auth0 has not verified the address yet. |
| `body.email` | `not_a_student_email` | A student account needs a university address. |
| `body.username` | `required` | A student account needs a username. |
| `body.business_name` | `required` | A business account needs a name. |

## Not yet built

These parts of the accounts epic are still to come:

- Editing a student profile (university, courses, subjects).
- Choosing which profile fields other students can see.
- Editing a business profile (contact email, phone number).

Each will add fields to `Account` or a model beside it. Logging in will not change.
