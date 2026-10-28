<script lang="ts">
	import {
		communityRequest,
		type Channel,
		type DirectConversation,
		type Message
	} from './communities';

	let {
		communityId,
		channel,
		role,
		onDirectMessage
	}: {
		communityId: number;
		channel: Channel;
		role: string;
		onDirectMessage: (conversation: DirectConversation) => void;
	} = $props();
	let messages = $state<Message[]>([]);
	let hasOlder = $state(false);
	let content = $state('');
	let replyTo = $state<Message | null>(null);
	let editingId = $state<number | null>(null);
	let draft = $state('');
	let reactionFor = $state<number | null>(null);
	let search = $state('');
	let results = $state<Message[] | null>(null);
	let pins = $state<Message[] | null>(null);
	let error = $state('');
	let sending = $state(false);
	let polling = false;
	let generation = 0;
	const emojiChoices = ['👍', '❤️', '😂', '🎉', '😮'];

	const base = () => `/communities/${communityId}/channels/${channel.id}`;
	const displayTime = (value: string) => new Date(value).toLocaleString();
	const problem = (cause: unknown) =>
		cause instanceof Error ? cause.message : 'Something went wrong.';

	async function load() {
		const current = ++generation;
		try {
			const page = await communityRequest<{ items: Message[]; has_more: boolean }>(
				`${base()}/messages`
			);
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
			const page = await communityRequest<{ items: Message[]; has_more: boolean }>(
				`${base()}/messages`
			);
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
			const page = await communityRequest<{ items: Message[]; has_more: boolean }>(
				`${base()}/messages?before=${messages[0].id}`
			);
			messages = [...page.items, ...messages];
			hasOlder = page.has_more;
		} catch (cause) {
			error = problem(cause);
		}
	}

	async function send() {
		if (!content.trim() || sending) return;
		sending = true;
		try {
			const message = await communityRequest<Message>(`${base()}/messages`, 'POST', {
				content,
				...(replyTo ? { reply_to: replyTo.id } : {})
			});
			messages = [...messages, message];
			content = '';
			replyTo = null;
			error = '';
		} catch (cause) {
			error = problem(cause);
		} finally {
			sending = false;
		}
	}

	async function change(message: Message, method: string, suffix = '', body?: object) {
		try {
			const changed = await communityRequest<Message>(
				`${base()}/messages/${message.id}${suffix}`,
				method,
				body
			);
			if (method === 'DELETE' && !suffix) {
				messages = messages.map((item) =>
					item.id === message.id
						? {
								...item,
								content: '',
								deleted_at: new Date().toISOString(),
								reactions: [],
								pinned_at: null
							}
						: item
				);
			} else {
				messages = messages.map((item) => (item.id === changed.id ? changed : item));
			}
			if (method === 'PATCH') editingId = null;
			reactionFor = null;
			error = '';
		} catch (cause) {
			error = problem(cause);
		}
	}

	async function find() {
		if (search.trim().length < 2) return;
		try {
			const found = await communityRequest<{ items: Message[] }>(
				`/communities/${communityId}/messages/search?q=${encodeURIComponent(search.trim())}`
			);
			results = found.items;
			pins = null;
			error = '';
		} catch (cause) {
			error = problem(cause);
		}
	}

	async function showPins() {
		try {
			pins = (await communityRequest<{ items: Message[] }>(`${base()}/pins`)).items;
			results = null;
		} catch (cause) {
			error = problem(cause);
		}
	}

	async function startDM(message: Message) {
		try {
			const conversation = await communityRequest<DirectConversation>(
				`${base()}/messages/${message.id}/dm`,
				'POST'
			);
			onDirectMessage(conversation);
		} catch (cause) {
			error = problem(cause);
		}
	}

	$effect(() => {
		void communityId;
		void channel.id;
		messages = [];
		hasOlder = false;
		results = pins = null;
		void load();
		const timer = window.setInterval(() => void refresh(), 3000);
		return () => {
			window.clearInterval(timer);
			generation++;
		};
	});
</script>

<div class="chat">
	<div class="toolbar">
		<strong># {channel.name}</strong>
		<div class="tools">
			<form
				onsubmit={(event) => {
					event.preventDefault();
					void find();
				}}
			>
				<input
					aria-label="Search community messages"
					placeholder="Search messages"
					bind:value={search}
				/>
				<button>Search</button>
			</form>
			<button onclick={() => void showPins()}>Pins</button>
		</div>
	</div>
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	{#if results || pins}
		<div class="results">
			<button
				onclick={() => {
					results = null;
					pins = null;
				}}>Back to chat</button
			>
			<h4>{results ? 'Search results' : 'Pinned messages'}</h4>
			{#each results ?? pins ?? [] as item (item.id)}
				<p><strong>{item.author_name}</strong> · #{item.channel_id} · {item.content}</p>
			{:else}<p>No messages found.</p>{/each}
		</div>
	{:else}
		<div class="messages" aria-live="polite">
			{#if hasOlder}<button onclick={() => void older()}>Load older messages</button>{/if}
			{#each messages as message (message.id)}
				<article class="message" id={`message-${message.id}`}>
					<div class="message-head">
						<strong>{message.author_name}</strong><time datetime={message.created_at}
							>{displayTime(message.created_at)}</time
						>{#if message.pinned_at}<span>📌 Pinned</span>{/if}
					</div>
					{#if message.reply_to}<p class="reply">↳ Reply to message #{message.reply_to}</p>{/if}
					{#if editingId === message.id}
						<form
							class="edit-form"
							onsubmit={(event) => {
								event.preventDefault();
								void change(message, 'PATCH', '', { content: draft });
							}}
						>
							<input aria-label="Edit message" maxlength="2000" bind:value={draft} />
							<button disabled={!draft.trim()}>Save</button>
							<button type="button" onclick={() => (editingId = null)}>Cancel</button>
						</form>
					{:else}<p class="body">
							{message.deleted_at ? 'Message deleted' : message.content}{message.edited_at
								? ' (edited)'
								: ''}
						</p>{/if}
					{#if !message.deleted_at}
						<div class="message-actions">
							<button onclick={() => (replyTo = message)}>Reply</button>
							{#if !message.mine}<button onclick={() => void startDM(message)}
									>Message privately</button
								>{/if}
							{#each message.reactions as reaction (reaction.emoji)}
								<button
									class:mine={reaction.me}
									onclick={() =>
										void change(
											message,
											reaction.me ? 'DELETE' : 'POST',
											`/reactions${reaction.me ? `/${encodeURIComponent(reaction.emoji)}` : ''}`,
											reaction.me ? undefined : { emoji: reaction.emoji }
										)}>{reaction.emoji} {reaction.count}</button
								>
							{/each}
							<button onclick={() => (reactionFor = reactionFor === message.id ? null : message.id)}
								>+ React</button
							>
							{#if message.mine}<button
									onclick={() => {
										editingId = message.id;
										draft = message.content;
									}}>Edit</button
								>{/if}
							{#if role === 'owner' || role === 'moderator'}<button
									onclick={() =>
										void change(message, message.pinned_at ? 'DELETE' : 'POST', '/pin')}
									>{message.pinned_at ? 'Unpin' : 'Pin'}</button
								>{/if}
							{#if message.can_delete}<button
									onclick={() => {
										if (confirm('Delete this message?')) void change(message, 'DELETE');
									}}>Delete</button
								>{/if}
						</div>
						{#if reactionFor === message.id}<div
								class="reaction-picker"
								aria-label="Choose a reaction"
							>
								{#each emojiChoices as emoji (emoji)}<button
										onclick={() => void change(message, 'POST', '/reactions', { emoji })}
										>{emoji}</button
									>{/each}
							</div>{/if}
					{/if}
				</article>
			{:else}<p class="muted">No messages yet. Start the conversation.</p>{/each}
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
			<input
				aria-label={`Message #${channel.name}`}
				maxlength="2000"
				placeholder={channel.archived ? 'This channel is archived' : `Message #${channel.name}`}
				bind:value={content}
				disabled={channel.archived}
			/>
			<button disabled={channel.archived || sending || !content.trim()}>Send</button>
		</form>
	{/if}
</div>

<style>
	.chat {
		border: 1px solid #eee1e4;
		border-radius: 12px;
		overflow: hidden;
		margin-top: 18px;
	}
	.toolbar,
	.tools,
	.tools form,
	.message-head,
	.message-actions,
	.composer {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.toolbar {
		justify-content: space-between;
		padding: 12px 16px;
		border-bottom: 1px solid #eee1e4;
	}
	.tools input {
		width: 170px;
	}
	.messages {
		min-height: 240px;
		max-height: 500px;
		overflow-y: auto;
		padding: 16px;
	}
	.message {
		padding: 12px 0;
		border-bottom: 1px solid #f2ecee;
	}
	.message-head time,
	.reply,
	.muted {
		color: #746c70;
		font-size: 12px;
	}
	.message-head span {
		color: #b53650;
		font-size: 12px;
	}
	.body {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		margin: 6px 0;
	}
	.message-actions {
		flex-wrap: wrap;
	}
	.message-actions button {
		font-size: 12px;
		padding: 3px 7px;
	}
	.message-actions .mine {
		background: #ffe4e8;
	}
	.edit-form,
	.reaction-picker {
		display: flex;
		gap: 6px;
		margin: 8px 0;
	}
	.edit-form input {
		flex: 1;
	}
	.replying {
		padding: 0 16px;
		font-size: 13px;
	}
	.composer {
		padding: 12px;
		border-top: 1px solid #eee1e4;
	}
	.composer input {
		flex: 1;
	}
	.results {
		padding: 16px;
		max-height: 500px;
		overflow-y: auto;
	}
	.results p {
		border-bottom: 1px solid #f2ecee;
		padding: 8px 0;
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
	input {
		border: 1px solid #d8cdd0;
		border-radius: 7px;
		padding: 9px;
		font: inherit;
	}
	.error {
		color: #a51f3b;
		padding: 0 16px;
	}
	@media (max-width: 750px) {
		.toolbar,
		.tools {
			align-items: stretch;
			flex-direction: column;
		}
		.tools form {
			width: 100%;
		}
		.tools input {
			flex: 1;
			width: 0;
		}
	}
</style>
