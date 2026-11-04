<script lang="ts">
	import { messageLink } from './chatLinks';
	let { id }: { id: number } = $props();
	let fallback = $state(''),
		copied = $state(false);
	async function copy() {
		const url = messageLink(location.href, id);
		try {
			await navigator.clipboard.writeText(url);
			copied = true;
		} catch {
			fallback = url;
		}
	}
</script>

<button title="Copy link to message" onclick={copy}>{copied ? 'Copied' : 'Copy link'}</button>
{#if fallback}<input
		aria-label="Message link"
		readonly
		value={fallback}
		onclick={(e) => e.currentTarget.select()}
	/>{/if}
