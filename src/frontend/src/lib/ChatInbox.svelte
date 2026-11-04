<script lang="ts">
	import Inbox from '@lucide/svelte/icons/inbox';
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

<details class="inbox">
	<summary class="chat-icon" aria-label="Notification inbox" title="Inbox"
		><Inbox size={18} />{#if items.length}<i></i>{/if}</summary
	>
	<section>
		<strong>Inbox</strong>{#if error}<small>{error}</small>{/if}
		{#each items as item ((item.conversation_id ? 'dm' : 'ch') + item.id)}
			<a
				data-sveltekit-reload
				href={resolve(
					`/communities?${item.conversation_id ? 'dm=' + item.conversation_id : 'id=' + item.channel__community_id + '&channel=' + item.channel_id}#message-${item.id}`
				)}><b>{item.author_name}</b> {item.content.slice(0, 65) || 'Attachment'}</a
			>{:else}<small>No unread notifications.</small>{/each}
	</section>
</details>

<style>
	.inbox {
		position: relative;
	}
	.inbox summary {
		list-style: none;
		position: relative;
	}
	.inbox summary::-webkit-details-marker {
		display: none;
	}
	i {
		position: absolute;
		right: 5px;
		top: 4px;
		width: 6px;
		height: 6px;
		background: var(--accent);
		border-radius: 50%;
	}
	section {
		position: absolute;
		right: 0;
		top: 100%;
		z-index: 9;
		width: min(288px, 80vw);
		padding: 14px;
		background: var(--panel);
		color: var(--ink);
		border: 1px solid var(--line);
		border-radius: 10px;
		box-shadow: 0 8px 28px #0002;
		max-height: 55vh;
		overflow: auto;
	}
	section strong,
	section a,
	section small {
		display: block;
		padding: 4px;
	}
</style>
