<script lang="ts">
	import type { StudySpot } from './contract';

	type Props = {
		spots: StudySpot[];
		total: number;
		hasMore: boolean;
		loadingMore?: boolean;
		onShowMore?: () => void;
	};

	let { spots, total, hasMore, loadingMore = false, onShowMore }: Props = $props();

	/**
	 * The importer's vocabulary is snake_case (`academic_library`), because the
	 * category belongs to the data rather than to the interface. Presenting it
	 * is this component's job, not the API's.
	 */
	function readableCategory(category: string): string {
		const words = category.replace(/_/g, ' ');
		return words.charAt(0).toUpperCase() + words.slice(1);
	}

	/**
	 * Neighborhood is absent for some records and borough never is, so the two
	 * are joined only when both exist rather than leaving a stray separator.
	 */
	function place(spot: StudySpot): string {
		return spot.neighborhood ? `${spot.neighborhood}, ${spot.borough}` : spot.borough;
	}
</script>

<section aria-label="Search results">
	<p class="count">
		{#if total === spots.length}
			{total} {total === 1 ? 'place' : 'places'}
		{:else}
			Showing {spots.length} of {total} places
		{/if}
	</p>

	<ul>
		{#each spots as spot (spot.id)}
			<li>
				<h3>{spot.name}</h3>
				<p class="meta">
					<span class="category">{readableCategory(spot.category)}</span>
					<span aria-hidden="true">·</span>
					<span>{place(spot)}</span>
				</p>
				{#if spot.address}
					<p class="address">{spot.address}</p>
				{/if}
				{#if spot.university}
					<!-- Proximity, never affiliation: see the contract. -->
					<p class="campus">Near {spot.university}</p>
				{/if}
			</li>
		{/each}
	</ul>

	{#if hasMore}
		<button type="button" onclick={() => onShowMore?.()} disabled={loadingMore}>
			{loadingMore ? 'Loading…' : 'Show more'}
		</button>
	{/if}
</section>

<style>
	section {
		width: min(1180px, 100%);
		margin: 0 auto;
		padding: 40px 0 72px;
		text-align: left;
	}

	.count {
		margin: 0 0 20px;
		color: var(--color-muted);
		font-size: 14px;
		font-weight: 600;
	}

	ul {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
		gap: 16px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	li {
		padding: 20px;
		border: 1px solid var(--color-border);
		border-radius: 18px;
		background: white;
	}

	h3 {
		margin: 0 0 8px;
		font-size: 17px;
		font-weight: 700;
		letter-spacing: -0.02em;
		line-height: 1.3;
	}

	.meta {
		display: flex;
		flex-wrap: wrap;
		gap: 7px;
		margin: 0;
		color: var(--color-muted);
		font-size: 13px;
	}

	.category {
		color: var(--color-brand-hover);
		font-weight: 650;
	}

	.address,
	.campus {
		margin: 10px 0 0;
		color: var(--color-muted);
		font-size: 13px;
		line-height: 1.5;
	}

	.campus {
		font-style: italic;
	}

	button {
		display: block;
		min-height: 48px;
		margin: 28px auto 0;
		padding: 0 28px;
		border: 1px solid var(--color-border);
		border-radius: 12px;
		background: white;
		font-size: 15px;
		font-weight: 650;
		cursor: pointer;
		transition: border-color 160ms ease;
	}

	button:hover:not(:disabled) {
		border-color: var(--color-text);
	}

	button:disabled {
		color: var(--color-muted);
		cursor: progress;
	}

	@media (max-width: 560px) {
		ul {
			grid-template-columns: 1fr;
		}
	}
</style>
