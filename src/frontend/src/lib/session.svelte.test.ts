/**
 * The session's decisions, with Auth0 and the API both stood in for.
 *
 * Run in the browser project because the module holds runes state, which only
 * compiles in a `.svelte.ts` file.
 */

import { describe, expect, it } from 'vitest';
import type { Account } from './contract';
import { Session, safeReturnTo, type AuthClient } from './session.svelte';

const CONFIG = { enabled: true, domain: 'x.auth0.com', client_id: 'spa', audience: 'api' };

const ACCOUNT: Account = {
	email: 'ada@nyu.edu',
	email_verified: true,
	username: 'ada',
	account_type: 'student',
	business_name: '',
	created_at: '2026-10-27T12:00:00Z'
};

function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'content-type': 'application/json' }
	});
}

type Options = {
	enabled?: boolean;
	authenticated?: boolean;
	account?: Account;
	returnTo?: string;
};

/** A session wired to a fake client, and a log of what was asked of the client. */
function setup({
	enabled = true,
	authenticated = true,
	account = ACCOUNT,
	returnTo
}: Options = {}) {
	const log: { method: string; argument?: unknown }[] = [];

	const client = {
		checkSession: async () => void log.push({ method: 'checkSession' }),
		isAuthenticated: async () => authenticated,
		getTokenSilently: async (argument?: unknown) => {
			log.push({ method: 'getTokenSilently', argument });
			return 'token';
		},
		loginWithRedirect: async (argument?: unknown) =>
			void log.push({ method: 'loginWithRedirect', argument }),
		handleRedirectCallback: async () => ({ appState: { returnTo } }),
		logout: async (argument?: unknown) => void log.push({ method: 'logout', argument })
	} as unknown as AuthClient;

	const fetcher = (async (input: RequestInfo | URL) => {
		if (String(input) === '/api/auth/config') return json(enabled ? CONFIG : { enabled: false });
		return json(account);
	}) as typeof globalThis.fetch;

	const session = new Session({ fetcher, createClient: async () => client });
	return { session, log };
}

describe('start', () => {
	it('is disabled when the API has no Auth0 tenant', async () => {
		const { session, log } = setup({ enabled: false });

		await session.start();

		expect(session.status).toBe('disabled');
		expect(log).toEqual([]);
	});

	it('is signed out without an Auth0 session', async () => {
		const { session } = setup({ authenticated: false });

		await session.start();

		expect(session.status).toBe('signed-out');
		expect(session.account).toBeNull();
	});

	it('loads the account of whoever is logged in', async () => {
		const { session } = setup();

		await session.start();

		expect(session.status).toBe('signed-in');
		expect(session.account).toEqual(ACCOUNT);
	});

	it('only starts once', async () => {
		const { session, log } = setup();

		await Promise.all([session.start(), session.start()]);

		expect(log.filter((entry) => entry.method === 'checkSession')).toHaveLength(1);
	});

	it('leaves the callback page to finish the log-in', async () => {
		const { session, log } = setup();

		await session.start({ callback: true });

		expect(session.status).toBe('loading');
		expect(log).toEqual([]);
	});
});

describe('finishLogIn', () => {
	it('sends a new account to choose its type', async () => {
		const { session } = setup({ account: { ...ACCOUNT, account_type: null }, returnTo: '/spots' });

		expect(await session.finishLogIn()).toBe('/account');
	});

	it('returns an existing account to where it started', async () => {
		const { session } = setup({ returnTo: '/spots/facdb:bobst' });

		expect(await session.finishLogIn()).toBe('/spots/facdb:bobst');
		expect(session.status).toBe('signed-in');
	});

	it('will not return to another site', async () => {
		const { session } = setup({ returnTo: '//evil.example/phish' });

		expect(await session.finishLogIn()).toBe('/');
	});
});

describe('redirects', () => {
	it('logs in, coming back to the page it left', async () => {
		const { session, log } = setup({ authenticated: false });

		await session.logIn('/spots/facdb:bobst');

		expect(log.at(-1)).toEqual({
			method: 'loginWithRedirect',
			argument: { appState: { returnTo: '/spots/facdb:bobst' }, authorizationParams: {} }
		});
	});

	it('opens sign-up rather than log-in', async () => {
		const { session, log } = setup({ authenticated: false });

		await session.signUp();

		expect(log.at(-1)).toMatchObject({
			argument: { authorizationParams: { screen_hint: 'signup' } }
		});
	});

	it('forgets the account on log-out', async () => {
		const { session, log } = setup();
		await session.start();

		await session.logOut();

		expect(session.status).toBe('signed-out');
		expect(session.account).toBeNull();
		expect(log.at(-1)?.method).toBe('logout');
	});
});

describe('refresh', () => {
	it('skips the token cache, so a newly verified email shows', async () => {
		const { session, log } = setup();
		await session.start();

		await session.refresh();

		expect(log.at(-1)).toEqual({ method: 'getTokenSilently', argument: { cacheMode: 'off' } });
	});
});

describe('safeReturnTo', () => {
	it('keeps paths on this site and nothing else', () => {
		expect(safeReturnTo('/account')).toBe('/account');
		expect(safeReturnTo('//evil.example')).toBe('/');
		expect(safeReturnTo('https://evil.example')).toBe('/');
		expect(safeReturnTo(undefined)).toBe('/');
	});
});
