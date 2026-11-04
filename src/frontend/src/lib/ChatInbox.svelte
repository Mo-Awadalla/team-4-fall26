<script lang="ts">
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { communityRequest } from './communities';
	type Notice = {
		id: number;
		author_name: string;
		content: string;
		channel_id?: number;
		channel__community_id?: number;
		conversation_id?: number;
	};
	let items = $state<Notice[]>([]),
		error = $state('');
	onMount(() => {
		let busy = false;
		async function refresh() {
			if (document.hidden || busy) return;
			busy = true;
			try {
				items = (await communityRequest<{ items: Notice[] }>('/chat/notifications')).items;
				error = '';
			} catch (e) {
				error = e instanceof Error ? e.message : 'Inbox unavailable';
			} finally {
				busy = false;
			}
		}
		void refresh();
		const timer = setInterval(refresh, 8000);
		return () => clearInterval(timer);
	});
</script>

<details>
	<summary>Inbox {items.length ? '· ' + items.length : ''}</summary>
	{#if error}<small>{error}</small>{/if}
	{#each items as item ((item.conversation_id ? 'dm' : 'ch') + item.id)}<a
			data-sveltekit-reload
			href={resolve('/communities') +
				'?' +
				(item.conversation_id
					? 'dm=' + item.conversation_id
					: 'id=' + item.channel__community_id + '&channel=' + item.channel_id) +
				'#message-' +
				item.id}><b>{item.author_name}</b> {item.content.slice(0, 65) || 'Attachment'}</a
		>{:else}<small>No unread notifications.</small>{/each}
</details>

<style>
	details {
		padding: 0.6rem;
		max-height: 40vh;
		overflow: auto;
	}
	a {
		display: block;
		padding: 0.4rem;
	}
</style>
