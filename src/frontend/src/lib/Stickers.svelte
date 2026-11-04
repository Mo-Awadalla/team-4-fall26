<script lang="ts">
	import { stickers } from './stickers';
	let { onpick }: { onpick: (text: string) => void } = $props();
</script>

<details>
	<summary>Stickers</summary>
	{#each stickers as sticker (sticker.id)}<button
			type="button"
			onclick={() => onpick(':sticker:' + sticker.id + ':')}
			><img src={sticker.src} alt={sticker.name} /></button
		>{/each}
</details>

<style>
	img {
		width: 3rem;
	}
	details {
		display: inline-block;
	}
</style>
