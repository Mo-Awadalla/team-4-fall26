<script lang="ts">
	import { communityRequest, type Poll } from './communities';
	let { poll, url, onvote }: { poll: Poll; url: string; onvote: (poll: Poll) => void } = $props();
	let error = $state(''),
		busy = $state(false);
	async function vote(choice: number) {
		busy = true;
		try {
			onvote(await communityRequest<Poll>(url, 'PUT', { choice }));
			error = '';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Vote failed';
		} finally {
			busy = false;
		}
	}
</script>

<div role="group" aria-label="Poll options">
	{#each poll.options as option, i (option)}<button
			disabled={busy}
			aria-pressed={poll.mine === i}
			onclick={() => void vote(i)}>{poll.mine === i ? '✓ ' : ''}{option} · {poll.counts[i]}</button
		>{/each}
</div>
{#if error}<span role="alert">{error}</span>{/if}
