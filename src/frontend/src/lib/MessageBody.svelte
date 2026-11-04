<script lang="ts">
	import { stickers } from './stickers';
	import { renderMessage } from './markdown';
	let { content }: { content: string } = $props();
	let sticker = $derived(stickers.find((s) => content === ':sticker:' + s.id + ':'));
</script>

{#if sticker}<img width="112" src={sticker.src} alt={sticker.name} />{:else}<div class="body">
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- parser disables HTML and escapes spoiler text -->
		{@html renderMessage(content)}
	</div>{/if}

<style>
	.body {
		overflow-wrap: anywhere;
	}
	.body :global(pre) {
		overflow: auto;
		background: #222;
		color: white;
		padding: 0.6rem;
	}
	.body :global(summary) {
		cursor: pointer;
	}
	.body :global(a) {
		text-decoration: underline;
	}
</style>
