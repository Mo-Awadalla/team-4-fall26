<script lang="ts">
	let { id }: { id: number } = $props();
	let fallback = $state(''),
		copied = $state(false);
	async function copy() {
		const url = new URL(location.href);
		url.hash = 'message-' + id;
		try {
			await navigator.clipboard.writeText(url.href);
			copied = true;
		} catch {
			fallback = url.href;
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
