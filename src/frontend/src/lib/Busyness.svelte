<script lang="ts">
	import { busyness } from './busyness';

	let { nearby, label = 'Area' }: { nearby: number; label?: string } = $props();

	const state = $derived(busyness(nearby));
</script>

<!--
	Three encodings of the same thing: the number of footprints, their colour,
	and the word. Colour alone would fail anyone who cannot distinguish these
	three, and the count beside it is what makes the word checkable.
-->
<p class="busyness">
	<span class="key">{label}</span>
	<span class="feet" style:color={state.colour} aria-hidden="true">
		{#each [0, 1, 2] as index (index)}
			<svg viewBox="0 0 16 16" class:dim={index >= state.feet}>
				<path
					d="M8 1.6c2 0 3.2 1.7 3.2 4 0 1.8-.6 3.2-.6 4.6 0 1.3.9 2 .9 3.2 0 1.6-1.4 2.6-3.5 2.6s-3.5-1-3.5-2.6c0-1.2.9-1.9.9-3.2 0-1.4-.6-2.8-.6-4.6 0-2.3 1.2-4 3.2-4Z"
				/>
			</svg>
		{/each}
	</span>
	<span class="word" style:color={state.colour}>{state.label}</span>
	<span class="detail">· {state.detail}</span>
</p>

<style>
	.busyness {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 3px 7px;
		margin: 10px 0 0;
		font-size: 13px;
	}

	.key {
		color: var(--color-muted);
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.feet {
		display: inline-flex;
		gap: 1px;
	}

	.feet svg {
		width: 11px;
		fill: currentColor;
	}

	/* Drawn rather than omitted, so the scale reads as one of three. */
	.feet svg.dim {
		opacity: 0.22;
	}

	.word {
		font-weight: 700;
	}

	.detail {
		color: var(--color-muted);
	}
</style>
