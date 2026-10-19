<script lang="ts">
	import { resolve } from '$app/paths';
	import SearchBar from '$lib/SearchBar.svelte';
	import SpotResults from '$lib/SpotResults.svelte';
	import { ApiError, DEFAULT_LIMIT, searchSpots } from '$lib/api';
	import type { StudySpot } from '$lib/contract';

	type Status = 'idle' | 'searching' | 'loaded' | 'error';

	let status = $state<Status>('idle');
	let query = $state('');
	let spots = $state<StudySpot[]>([]);
	let total = $state(0);
	let hasMore = $state(false);
	let loadingMore = $state(false);
	let errorMessage = $state('');

	// The hero fills the viewport until there is something below it to see.
	let searched = $derived(status !== 'idle');

	/**
	 * Each search is tagged so a slow earlier request cannot overwrite a faster
	 * later one. Typing a second query before the first returns is ordinary
	 * behaviour, and without this the results could end up showing the wrong one.
	 */
	let latestSearch = 0;

	function describe(error: unknown): string {
		if (error instanceof ApiError) {
			// The database being unavailable is worth saying plainly; everything
			// else is reported in the API's own words.
			if (error.code === 'database_unavailable') {
				return 'The study-spot database is unavailable. Try again shortly.';
			}
			if (error.code === 'network_error') {
				return 'Could not reach StudySpot. Check your connection and try again.';
			}
			return error.message;
		}
		return 'Something went wrong while searching.';
	}

	async function handleSearch(submitted: string): Promise<void> {
		const search = ++latestSearch;

		query = submitted;
		status = 'searching';
		errorMessage = '';

		try {
			const page = await searchSpots(submitted, { limit: DEFAULT_LIMIT });
			if (search !== latestSearch) return;

			spots = page.items;
			total = page.pagination.total;
			hasMore = page.pagination.has_more;
			status = 'loaded';
		} catch (error) {
			if (search !== latestSearch) return;

			errorMessage = describe(error);
			spots = [];
			total = 0;
			hasMore = false;
			status = 'error';
		}
	}

	async function handleShowMore(): Promise<void> {
		if (loadingMore) return;
		const search = latestSearch;
		loadingMore = true;

		try {
			const page = await searchSpots(query, { limit: DEFAULT_LIMIT, offset: spots.length });
			if (search !== latestSearch) return;

			spots = [...spots, ...page.items];
			hasMore = page.pagination.has_more;
		} catch (error) {
			if (search !== latestSearch) return;
			errorMessage = describe(error);
		} finally {
			loadingMore = false;
		}
	}
</script>

<svelte:head>
	<title>StudySpot</title>
	<meta
		name="description"
		content="Discover cafés and other NYC third places where students can meet and study."
	/>
</svelte:head>

<div class="page">
	<header>
		<a class="brand" href={resolve('/')} aria-label="StudySpot home">
			<svg viewBox="0 0 32 32" aria-hidden="true">
				<path d="M7 7.5h18v17H7z"></path>
				<path d="M11 12h10M11 16h10M11 20h6"></path>
			</svg>
			<span>StudySpot</span>
		</a>
	</header>

	<main>
		<section class="hero" class:compact={searched} aria-labelledby="hero-title">
			<div class="copy">
				<p class="eyebrow">NYC third places</p>
				<h1 id="hero-title">Find a place to study together.</h1>
				<p class="description">Explore cafés and public gathering places from NYC Open Data.</p>
			</div>

			<SearchBar onSearch={handleSearch} />
		</section>

		<!-- aria-live so a screen reader hears the outcome without moving focus. -->
		<div aria-live="polite">
			{#if status === 'searching'}
				<p class="status">Searching…</p>
			{:else if status === 'error'}
				<p class="status error" role="alert">{errorMessage}</p>
			{:else if status === 'loaded' && spots.length === 0}
				<p class="status">
					No places match <strong>{query}</strong>. Try a library, a campus, or a neighborhood.
				</p>
			{:else if status === 'loaded'}
				<SpotResults {spots} {total} {hasMore} {loadingMore} onShowMore={handleShowMore} />
			{/if}
		</div>
	</main>
</div>

<style>
	.page {
		min-height: 100vh;
		padding: 0 24px 24px;
	}

	header,
	main {
		width: min(1180px, 100%);
		margin: 0 auto;
	}

	header {
		display: flex;
		align-items: center;
		height: 76px;
	}

	.brand {
		display: inline-flex;
		align-items: center;
		gap: 9px;
		color: var(--color-brand);
		font-size: 20px;
		font-weight: 750;
		letter-spacing: -0.04em;
	}

	.brand svg {
		width: 30px;
		height: 30px;
		fill: none;
		stroke: currentColor;
		stroke-linecap: round;
		stroke-linejoin: round;
		stroke-width: 2;
	}

	.hero {
		display: flex;
		min-height: calc(100vh - 100px);
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 48px;
		padding: 72px 48px 128px;
		border-radius: 28px;
		background: #f7f1eb;
		text-align: center;
		transition:
			min-height 240ms ease,
			padding 240ms ease;
	}

	/* Once results exist, the hero stops owning the whole viewport. */
	.hero.compact {
		min-height: 0;
		gap: 32px;
		padding: 48px 48px 56px;
	}

	.hero.compact h1 {
		font-size: clamp(2rem, 4vw, 3rem);
	}

	.hero.compact .description {
		display: none;
	}

	.copy {
		max-width: 760px;
	}

	.eyebrow {
		margin: 0 0 16px;
		color: var(--color-brand-hover);
		font-size: 12px;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}

	h1 {
		margin: 0;
		font-size: clamp(3.2rem, 7vw, 5.75rem);
		font-weight: 750;
		letter-spacing: -0.07em;
		line-height: 0.96;
		transition: font-size 240ms ease;
	}

	.description {
		max-width: 580px;
		margin: 26px auto 0;
		color: var(--color-muted);
		font-size: 17px;
		line-height: 1.6;
	}

	.status {
		margin: 0;
		padding: 40px 0;
		color: var(--color-muted);
		font-size: 15px;
		text-align: center;
	}

	.status.error {
		color: var(--color-brand-hover);
		font-weight: 600;
	}

	.status strong {
		color: var(--color-text);
	}

	@media (max-width: 560px) {
		.page {
			padding: 0 15px 15px;
		}

		.hero {
			min-height: calc(100vh - 91px);
			gap: 36px;
			padding: 56px 16px;
			border-radius: 20px;
		}

		.hero.compact {
			min-height: 0;
			padding: 36px 16px 40px;
		}
	}
</style>
