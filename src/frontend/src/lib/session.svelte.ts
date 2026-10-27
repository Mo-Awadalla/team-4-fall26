/**
 * Who is logged in, shared by every page.
 *
 * Auth0 does the logging in: its hosted page takes the email, the password, the
 * sign-up and the password reset, and hands back an access token. This module
 * keeps that token's account in reactive state so the header and the account
 * page agree, and is the one place that talks to the Auth0 SDK.
 *
 * Pages are prerendered, so none of this runs until the browser does. The
 * layout calls `start()` on mount; everything rendered before then sees
 * `status === 'loading'`.
 */

import type { Auth0Client } from '@auth0/auth0-spa-js';
import { ApiError, type Fetcher } from './api';
import { completeSignUp, fetchAccount, fetchAuthConfig } from './accounts';
import type { Account, AuthConfig, CompleteSignUp } from './contract';

export type SessionStatus = 'loading' | 'disabled' | 'signed-out' | 'signed-in' | 'error';

/** The part of the Auth0 client this module uses, so tests can stand in for it. */
export type AuthClient = Pick<
	Auth0Client,
	| 'checkSession'
	| 'isAuthenticated'
	| 'getTokenSilently'
	| 'loginWithRedirect'
	| 'handleRedirectCallback'
	| 'logout'
>;

type Enabled = Extract<AuthConfig, { enabled: true }>;

export type SessionDependencies = {
	fetcher?: Fetcher;
	createClient?: (config: Enabled) => Promise<AuthClient>;
};

/** Where Auth0 sends the browser back to, which must be listed in its settings. */
export const CALLBACK_PATH = '/callback';

/**
 * The real client, loaded only when accounts are switched on.
 *
 * The token cache lives in localStorage with refresh tokens rather than in
 * memory with a hidden iframe: the iframe needs Auth0's third-party cookie,
 * which Safari and Firefox block, and without it every reload would log the
 * person out.
 */
async function auth0Client(config: Enabled): Promise<AuthClient> {
	const { Auth0Client } = await import('@auth0/auth0-spa-js');
	return new Auth0Client({
		domain: config.domain,
		clientId: config.client_id,
		authorizationParams: {
			audience: config.audience,
			redirect_uri: `${window.location.origin}${CALLBACK_PATH}`
		},
		cacheLocation: 'localstorage',
		useRefreshTokens: true
	});
}

/**
 * A path on this site to come back to, or the homepage.
 *
 * `returnTo` travels through Auth0 and back, so it is checked on the way in:
 * `//elsewhere.example` is a path to a browser and a different site to a person.
 */
export function safeReturnTo(value: unknown): string {
	if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return '/';
	return value;
}

function describe(error: unknown): string {
	if (error instanceof ApiError) {
		if (error.code === 'network_error') {
			return 'Could not reach StudySpot. Check your connection and try again.';
		}
		return error.message;
	}
	return 'Something went wrong while logging in.';
}

/** Auth0 reports a session that has ended by refusing a token with these. */
function isLoggedOut(error: unknown): boolean {
	if (error instanceof ApiError) return error.status === 401;
	const code = (error as { error?: unknown } | null)?.error;
	return code === 'login_required' || code === 'missing_refresh_token' || code === 'invalid_grant';
}

export class Session {
	status = $state<SessionStatus>('loading');
	account = $state<Account | null>(null);
	error = $state('');

	#fetcher: Fetcher;
	#createClient: (config: Enabled) => Promise<AuthClient>;
	#client: AuthClient | null = null;
	#started: Promise<void> | null = null;

	constructor(dependencies: SessionDependencies = {}) {
		this.#fetcher = dependencies.fetcher ?? ((...args) => globalThis.fetch(...args));
		this.#createClient = dependencies.createClient ?? auth0Client;
	}

	/**
	 * Find out who is logged in. Safe to call more than once; only the first
	 * call does anything.
	 *
	 * `callback` is set on the page Auth0 redirects back to, which finishes the
	 * log-in itself with `finishLogIn()` rather than asking about a session that
	 * does not exist yet.
	 */
	start({ callback = false }: { callback?: boolean } = {}): Promise<void> {
		this.#started ??= this.#start(callback);
		return this.#started;
	}

	async #start(callback: boolean): Promise<void> {
		try {
			const config = await fetchAuthConfig(this.#fetcher);
			if (!config.enabled) {
				this.status = 'disabled';
				return;
			}

			this.#client = await this.#createClient(config);
			if (callback) return;

			// Renews the cached tokens if they have lapsed. It never throws: no
			// session is an answer, not an error.
			await this.#client.checkSession();
			if (await this.#client.isAuthenticated()) {
				await this.#loadAccount();
			} else {
				this.status = 'signed-out';
			}
		} catch (error) {
			this.#fail(error);
		}
	}

	/**
	 * Complete the redirect back from Auth0, and say where to go next.
	 *
	 * A new account goes to the account page to choose student or business;
	 * anyone else returns to wherever they started logging in from.
	 */
	async finishLogIn(): Promise<string> {
		await this.start({ callback: true });
		const client = this.#client;
		if (!client) return '/';

		try {
			const { appState } = await client.handleRedirectCallback<{ returnTo?: string }>();
			await this.#loadAccount();
			if (this.account && this.account.account_type === null) return '/account';
			return safeReturnTo(appState?.returnTo);
		} catch (error) {
			this.#fail(error);
			return '/account';
		}
	}

	/** Go to Auth0's log-in page, coming back to `returnTo` afterwards. */
	async logIn(returnTo = '/'): Promise<void> {
		await this.#redirect(returnTo, {});
	}

	/** Go to Auth0's sign-up page, which then comes back to finish here. */
	async signUp(returnTo = '/account'): Promise<void> {
		await this.#redirect(returnTo, { screen_hint: 'signup' });
	}

	async logOut(): Promise<void> {
		const client = this.#client;
		if (!client) return;
		this.account = null;
		this.status = 'signed-out';
		await client.logout({ logoutParams: { returnTo: window.location.origin } });
	}

	/**
	 * Reload the account from a brand-new token.
	 *
	 * Verifying an email happens in another tab, and the cached token still says
	 * it is unverified, so this skips the cache to see the change.
	 */
	async refresh(): Promise<void> {
		try {
			await this.#loadAccount(true);
		} catch (error) {
			this.#fail(error);
		}
	}

	/** Choose student or business. Validation errors are thrown to the form. */
	async completeSignUp(choice: CompleteSignUp): Promise<Account> {
		const account = await completeSignUp(await this.#token(), choice, this.#fetcher);
		this.account = account;
		return account;
	}

	async #redirect(returnTo: string, authorizationParams: Record<string, string>): Promise<void> {
		await this.start();
		if (!this.#client) return;
		await this.#client.loginWithRedirect({
			appState: { returnTo: safeReturnTo(returnTo) },
			authorizationParams
		});
	}

	async #token(fresh = false): Promise<string> {
		const token = fresh
			? await this.#client?.getTokenSilently({ cacheMode: 'off' })
			: await this.#client?.getTokenSilently();
		// The SDK's types allow for no token at all; that is being logged out.
		if (!token) throw new ApiError('unauthorized', 'You are not logged in.', 401);
		return token;
	}

	async #loadAccount(fresh = false): Promise<void> {
		try {
			this.account = await fetchAccount(await this.#token(fresh), this.#fetcher);
			this.status = 'signed-in';
			this.error = '';
		} catch (error) {
			if (!isLoggedOut(error)) throw error;
			this.account = null;
			this.status = 'signed-out';
		}
	}

	#fail(error: unknown): void {
		this.error = describe(error);
		this.status = 'error';
	}
}

/** The session every page shares. */
export const session = new Session();
