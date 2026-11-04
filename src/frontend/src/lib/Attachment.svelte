<script lang="ts">
	import { communityRequest } from './communities';
	import { onDestroy } from 'svelte';
	let { url, name }: { url: string; name: string } = $props();
	let source = $state(''),
		error = $state(''),
		loading = $state(false);
	let kind = $derived(
		/\.(png|jpe?g|gif|webp)$/i.test(name) ? 'image' : /\.(mp4|webm)$/i.test(name) ? 'video' : 'file'
	);
	async function load() {
		loading = true;
		try {
			const { data } = await communityRequest<{ data: string }>(url + '?attachment=1');
			const bytes = Uint8Array.from(atob(data), (ch) => ch.charCodeAt(0));
			source = URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' }));
		} catch (e) {
			error = e instanceof Error ? e.message : 'Download failed';
		} finally {
			loading = false;
		}
	}
	onDestroy(() => {
		if (source) URL.revokeObjectURL(source);
	});
</script>

{#if source}
	{#if kind === 'image'}<img src={source} alt={name} />{:else if kind === 'video'}<video
			controls
			src={source}><track kind="captions" /></video
		>{/if}
	<a href={source} download={name}>Download {name}</a>
{:else}<button disabled={loading} onclick={load}>Open {name}</button>{/if}
{#if error}<span role="alert">{error}</span>{/if}

<style>
	img,
	video {
		display: block;
		max-width: min(100%, 28rem);
		max-height: 20rem;
	}
</style>
