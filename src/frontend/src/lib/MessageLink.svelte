<script lang="ts">
	import Link2 from '@lucide/svelte/icons/link-2';
	import Check from '@lucide/svelte/icons/check';
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

<button
	title="Copy link to message"
	onclick={copy}
	aria-label={copied ? 'Link copied' : 'Copy link to message'}
	>{#if copied}<Check size={16} />{:else}<Link2 size={16} />{/if}</button
>
{#if fallback}<input
		aria-label="Message link"
		readonly
		value={fallback}
		onclick={(e) => e.currentTarget.select()}
	/>{/if}
