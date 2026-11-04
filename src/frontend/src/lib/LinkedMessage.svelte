<script lang="ts">
	import { communityRequest } from './communities';
	import MessageBody from './MessageBody.svelte';
	import { onMount } from 'svelte';
	let { url }: { url: string } = $props();
	let linked = $state<{ content: string; author_name: string; deleted_at: string | null } | null>(
		null
	);
	let error = $state('');
	onMount(() => {
		let current = 0;
		async function open() {
			const version = ++current;
			linked = null;
			error = '';
			const match = /^#message-(\d+)$/.exec(location.hash);
			if (!match) return;
			try {
				const item = await communityRequest<
					| NonNullable<typeof linked>
					| { content: string; author_name: string; deleted_at: string | null }
				>(url + '/' + match[1]);
				if (version === current) linked = item;
			} catch {
				if (version === current) error = 'This linked message is unavailable.';
			}
		}
		void open();
		window.addEventListener('hashchange', open);
		return () => {
			current++;
			window.removeEventListener('hashchange', open);
		};
	});
</script>

{#if linked}<aside aria-label="Linked message">
		<strong>Linked message · {linked.author_name}</strong><MessageBody
			content={linked.deleted_at ? 'Message deleted' : linked.content}
		/>
	</aside>{:else if error}<p>{error}</p>{/if}
