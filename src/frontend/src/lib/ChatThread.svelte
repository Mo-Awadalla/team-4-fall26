<script lang="ts">
	import { onMount } from 'svelte';
	import MessageLink from './MessageLink.svelte';
	import { mergeMessages } from './history';
	import { communityRequest, type DirectMessage } from './communities';
	import MessageBody from './MessageBody.svelte';
	let {
		url,
		root,
		onclose
	}: { url: string; root: { id: number; content: string }; onclose: () => void } = $props();
	type Reply = DirectMessage & { can_delete?: boolean };
	let editing = $state<number | null>(null),
		draft = $state('');
	async function change(item: Reply, method: 'PATCH' | 'DELETE') {
		try {
			await communityRequest(
				url + '/' + item.id,
				method,
				method === 'PATCH' ? { content: draft } : undefined
			);
			const fresh = await communityRequest<Reply>(url + '/' + item.id);
			items = mergeMessages(items, [fresh]);
			editing = null;
			error = '';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Message update failed';
		}
	}
	let items = $state<Reply[]>([]),
		content = $state(''),
		error = $state(''),
		busy = $state(false),
		more = $state(false);
	async function load(older = false) {
		try {
			const page = await communityRequest<{ items: Reply[]; has_more: boolean }>(
				url + '?thread=' + root.id + (older && items.length ? '&before=' + items[0].id : '')
			);
			if (older) {
				items = mergeMessages(items, page.items);
				more = page.has_more;
			} else {
				const first = page.items[0]?.id;
				const kept = first ? items.filter((i) => i.id < first) : [];
				items = mergeMessages(kept, page.items);
				if (!kept.length) more = page.has_more;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Cannot load thread';
		}
	}
	async function send() {
		if (busy || !content.trim()) return;
		busy = true;
		try {
			await communityRequest(url, 'POST', { content, thread: root.id });
			content = '';
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Send failed';
		} finally {
			busy = false;
		}
	}
	onMount(() => {
		void load();
		const t = window.setInterval(() => {
			if (!document.hidden) void load();
		}, 3000);
		return () => clearInterval(t);
	});
</script>

<aside class="thread">
	<header><strong>Thread</strong><button onclick={onclose}>Close</button></header>
	<MessageBody content={root.content} />
	<hr />
	{#if more}<button onclick={() => void load(true)}>Earlier replies</button>{/if}
	{#each items as item (item.id)}<p><strong>{item.author_name}</strong></p>
		{#if editing === item.id}<form
				onsubmit={(e) => {
					e.preventDefault();
					void change(item, 'PATCH');
				}}
			>
				<input aria-label="Edit thread reply" bind:value={draft} maxlength="2000" /><button
					disabled={!draft.trim()}>Save</button
				><button type="button" onclick={() => (editing = null)}>Cancel</button>
			</form>
		{:else}<MessageBody content={item.deleted_at ? 'Message deleted' : item.content} />{/if}
		{#if !item.deleted_at}<MessageLink id={item.id} />{#if item.mine}<button
					onclick={() => {
						draft = item.content;
						editing = item.id;
					}}>Edit</button
				>{/if}
			{#if item.mine || item.can_delete}<button
					onclick={() => {
						if (confirm('Delete this reply?')) void change(item, 'DELETE');
					}}>Delete</button
				>{/if}{/if}{:else}<p>Start the discussion.</p>{/each}
	<form
		onsubmit={(e) => {
			e.preventDefault();
			void send();
		}}
	>
		<input aria-label="Thread reply" maxlength="2000" bind:value={content} /><button
			disabled={busy || !content.trim()}>Reply in thread</button
		>
	</form>
	{#if error}<p role="alert">{error}</p>{/if}
</aside>

<style>
	.thread {
		background: var(--panel);
		border: 1px solid var(--line);
		padding: 1rem;
		position: absolute;
		inset: 0 0 0 auto;
		width: min(100%, 24rem);
		overflow: auto;
		z-index: 3;
		box-shadow: -4px 0 14px #0002;
	}
	header {
		display: flex;
		justify-content: space-between;
	}
</style>
