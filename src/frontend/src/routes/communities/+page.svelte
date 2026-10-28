<script lang="ts">
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { communityRequest, type Community, type Invite, type Member } from '$lib/communities';

	let communities = $state<Community[]>([]);
	let selected = $state<Community | null>(null);
	let members = $state<Member[]>([]);
	let hasMoreMembers = $state(false);
	let invites = $state<Invite[]>([]);
	let bannedIds = $state<(string | number)[]>([]);
	let moderationEvents = $state<
		{ id: number; action: string; target_id: string | number | null }[]
	>([]);
	let query = $state('');
	let viewMine = $state(false);
	let hasMore = $state(false);
	let error = $state('');
	let loading = $state(true);
	let creating = $state(false);
	let name = $state('');
	let description = $state('');
	let school = $state('');
	let course = $state('');
	let channelName = $state('');
	let inviteLink = $state('');
	let tab = $state<'about' | 'members' | 'settings'>('about');
	let requestNumber = 0;
	const activeCommunityId = () => selected?.id;

	async function browse(search = query, more = false, mine = viewMine) {
		const current = ++requestNumber;
		loading = true;
		try {
			const result = await communityRequest<{ items: Community[]; has_more: boolean }>(
				`/communities?q=${encodeURIComponent(search)}&offset=${more ? communities.length : 0}${mine ? '&mine=true' : ''}`
			);
			if (current === requestNumber) {
				communities = more ? [...communities, ...result.items] : result.items;
				hasMore = result.has_more;
			}
		} catch (cause) {
			if (current === requestNumber) {
				communities = [];
				hasMore = false;
				error = message(cause);
			}
		} finally {
			if (current === requestNumber) loading = false;
		}
	}

	function message(cause: unknown): string {
		return cause instanceof Error ? cause.message : 'Something went wrong.';
	}

	async function choose(id: number) {
		error = '';
		try {
			selected = await communityRequest<Community>(`/communities/${id}`);
			name = selected.name;
			description = selected.description;
			school = selected.school;
			course = selected.course;
			members = [];
			invites = [];
			tab = 'about';
			history.replaceState(null, '', `?id=${id}`);
		} catch (cause) {
			error = message(cause);
		}
	}

	async function action(path: string, method = 'POST', body?: object) {
		error = '';
		try {
			await communityRequest(path, method, body);
			const previousTab = tab;
			if (selected) {
				await choose(selected.id);
				if (previousTab === 'members') await loadMembers();
				if (previousTab === 'settings') await loadSettings();
			}
			await browse();
		} catch (cause) {
			error = message(cause);
		}
	}

	async function deleteCommunity() {
		if (!selected || !confirm(`Delete ${selected.name} and all its channels?`)) return;
		try {
			await communityRequest(`/communities/${selected.id}`, 'DELETE');
			selected = null;
			history.replaceState(null, '', resolve('/communities'));
			await browse();
		} catch (cause) {
			error = message(cause);
		}
	}

	async function create() {
		error = '';
		try {
			const created = await communityRequest<Community>('/communities', 'POST', {
				name,
				description,
				school,
				course
			});
			creating = false;
			name = description = school = course = '';
			await browse();
			await choose(created.id);
		} catch (cause) {
			error = message(cause);
		}
	}

	async function loadMembers(more = false) {
		if (!selected) return;
		tab = 'members';
		try {
			const result = await communityRequest<{ items: Member[]; has_more: boolean }>(
				`/communities/${selected.id}/members?limit=50&offset=${more ? members.length : 0}`
			);
			members = more ? [...members, ...result.items] : result.items;
			hasMoreMembers = result.has_more;
		} catch (cause) {
			error = message(cause);
		}
	}

	async function loadSettings() {
		if (!selected) return;
		tab = 'settings';
		if (selected.role === 'owner' || selected.role === 'moderator') {
			try {
				invites = await communityRequest<Invite[]>(`/communities/${selected.id}/invites`);
				const moderation = await communityRequest<{
					banned_user_ids: (string | number)[];
					events: typeof moderationEvents;
				}>(`/communities/${selected.id}/moderation`);
				bannedIds = moderation.banned_user_ids;
				moderationEvents = moderation.events;
			} catch (cause) {
				error = message(cause);
			}
		}
	}

	async function createInvite() {
		if (!selected) return;
		try {
			const result = await communityRequest<{ token: string }>(
				`/communities/${selected.id}/invites`,
				'POST',
				{
					expires_in_hours: 168,
					max_uses: 100
				}
			);
			inviteLink = `${location.origin}${resolve('/communities')}?invite=${result.token}`;
			await loadSettings();
		} catch (cause) {
			error = message(cause);
		}
	}

	$effect(() => {
		void browse(query, false, viewMine);
	});

	onMount(() => {
		const url = new URL(location.href);
		const id = Number(url.searchParams.get('id'));
		if (Number.isSafeInteger(id) && id > 0) void choose(id);
		const token = url.searchParams.get('invite');
		if (token) {
			void communityRequest<{ community_id: number }>(
				`/communities/invites/${encodeURIComponent(token)}/redeem`,
				'POST'
			)
				.then((result) => choose(result.community_id))
				.catch((cause) => {
					error = message(cause);
				});
		}
	});
</script>

<svelte:head>
	<title>Communities · StudySpot</title>
	<meta name="description" content="Find and create public study communities in New York City." />
</svelte:head>

<div class="shell">
	<header>
		<a class="brand" href={resolve('/')}>StudySpot</a>
		<nav>
			<a href={resolve('/')}>Explore spots</a><a class="current" href={resolve('/communities')}
				>Communities</a
			>
		</nav>
	</header>
	<main>
		<aside class="sidebar">
			<h1>Find your people.</h1>
			<p>Public study communities for courses, schools, and neighborhoods.</p>
			<label for="community-search">Search communities</label>
			<div class="tabs">
				<button class:chosen={!viewMine} onclick={() => (viewMine = false)}>All</button><button
					class:chosen={viewMine}
					onclick={() => (viewMine = true)}>Joined</button
				>
			</div>
			<input id="community-search" bind:value={query} placeholder="Math 51A, NYU, Brooklyn…" />
			<button
				class="primary"
				onclick={() => {
					creating = !creating;
					selected = null;
				}}>+ Create community</button
			>
			{#if loading}<p class="muted">Loading…</p>{/if}
			<div class="list">
				{#each communities as community (community.id)}
					<button
						class:active={selected?.id === community.id}
						onclick={() => void choose(community.id)}
					>
						<strong>{community.name}</strong>
						<span
							>{community.course || community.school || 'Study community'} · {community.member_count}
							members</span
						>
					</button>
				{/each}
			</div>
			{#if hasMore}<button onclick={() => void browse(query, true)}>Show more</button>{/if}
		</aside>
		<section class="content">
			{#if error}<p class="error" role="alert">{error}</p>{/if}
			{#if creating}
				<h2>Create a community</h2>
				<p class="muted">Everyone can discover and read public communities.</p>
				<form
					onsubmit={(event) => {
						event.preventDefault();
						void create();
					}}
				>
					<label
						>Name<input
							required
							maxlength="100"
							bind:value={name}
							placeholder="Math 51A Study Group"
						/></label
					>
					<label>Description<textarea maxlength="1000" bind:value={description}></textarea></label>
					<label>School<input maxlength="100" bind:value={school} placeholder="NYU" /></label>
					<label>Course<input maxlength="100" bind:value={course} placeholder="MATH 51A" /></label>
					<button class="primary">Create community</button>
				</form>
			{:else if selected}
				<div class="title">
					<div>
						<p class="eyebrow">Public community · {selected.member_count} members</p>
						<h2>{selected.name}</h2>
						<p>{[selected.school, selected.course].filter(Boolean).join(' · ')}</p>
					</div>
					{#if selected.role === 'visitor'}<button
							class="primary"
							onclick={() => void action(`/communities/${activeCommunityId()}/join`)}
							>Join community</button
						>
					{:else if selected.role !== 'owner'}<button
							onclick={() => void action(`/communities/${activeCommunityId()}/leave`)}>Leave</button
						>{/if}
				</div>
				<div class="tabs">
					<button class:chosen={tab === 'about'} onclick={() => (tab = 'about')}>About</button
					><button class:chosen={tab === 'members'} onclick={() => void loadMembers()}
						>Members</button
					>{#if selected.role === 'owner' || selected.role === 'moderator'}<button
							class:chosen={tab === 'settings'}
							onclick={() => void loadSettings()}>Manage</button
						>{/if}
				</div>
				{#if tab === 'about'}
					<p class="description">{selected.description || 'A place to study together.'}</p>
					<h3>Channels</h3>
					{#each selected.channels ?? [] as channel (channel.id)}<p class="channel">
							# {channel.name}
							{channel.archived ? '· Archived' : ''}
						</p>{/each}
					<p class="muted">Channel conversations are coming in a later update.</p>
				{:else if tab === 'members'}
					<h3>Members</h3>
					{#each members as member (member.user_id)}<div class="row">
							<span
								>Member #{member.user_id}
								{member.user_id === String(selected.owner_id)
									? '· Owner'
									: `· ${member.role}`}</span
							>
							{#if selected.role === 'owner' && member.user_id !== String(selected.owner_id)}<button
									onclick={() =>
										void action(
											`/communities/${activeCommunityId()}/members/${member.user_id}`,
											'PATCH',
											{ role: member.role === 'moderator' ? 'member' : 'moderator' }
										)}>{member.role === 'moderator' ? 'Remove moderator' : 'Make moderator'}</button
								>{/if}
							{#if (selected.role === 'owner' || selected.role === 'moderator') && member.user_id !== String(selected.owner_id) && (member.role !== 'moderator' || selected.role === 'owner')}<button
									onclick={() =>
										void action(
											`/communities/${activeCommunityId()}/members/${member.user_id}`,
											'DELETE'
										)}>Kick</button
								><button
									onclick={() =>
										void action(`/communities/${activeCommunityId()}/moderation`, 'POST', {
											user_id: member.user_id,
											action: 'ban'
										})}>Ban</button
								>{/if}
						</div>{/each}
					{#if hasMoreMembers}<button onclick={() => void loadMembers(true)}
							>Show more members</button
						>{/if}
					{#if selected.role === 'owner'}<p class="muted">
							To transfer ownership, choose a member ID:
						</p>
						<form
							onsubmit={(event) => {
								event.preventDefault();
								const input = event.currentTarget.querySelector('input');
								if (input)
									void action(`/communities/${activeCommunityId()}/transfer`, 'POST', {
										user_id: input.value
									});
							}}
						>
							<input required aria-label="New owner member ID" /><button>Transfer ownership</button>
						</form>{/if}
				{:else}
					<h3>Invites</h3>
					<p class="muted">Invites are shareable join links. This community is public.</p>
					<button onclick={() => void createInvite()}>Create 7-day invite</button>
					{#if inviteLink}<p>
							<input
								readonly
								aria-label="New invite link"
								value={inviteLink}
								onclick={(event) => event.currentTarget.select()}
							/>
						</p>{/if}
					{#each invites as invite (invite.id)}<div class="row">
							<span
								>Invite #{invite.id} · {invite.uses}{invite.max_uses ? `/${invite.max_uses}` : ''} uses
								{invite.revoked ? '· Revoked' : ''}</span
							>{#if !invite.revoked}<button
									onclick={() =>
										void action(
											`/communities/${activeCommunityId()}/invites/${invite.id}`,
											'DELETE'
										)}>Revoke</button
								>{/if}
						</div>{/each}
					<h3>Banned members</h3>
					{#each bannedIds as userId (userId)}<div class="row">
							<span>Member #{userId}</span><button
								onclick={() =>
									void action(`/communities/${activeCommunityId()}/moderation`, 'POST', {
										user_id: String(userId),
										action: 'unban'
									})}>Unban</button
							>
						</div>{/each}
					<h3>Recent moderation</h3>
					{#each moderationEvents as event (event.id)}<p class="muted">
							{event.action} · Member #{event.target_id ?? 'deleted'}
						</p>{/each}
					{#if selected.role === 'owner'}
						<h3>Community details</h3>
						<form
							onsubmit={(event) => {
								event.preventDefault();
								void action(`/communities/${activeCommunityId()}`, 'PATCH', {
									name,
									description,
									school,
									course
								});
							}}
						>
							<label>Name<input required maxlength="100" bind:value={name} /></label><label
								>Description<textarea maxlength="1000" bind:value={description}></textarea></label
							><label>School<input maxlength="100" bind:value={school} /></label><label
								>Course<input maxlength="100" bind:value={course} /></label
							><button>Save details</button>
						</form>
						<h3>Channels</h3>
						<form
							onsubmit={(event) => {
								event.preventDefault();
								void action(`/communities/${activeCommunityId()}/channels`, 'POST', {
									name: channelName
								}).then(() => (channelName = ''));
							}}
						>
							<input
								required
								pattern="[a-z0-9][a-z0-9-]*"
								maxlength="50"
								bind:value={channelName}
								placeholder="exam-prep"
								aria-label="New channel name"
							/><button>Add channel</button>
						</form>
						{#each selected.channels ?? [] as channel (channel.id)}<div class="row">
								<span># {channel.name}</span><button
									onclick={() => {
										const next = prompt('Channel name', channel.name);
										if (next && next !== channel.name)
											void action(
												`/communities/${activeCommunityId()}/channels/${channel.id}`,
												'PATCH',
												{ name: next }
											);
									}}>Rename</button
								><button
									disabled={channel.position === 0}
									onclick={() =>
										void action(
											`/communities/${activeCommunityId()}/channels/${channel.id}`,
											'PATCH',
											{ position: channel.position - 1 }
										)}>↑</button
								><button
									disabled={channel.position >= (selected?.channels?.length ?? 0) - 1}
									onclick={() =>
										void action(
											`/communities/${activeCommunityId()}/channels/${channel.id}`,
											'PATCH',
											{ position: channel.position + 1 }
										)}>↓</button
								><button
									onclick={() =>
										void action(
											`/communities/${activeCommunityId()}/channels/${channel.id}`,
											'PATCH',
											{ archived: !channel.archived }
										)}>{channel.archived ? 'Restore' : 'Archive'}</button
								>
							</div>{/each}
						<button class="danger" onclick={() => void deleteCommunity()}>Delete community</button>
					{/if}
				{/if}
			{:else}
				<div class="empty">
					<span>✳</span>
					<h2>Study better together.</h2>
					<p>Choose a community to see its channels and members, or create one for your class.</p>
				</div>
			{/if}
		</section>
	</main>
</div>

<style>
	.shell {
		min-height: 100vh;
		background: #faf9f7;
		color: #262526;
	}
	header {
		max-width: 1220px;
		margin: auto;
		height: 72px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 24px;
	}
	.brand {
		color: #df3150;
		font-size: 22px;
		font-weight: 800;
		letter-spacing: -0.04em;
	}
	nav {
		display: flex;
		gap: 24px;
		font-weight: 600;
	}
	.current {
		color: #df3150;
	}
	main {
		max-width: 1220px;
		min-height: calc(100vh - 72px);
		margin: auto;
		display: grid;
		grid-template-columns: 320px 1fr;
		background: white;
		border: 1px solid #eee7e7;
		border-radius: 16px 16px 0 0;
		overflow: hidden;
	}
	.sidebar {
		background: #fff7f7;
		padding: 32px 22px;
		border-right: 1px solid #f0e3e3;
	}
	h1 {
		font-size: 29px;
		line-height: 1.1;
		letter-spacing: -0.05em;
		margin: 0 0 12px;
	}
	h2 {
		font-size: 33px;
		letter-spacing: -0.05em;
		margin: 0 0 8px;
	}
	h3 {
		margin: 28px 0 12px;
	}
	p {
		line-height: 1.5;
	}
	.sidebar > p,
	.muted {
		color: #746c70;
	}
	label {
		display: block;
		font-size: 13px;
		font-weight: 700;
		margin: 18px 0 8px;
	}
	input,
	textarea {
		width: 100%;
		border: 1px solid #d8cdd0;
		background: white;
		border-radius: 8px;
		padding: 11px 12px;
		font: inherit;
	}
	textarea {
		min-height: 100px;
		resize: vertical;
	}
	button {
		cursor: pointer;
		border: 1px solid #ddd2d5;
		border-radius: 8px;
		background: white;
		padding: 9px 13px;
		font: inherit;
		font-weight: 650;
	}
	button:hover {
		border-color: #df3150;
	}
	.primary {
		background: #df3150;
		color: white;
		border-color: #df3150;
	}
	.sidebar > .primary {
		width: 100%;
		margin: 14px 0 20px;
	}
	.list {
		display: grid;
		gap: 7px;
	}
	.list button {
		text-align: left;
		display: grid;
		gap: 4px;
		border: 0;
		background: transparent;
		padding: 13px;
	}
	.list button.active,
	.list button:hover {
		background: #ffe9ed;
	}
	.list span {
		font-size: 13px;
		color: #746c70;
		font-weight: 400;
	}
	.content {
		padding: 40px 48px;
	}
	.title {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 16px;
	}
	.eyebrow {
		color: #df3150;
		text-transform: uppercase;
		font-size: 12px;
		font-weight: 800;
		letter-spacing: 0.09em;
		margin: 0 0 8px;
	}
	.tabs {
		display: flex;
		gap: 20px;
		border-bottom: 1px solid #e7e1e2;
		margin-top: 28px;
	}
	.tabs button {
		border: 0;
		border-radius: 0;
		border-bottom: 3px solid transparent;
	}
	.tabs button.chosen {
		color: #df3150;
		border-color: #df3150;
	}
	.description {
		font-size: 17px;
		margin-top: 28px;
		white-space: pre-wrap;
	}
	.channel {
		background: #f8f7f6;
		border-radius: 8px;
		padding: 13px;
		font-weight: 650;
	}
	.row {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 10px;
		padding: 12px 0;
		border-bottom: 1px solid #eee;
	}
	.row span {
		margin-right: auto;
	}
	.danger {
		color: #b51b37;
		margin-top: 30px;
	}
	.error {
		padding: 12px;
		border-radius: 8px;
		background: #fff0f1;
		color: #a31630;
	}
	.empty {
		margin: 15vh auto;
		max-width: 420px;
		text-align: center;
	}
	.empty span {
		font-size: 50px;
		color: #df3150;
	}
	@media (max-width: 740px) {
		main {
			display: block;
		}
		.sidebar {
			border-right: 0;
			border-bottom: 1px solid #eee;
		}
		.content {
			padding: 28px 22px;
		}
		header {
			gap: 12px;
		}
	}
</style>
