/**
 * The browser's view of the account routes.
 *
 * Kept apart from `api.ts` because these carry an access token and the spot
 * routes never do: nothing about searching should depend on being logged in.
 */

import { ApiError, isErrorEnvelope, type Fetcher } from './api';
import type { Account, AuthConfig, CompleteSignUp } from './contract';

async function request<T>(path: string, init: RequestInit, fetcher: Fetcher): Promise<T> {
	let response: Response;
	try {
		response = await fetcher(path, {
			...init,
			headers: { accept: 'application/json', ...init.headers }
		});
	} catch {
		throw new ApiError('network_error', 'Could not reach the StudySpot API.', 0);
	}

	let body: unknown;
	try {
		body = await response.json();
	} catch {
		throw new ApiError(
			'invalid_response',
			'The API returned a response that was not JSON.',
			response.status
		);
	}

	if (!response.ok) {
		if (isErrorEnvelope(body)) {
			throw new ApiError(
				body.error.code,
				body.error.message,
				response.status,
				body.error.details ?? []
			);
		}
		throw new ApiError('error', `The API returned ${response.status}.`, response.status);
	}

	return body as T;
}

/** Which Auth0 tenant to log in with, or that accounts are switched off. */
export function fetchAuthConfig(fetcher: Fetcher = globalThis.fetch): Promise<AuthConfig> {
	return request<AuthConfig>('/api/auth/config', {}, fetcher);
}

/**
 * The account behind `token`.
 *
 * The first call after an Auth0 sign-up is also what creates it, so there is
 * no separate registration request to forget.
 */
export function fetchAccount(token: string, fetcher: Fetcher = globalThis.fetch): Promise<Account> {
	return request<Account>(
		'/api/account',
		{ headers: { authorization: `Bearer ${token}` } },
		fetcher
	);
}

/** Finish sign-up by saying which kind of account this is. Allowed once. */
export function completeSignUp(
	token: string,
	choice: CompleteSignUp,
	fetcher: Fetcher = globalThis.fetch
): Promise<Account> {
	return request<Account>(
		'/api/account',
		{
			method: 'POST',
			headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
			body: JSON.stringify(choice)
		},
		fetcher
	);
}

/** How an account is named in the header: the name its owner chose. */
export function displayName(account: Account): string {
	return account.business_name || account.username || account.email;
}
