<script lang="ts">
	import SearchMessages from './SearchMessages.svelte';
	import MessageLink from './MessageLink.svelte';
	import LinkedMessage from './LinkedMessage.svelte';
	import Ballot from './Ballot.svelte';
	import PollComposer from './PollComposer.svelte';
	import Presence from './Presence.svelte';
	import Stickers from './Stickers.svelte';
	import ChatThread from './ChatThread.svelte';
	import Attachment from './Attachment.svelte';
	import { composeMessage } from './communities';
	import MessageBody from './MessageBody.svelte';
	import { communityRequest, type DirectConversation, type DirectMessage } from './communities';

	let { conversation }: { conversation: DirectConversation } = $props();
	let messages = $state<DirectMessage[]>([]);
	async function react(item: DirectMessage, emoji: string) {
		try {
			const updated = await communityRequest<DirectMessage>(
				base() + '/' + item.id + '/reactions',
				'PUT',
				{ emoji, active: !item.reactions?.find((r) => r.emoji === emoji)?.me }
			);
			messages = messages.map((m) => (m.id === item.id ? updated : m));
		} catch (e) {
			error = problem(e);
		}
	}
	let pins = $state<DirectMessage[]>([]);
	async function showPins() {
		try {
			pins = (await communityRequest<{ items: DirectMessage[] }>(`/dms/${conversation.id}/pins`))
				.items;
		} catch (e) {
			error = problem(e);
		}
	}
	async function pin(item: DirectMessage) {
		try {
			const updated = await communityRequest<DirectMessage>(
				base() + '/' + item.id + '/pin',
				'PUT',
				{ pinned: !item.pinned_at }
			);
			messages = messages.map((m) => (m.id === item.id ? updated : m));
			await showPins();
		} catch (e) {
			error = problem(e);
		}
	}
	let matches = $state<Pick<DirectMessage, 'id' | 'author_name' | 'content'>[]>([]);
	let hasOlder = $state(false);
	let content = $state('');
	let replyTo = $state<DirectMessage | null>(null);
	let editingId = $state<number | null>(null);
	let draft = $state('');
	let error = $state('');
	let files = $state<FileList>();
	let thread = $state<{ id: number; content: string } | null>(null);
	let presence = $state<Presence>();
	let sending = $state(false);
	let polling = false;
	let generation = 0;
	const base = () => `/dms/${conversation.id}/messages`;
	const problem = (cause: unknown) =>
		cause instanceof Error ? cause.message : 'Something went wrong.';

	async function load() {
		const current = ++generation;
		try {
			const page = await communityRequest<{ items: DirectMessage[]; has_more: boolean }>(base());
			if (current !== generation) return;
			messages = page.items;
			hasOlder = page.has_more;
			error = '';
		} catch (cause) {
			if (current === generation) error = problem(cause);
		}
	}

	async function refresh() {
		if (polling || document.visibilityState !== 'visible') return;
		polling = true;
		const current = generation;
		try {
			const page = await communityRequest<{ items: DirectMessage[] }>(base());
			if (current === generation) {
				const first = page.items[0]?.id;
				const retained = first ? messages.filter((item) => item.id < first) : [];
				const older = retained.slice(-200);
				messages = [...older, ...page.items];
				hasOlder ||= retained.length > older.length;
			}
		} catch (cause) {
			if (current === generation) error = problem(cause);
		} finally {
			polling = false;
		}
	}

	async function older() {
		if (!messages.length) return;
		try {
			const page = await communityRequest<{ items: DirectMessage[]; has_more: boolean }>(
				`${base()}?before=${messages[0].id}`
			);
			messages = [...page.items, ...messages];
			hasOlder = page.has_more;
		} catch (cause) {
			error = problem(cause);
		}
	}

	async function send() {
		if ((!content.trim() && !files?.length) || sending) return;
		sending = true;
		try {
			const sent = await communityRequest<DirectMessage>(
				base(),
				'POST',
				composeMessage(
					{
						content,
						...(replyTo ? { reply_to: replyTo.id } : {})
					},
					files?.[0]
				)
			);
			messages = [...messages, sent];
			files = new DataTransfer().files;
			content = '';
			replyTo = null;
			error = '';
		} catch (cause) {
			error = problem(cause);
		} finally {
			sending = false;
		}
	}

	async function change(message: DirectMessage, method: 'PATCH' | 'DELETE') {
		try {
			const updated = await communityRequest<DirectMessage>(
				`${base()}/${message.id}`,
				method,
				method === 'PATCH' ? { content: draft } : undefined
			);
			messages = messages.map((item) =>
				item.id === message.id
					? method === 'PATCH'
						? updated
						: { ...item, content: '', deleted_at: new Date().toISOString() }
					: item
			);
			editingId = null;
			error = '';
		} catch (cause) {
			error = problem(cause);
		}
	}

	$effect(() => {
		void conversation.id;
		messages = [];
		hasOlder = false;
		void load();
		const timer = window.setInterval(() => void refresh(), 3000);
		return () => {
			window.clearInterval(timer);
			generation++;
		};
	});
</script>

<div class="dm">
	<h2>Direct message with {conversation.other_name}</h2>
	<details
		ontoggle={(e) => {
			if (e.currentTarget.open) void showPins();
		}}
	>
		<summary>Pinned messages</summary>{#each pins as item (item.id)}<p>
				{item.author_name} · {item.content}
			</p>{:else}<p>No pins yet.</p>{/each}
	</details>
	<details>
		<summary>Search conversation</summary><SearchMessages
			url={base() + '/search'}
			onresults={(items) => (matches = items)}
			onerror={(s) => (error = s)}
		/>{#each matches as item (item.id)}<p>
				<strong>{item.author_name}</strong>
				{item.content}
			</p>{/each}
	</details>
	<p class="muted">Only the two of you can read this conversation.</p>
	{#if thread}{#key thread.id}<ChatThread
				url={base()}
				root={thread}
				onclose={() => (thread = null)}
			/>{/key}{/if}
	<LinkedMessage url={base()} />
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	<div class="messages" aria-live="polite">
		{#if hasOlder}<button onclick={() => void older()}>Load older messages</button>{/if}
		{#each messages as message (message.id)}
			<article>
				<div class="heading">
					<strong>{message.author_name}</strong><time datetime={message.created_at}
						>{new Date(message.created_at).toLocaleString()}</time
					>
				</div>
				{#if message.reply_to}<small>↳ Reply to message #{message.reply_to}</small>{/if}
				{#if editingId === message.id}
					<form
						class="edit"
						onsubmit={(event) => {
							event.preventDefault();
							void change(message, 'PATCH');
						}}
					>
						<input aria-label="Edit direct message" maxlength="2000" bind:value={draft} />
						<button disabled={!draft.trim()}>Save</button><button
							type="button"
							onclick={() => (editingId = null)}>Cancel</button
						>
					</form>
				{:else}{#if message.deleted_at}Message deleted{:else}{#if message.poll}<Ballot
								poll={message.poll}
								url={base() + '/' + message.id + '/vote'}
								onvote={(poll) =>
									(messages = messages.map((m) => (m.id === message.id ? { ...m, poll } : m)))}
							/>{/if}{#if message.file_name}<Attachment
								url={base() + '/' + message.id}
								name={message.file_name}
							/>{/if}<MessageBody content={message.content} />{#if message.edited_at}<small
								>(edited)</small
							>{/if}{/if}{/if}
				{#if !message.deleted_at}<div class="actions">
						<button onclick={() => void pin(message)}>{message.pinned_at ? 'Unpin' : 'Pin'}</button>
						<details>
							<summary>React</summary
							>{#each ['👍', '❤️', '😂', '🎉', '😮', '🔥', '😢'] as emoji (emoji)}<button
									onclick={() => void react(message, emoji)}>{emoji}</button
								>{/each}
						</details>
						{#each message.reactions ?? [] as r (r.emoji)}<button
								aria-pressed={r.me}
								onclick={() => void react(message, r.emoji)}>{r.emoji} {r.count}</button
							>{/each}
						<button onclick={() => (thread = message)}>Thread</button><MessageLink
							id={message.id}
						/>
						<button onclick={() => (replyTo = message)}>Reply</button>
						{#if message.mine}<button
								onclick={() => {
									editingId = message.id;
									draft = message.content;
								}}>Edit</button
							><button
								onclick={() => {
									if (confirm('Delete this message?')) void change(message, 'DELETE');
								}}>Delete</button
							>{/if}
					</div>{/if}
			</article>
		{:else}<p class="muted">No messages yet. Say hello.</p>{/each}
	</div>
	{#if replyTo}<p class="replying">
			Replying to {replyTo.author_name} <button onclick={() => (replyTo = null)}>Cancel</button>
		</p>{/if}
	<form
		class="composer"
		onsubmit={(event) => {
			event.preventDefault();
			void send();
		}}
	>
		<PollComposer url={base()} onsent={() => void refresh()} /><Presence
			bind:this={presence}
			url={`/dms/${conversation.id}` + '/presence'}
		/><Stickers
			onpick={(s) => {
				content = s;
			}}
		/><label>Attach file (2 MiB)<input type="file" bind:files /></label>
		<input
			aria-label={`Message ${conversation.other_name}`}
			maxlength="2000"
			placeholder={`Message ${conversation.other_name}`}
			oninput={() => presence?.typing()}
			bind:value={content}
		/>
		<button disabled={(!content.trim() && !files?.length) || sending}>Send</button>
	</form>
</div>

<style>
	.dm {
		position: relative;
	}
	.dm {
		border: 1px solid #eee1e4;
		border-radius: 12px;
		padding: 20px;
	}
	h2 {
		margin: 0;
	}
	.muted,
	time,
	small {
		color: #746c70;
	}
	time {
		font-size: 12px;
	}
	.heading,
	.actions,
	.composer,
	.edit {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.messages {
		min-height: 260px;
		max-height: 520px;
		overflow-y: auto;
		margin: 20px 0;
	}
	article {
		padding: 12px 0;
		border-bottom: 1px solid #f2ecee;
	}
	article p {
		margin: 6px 0;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}
	.actions button {
		font-size: 12px;
		padding: 3px 7px;
	}
	.composer input,
	.edit input {
		flex: 1;
	}
	input {
		border: 1px solid #d8cdd0;
		border-radius: 7px;
		padding: 9px;
		font: inherit;
	}
	button {
		cursor: pointer;
		border: 1px solid #ddd2d5;
		border-radius: 7px;
		background: white;
		padding: 6px 10px;
	}
	button:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.error {
		color: #a51f3b;
	}
</style>
