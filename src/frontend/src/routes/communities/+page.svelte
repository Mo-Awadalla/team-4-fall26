<script lang="ts">
	import { base, resolve } from '$app/paths';
	import { onMount, tick } from 'svelte';
	import SiteHeader from '$lib/SiteHeader.svelte';
	import Autocomplete from '$lib/Autocomplete.svelte';
	import ChannelChat from '$lib/ChannelChat.svelte';
	import DirectMessages from '$lib/DirectMessages.svelte';
	import {
		communityRequest,
		type Channel,
		type Community,
		type DirectConversation,
		type GuestMember,
		type Invite,
		type Member
	} from '$lib/communities';
	import { session } from '$lib/session.svelte';

	let communities = $state<Community[]>([]);
	let selected = $state<Community | null>(null);
	let directConversations = $state<DirectConversation[]>([]);
	let selectedDM = $state<DirectConversation | null>(null);
	let members = $state<Member[]>([]);
	let guestMembers = $state<GuestMember[]>([]);
	let memberOffset = 0;
	let memberRequest = 0;
	let hasMoreMembers = $state(false);
	let membersLoading = $state(false);
	let guestCount = $state(0);
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
	let schools = $state<string[]>([]);
	let schoolsRequested = false;
	const popularSchools = [
		'New York University',
		'CUNY Hunter College',
		'CUNY Queens College',
		'Columbia University in the City of New York',
		'Cornell University',
		'Harvard University',
		'Massachusetts Institute of Technology',
		'Stanford University',
		'University of California-Berkeley',
		'University of California-Los Angeles',
		'University of Michigan-Ann Arbor'
	];
	const popularCourses = [
		'Calculus I',
		'Calculus II',
		'Linear Algebra',
		'Introduction to Statistics',
		'Introduction to Computer Science',
		'Data Structures',
		'General Biology',
		'General Chemistry',
		'Physics I',
		'Introduction to Psychology',
		'Microeconomics',
		'English Composition'
	];
	let courseOptions = $derived([
		...new Set([
			...communities
				.filter((community) => community.school === school && community.course)
				.map((community) => community.course),
			...popularCourses
		])
	]);
	let transferableMembers = $derived(
		members.filter((member) => member.user_id !== String(selected?.owner_id))
	);
	let channelName = $state('');
	let channelCreateOpen = $state(false);
	let channelMenuOpen = $state<number | null>(null);
	let editingChannelId = $state<number | null>(null);
	let renameValue = $state('');
	let deleteTarget = $state<Channel | null>(null);
	let channelNameInput = $state<HTMLInputElement>();
	let renameInput = $state<HTMLInputElement>();
	let deleteDialog = $state<HTMLDialogElement>();
	let activeChannelId = $state<number | null>(null);
	let inviteLink = $state('');
	let shareLink = $state('');
	let copyStatus = $state('');
	let tab = $state<'main' | 'members' | 'settings'>('main');
	let requestNumber = 0;
	const activeCommunityId = () => selected?.id;

	async function loadSchools() {
		if (schoolsRequested) return;
		schoolsRequested = true;
		try {
			const response = await fetch(`${base}/schools.json`);
			if (!response.ok) throw new Error('School suggestions are unavailable.');
			schools = await response.json();
		} catch {
			schoolsRequested = false;
		}
	}

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
				error = '';
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

	async function choose(id: number, channelId?: number | null) {
		error = '';
		try {
			selected = await communityRequest<Community>(`/communities/${id}`);
			selectedDM = null;
			channelCreateOpen = false;
			channelMenuOpen = null;
			editingChannelId = null;
			shareLink = '';
			copyStatus = '';
			activeChannelId =
				selected.channels?.find((channel) => channel.id === channelId)?.id ??
				selected.channels?.[0]?.id ??
				null;
			name = selected.name;
			description = selected.description;
			school = selected.school;
			course = selected.course;
			members = [];
			guestMembers = [];
			memberOffset = 0;
			hasMoreMembers = false;
			guestCount = 0;
			invites = [];
			tab = 'main';
			history.replaceState(
				null,
				'',
				`?id=${id}${activeChannelId ? `&channel=${activeChannelId}` : ''}`
			);
			void loadMembers();
		} catch (cause) {
			error = message(cause);
		}
	}

	async function loadDMs(): Promise<DirectConversation[]> {
		try {
			directConversations = (await communityRequest<{ items: DirectConversation[] }>('/dms')).items;
			return directConversations;
		} catch (cause) {
			error = message(cause);
			return [];
		}
	}

	function openDM(conversation: DirectConversation) {
		selectedDM = conversation;
		selected = null;
		creating = false;
		history.replaceState(null, '', `?dm=${conversation.id}`);
		void loadDMs();
	}

	function goHome() {
		selected = null;
		selectedDM = null;
		creating = false;
		history.replaceState(null, '', resolve('/communities'));
	}

	function showCreate() {
		goHome();
		creating = true;
		name = description = school = course = '';
	}

	async function startMemberDM(userId: string) {
		if (!selected) return;
		try {
			openDM(
				await communityRequest<DirectConversation>(`/communities/${selected.id}/dms`, 'POST', {
					user_id: userId
				})
			);
		} catch (cause) {
			error = message(cause);
		}
	}

	async function startGuestDM(guestMemberId: number) {
		if (!selected) return;
		try {
			openDM(
				await communityRequest<DirectConversation>(`/communities/${selected.id}/dms`, 'POST', {
					guest_member_id: guestMemberId
				})
			);
		} catch (cause) {
			error = message(cause);
		}
	}

	async function action(path: string, method = 'POST', body?: object) {
		error = '';
		try {
			await communityRequest(path, method, body);
			const previousTab = tab;
			const previousChannelId = activeChannelId;
			if (selected) {
				await choose(selected.id, previousChannelId);
				if (selected?.channels?.some((channel) => channel.id === previousChannelId))
					activeChannelId = previousChannelId;
				if (previousTab === 'members') {
					tab = 'members';
					await loadMembers();
				}
				if (previousTab === 'settings') await loadSettings();
			}
			await browse();
		} catch (cause) {
			error = message(cause);
		}
	}

	function selectChannel(channelId: number) {
		activeChannelId = channelId;
		channelMenuOpen = null;
		editingChannelId = null;
		shareLink = '';
		copyStatus = '';
		if (selected) history.replaceState(null, '', `?id=${selected.id}&channel=${channelId}`);
	}

	async function createChannel() {
		if (!selected) return;
		try {
			const created = await communityRequest<Channel>(
				`/communities/${selected.id}/channels`,
				'POST',
				{ name: channelName }
			);
			channelName = '';
			await choose(selected.id, created.id);
			await tick();
			document.getElementById(`channel-select-${created.id}`)?.focus();
		} catch (cause) {
			error = message(cause);
		}
	}

	async function openChannelCreate() {
		channelMenuOpen = null;
		channelCreateOpen = true;
		await tick();
		channelNameInput?.focus();
	}

	async function closeChannelCreate() {
		channelCreateOpen = false;
		await tick();
		document.getElementById('add-channel-button')?.focus();
	}

	async function toggleChannelMenu(channelId: number) {
		channelMenuOpen = channelMenuOpen === channelId ? null : channelId;
		if (channelMenuOpen !== null) {
			await tick();
			document.querySelector<HTMLButtonElement>(`#channel-options-${channelId} button`)?.focus();
		}
	}

	async function startChannelRename(channel: Channel) {
		selectChannel(channel.id);
		editingChannelId = channel.id;
		renameValue = channel.name;
		await tick();
		renameInput?.focus();
	}

	async function cancelChannelRename(channelId: number) {
		editingChannelId = null;
		await tick();
		(
			document.getElementById(`edit-channel-${channelId}`) ??
			document.getElementById(`channel-trigger-${channelId}`)
		)?.focus();
	}

	async function renameChannel(channel: Channel) {
		if (!selected) return;
		try {
			await communityRequest(`/communities/${selected.id}/channels/${channel.id}`, 'PATCH', {
				name: renameValue
			});
			await choose(selected.id, activeChannelId);
			await tick();
			document.getElementById(`edit-channel-${channel.id}`)?.focus();
		} catch (cause) {
			error = message(cause);
		}
	}

	async function updateChannel(channelId: number, changes: object) {
		await action(`/communities/${activeCommunityId()}/channels/${channelId}`, 'PATCH', changes);
		await tick();
		document.getElementById(`channel-trigger-${channelId}`)?.focus();
	}

	async function confirmChannelDelete(channel: Channel) {
		channelMenuOpen = null;
		deleteTarget = channel;
		await tick();
		deleteDialog?.showModal();
	}

	async function deleteChannel() {
		if (!selected || !deleteTarget) return;
		const channelId = deleteTarget.id;
		deleteDialog?.close();
		deleteTarget = null;
		await action(`/communities/${selected.id}/channels/${channelId}`, 'DELETE');
		await tick();
		if (activeChannelId) document.getElementById(`channel-select-${activeChannelId}`)?.focus();
	}

	async function closeDeleteDialog() {
		const channelId = deleteTarget?.id;
		deleteTarget = null;
		await tick();
		if (channelId) document.getElementById(`channel-trigger-${channelId}`)?.focus();
	}

	function handleEscape(event: KeyboardEvent) {
		if (event.key !== 'Escape' || deleteDialog?.open) return;
		if (channelMenuOpen !== null) {
			const channelId = channelMenuOpen;
			channelMenuOpen = null;
			void tick().then(() => document.getElementById(`channel-trigger-${channelId}`)?.focus());
		} else if (editingChannelId !== null) void cancelChannelRename(editingChannelId);
		else if (channelCreateOpen) void closeChannelCreate();
	}

	async function shareChannel() {
		if (!selected || !activeChannelId) return;
		shareLink = `${location.origin}${resolve('/communities')}?id=${selected.id}&channel=${activeChannelId}`;
		try {
			await navigator.clipboard.writeText(shareLink);
			copyStatus = 'Channel link copied. Anyone can use it to join this public community.';
		} catch {
			copyStatus = 'Select and copy the link below to share this channel.';
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
		if (more && membersLoading) return;
		const current = ++memberRequest;
		const communityId = selected.id;
		const offset = more ? memberOffset : 0;
		membersLoading = true;
		try {
			const result = await communityRequest<{
				items: Member[];
				has_more: boolean;
				guest_items: GuestMember[];
				guest_has_more: boolean;
				guest_count: number;
			}>(`/communities/${communityId}/members?limit=50&offset=${offset}`);
			if (selected?.id !== communityId || current !== memberRequest) return;
			members = more ? [...members, ...result.items] : result.items;
			guestMembers = more ? [...guestMembers, ...result.guest_items] : result.guest_items;
			memberOffset = offset + 50;
			hasMoreMembers = result.has_more || result.guest_has_more;
			guestCount = result.guest_count;
			error = '';
		} catch (cause) {
			if (selected?.id === communityId && current === memberRequest) error = message(cause);
		} finally {
			if (selected?.id === communityId && current === memberRequest) membersLoading = false;
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
		void session.status;
		void browse(query, false, viewMine);
	});

	onMount(() => {
		const dmId = Number(new URL(location.href).searchParams.get('dm'));
		void session.start().then(async () => {
			if (selected) void choose(selected.id, activeChannelId);
			const items = await loadDMs();
			const conversation = items.find((item) => item.id === dmId);
			if (conversation) openDM(conversation);
		});
		const url = new URL(location.href);
		const id = Number(url.searchParams.get('id'));
		const channelId = Number(url.searchParams.get('channel'));
		const requestedChannel = Number.isSafeInteger(channelId) && channelId > 0 ? channelId : null;
		if (Number.isSafeInteger(id) && id > 0) void choose(id, requestedChannel);
		const token = url.searchParams.get('invite');
		if (token) {
			void communityRequest<{ community_id: number }>(
				`/communities/invites/${encodeURIComponent(token)}/redeem`,
				'POST'
			)
				.then((result) => choose(result.community_id, requestedChannel))
				.catch((cause) => {
					error = message(cause);
				});
		}
	});
</script>

<svelte:window onkeydown={handleEscape} />

<svelte:head>
	<title>Communities · StudySpot</title>
	<meta name="description" content="Find and create public study communities in New York City." />
</svelte:head>

<div class="shell">
	<SiteHeader />
	<dialog
		bind:this={deleteDialog}
		class="confirm-dialog"
		aria-labelledby="delete-channel-title"
		aria-describedby="delete-channel-description"
		onclose={() => void closeDeleteDialog()}
	>
		{#if deleteTarget}
			<h2 id="delete-channel-title">Delete #{deleteTarget.name}?</h2>
			<p id="delete-channel-description">
				This removes the channel and its messages for everyone in the community.
			</p>
			<div class="form-actions">
				<button onclick={() => deleteDialog?.close()}>Cancel</button><button
					class="destructive"
					onclick={() => void deleteChannel()}>Delete channel</button
				>
			</div>
		{/if}
	</dialog>
	<main>
		<aside class="sidebar">
			<h1><button class="home-link" onclick={goHome}>Communities</button></h1>
			<p>Public study communities for courses, schools, and neighborhoods.</p>
			<label for="community-search">Search communities</label>
			<div class="tabs">
				<button class:chosen={!viewMine} aria-pressed={!viewMine} onclick={() => (viewMine = false)}
					>All</button
				><button class:chosen={viewMine} aria-pressed={viewMine} onclick={() => (viewMine = true)}
					>Mine</button
				>
			</div>
			<input id="community-search" bind:value={query} placeholder="Math 51A, NYU, Brooklyn…" />
			<button class="primary" onclick={showCreate}>+ Create community</button>
			{#if loading}<p class="muted">Loading…</p>{/if}
			<div class="list">
				{#each communities as community (community.id)}
					<button
						class:active={selected?.id === community.id}
						aria-current={selected?.id === community.id ? 'page' : undefined}
						onclick={() => void choose(community.id)}
					>
						<strong>{community.name}</strong>
						<span
							>{community.course || community.school || 'Study community'} · {community.member_count}
							{community.member_count === 1 ? 'member' : 'members'}</span
						>
					</button>
				{/each}
			</div>
			{#if hasMore}<button onclick={() => void browse(query, true)}>Show more</button>{/if}
			<h2 class="dm-heading">Direct messages</h2>
			<div class="list">
				{#each directConversations as conversation (conversation.id)}
					<button
						class:active={selectedDM?.id === conversation.id}
						aria-current={selectedDM?.id === conversation.id ? 'page' : undefined}
						onclick={() => openDM(conversation)}
						><strong>{conversation.other_name}</strong><span>Private conversation</span></button
					>
				{:else}<p class="muted">Message a community member to start.</p>{/each}
			</div>
		</aside>
		<section class="content">
			{#if error}<p class="error" role="alert">{error}</p>{/if}
			{#if creating}
				<h2>Create a community</h2>
				<p class="muted">Anyone can create a public community without signing in.</p>
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
					<Autocomplete
						id="create-school"
						label="School"
						bind:value={school}
						options={schools}
						popular={popularSchools}
						placeholder="Search US schools"
						help="Choose a school or type another name."
						onOpen={() => void loadSchools()}
					/>
					<Autocomplete
						id="create-course"
						label="Course"
						bind:value={course}
						options={courseOptions}
						popular={courseOptions}
						placeholder="Search courses or enter a code"
						help="Course codes vary by school; you can enter yours."
					/>
					<div class="form-actions">
						<button class="primary">Create community</button><button type="button" onclick={goHome}
							>Cancel</button
						>
					</div>
				</form>
			{:else if selectedDM}
				<DirectMessages conversation={selectedDM} />
			{:else if selected}
				<div class="title">
					<div>
						<p class="eyebrow">
							Public community · {selected.member_count}
							{selected.member_count === 1 ? 'member' : 'members'}
						</p>
						<h2>{selected.name}</h2>
						<p>{[selected.school, selected.course].filter(Boolean).join(' · ')}</p>
					</div>
					{#if selected.role === 'visitor'}<button
							class="primary"
							onclick={() => void action(`/communities/${activeCommunityId()}/join`)}
							>Join community</button
						>
					{:else if selected.role === 'owner'}<span class="muted"
							>Joined · You own this community</span
						>
					{:else}<span class="muted">Joined</span><button
							onclick={() => void action(`/communities/${activeCommunityId()}/leave`)}>Leave</button
						>{/if}
				</div>
				<div class="tabs">
					<button
						class:chosen={tab === 'main'}
						aria-pressed={tab === 'main'}
						onclick={() => (tab = 'main')}>Main</button
					><button
						class:chosen={tab === 'members'}
						aria-pressed={tab === 'members'}
						onclick={() => {
							tab = 'members';
							void loadMembers();
						}}>Members ({selected.member_count})</button
					>{#if selected.role === 'owner' || selected.role === 'moderator'}<button
							class:chosen={tab === 'settings'}
							aria-pressed={tab === 'settings'}
							onclick={() => void loadSettings()}>Manage</button
						>{/if}
				</div>
				{#if tab === 'main'}
					<div class="workspace">
						<nav class="channel-rail" aria-label={`Channels in ${selected.name}`}>
							<div class="rail-heading">
								<h3>Channels <span>{selected.channels?.length ?? 0}/20</span></h3>
								{#if selected.role === 'owner'}<button
										class="icon-button"
										id="add-channel-button"
										aria-label="Add channel"
										title={(selected.channels?.length ?? 0) >= 20
											? 'Channel limit reached'
											: 'Add channel'}
										disabled={(selected.channels?.length ?? 0) >= 20}
										onclick={() => void openChannelCreate()}>+</button
									>{/if}
							</div>
							{#if channelCreateOpen}
								<form
									class="channel-form"
									onsubmit={(event) => {
										event.preventDefault();
										void createChannel();
									}}
								>
									<label for="new-channel-name">Channel name</label>
									<input
										id="new-channel-name"
										bind:this={channelNameInput}
										required
										pattern="[a-z0-9][a-z0-9-]*"
										maxlength="50"
										bind:value={channelName}
										placeholder="exam-prep"
										aria-describedby="channel-name-help"
									/>
									<p id="channel-name-help">Lowercase letters, numbers, and hyphens.</p>
									<div class="form-actions">
										<button class="primary">Create</button><button
											type="button"
											onclick={() => void closeChannelCreate()}>Cancel</button
										>
									</div>
								</form>
							{/if}
							<ul class="channel-list">
								{#each selected.channels ?? [] as channel (channel.id)}
									<li class="channel-item">
										<div class="channel-row" class:active={activeChannelId === channel.id}>
											<button
												class="channel-select"
												id={`channel-select-${channel.id}`}
												aria-current={activeChannelId === channel.id ? 'page' : undefined}
												onclick={() => selectChannel(channel.id)}
												><span aria-hidden="true">#</span><span
													>{channel.name}{channel.archived ? ' · Archived' : ''}</span
												></button
											>
											{#if selected.role === 'owner'}<button
													class="icon-button options-trigger"
													id={`channel-trigger-${channel.id}`}
													aria-label={`Options for #${channel.name}`}
													aria-expanded={channelMenuOpen === channel.id}
													aria-controls={`channel-options-${channel.id}`}
													onclick={() => void toggleChannelMenu(channel.id)}>···</button
												>{/if}
										</div>
										{#if channelMenuOpen === channel.id}
											<div
												class="channel-options"
												id={`channel-options-${channel.id}`}
												role="group"
												aria-label={`Options for #${channel.name}`}
											>
												<button onclick={() => void startChannelRename(channel)}>Rename</button>
												<button
													disabled={channel.position === 0}
													onclick={() =>
														void updateChannel(channel.id, { position: channel.position - 1 })}
													>Move up</button
												>
												<button
													disabled={channel.position >= (selected.channels?.length ?? 0) - 1}
													onclick={() =>
														void updateChannel(channel.id, { position: channel.position + 1 })}
													>Move down</button
												>
												<button
													onclick={() =>
														void updateChannel(channel.id, { archived: !channel.archived })}
													>{channel.archived ? 'Restore' : 'Archive'}</button
												>
												<button
													class="destructive"
													onclick={() => void confirmChannelDelete(channel)}>Delete channel</button
												>
											</div>
										{/if}
									</li>
								{/each}
							</ul>
							{#if selected.role !== 'owner'}<p class="rail-note">
									The community owner manages channels.
								</p>{/if}
						</nav>
						<div class="workspace-main">
							{#each selected.channels?.filter((channel) => channel.id === activeChannelId) ?? [] as channel (channel.id)}
								<div class="channel-pane">
									<div class="channel-intro">
										<div>
											<p class="eyebrow">Text channel</p>
											<h3># {channel.name}</h3>
											<p>
												{channel.archived
													? 'Archived · Read only'
													: selected.description || 'A place to study together.'}
											</p>
										</div>
										<div class="channel-actions">
											{#if selected.role === 'owner'}<button
													id={`edit-channel-${channel.id}`}
													onclick={() => void startChannelRename(channel)}>Edit channel</button
												>{/if}
											<button onclick={() => void shareChannel()}>Share channel</button>
										</div>
									</div>
									{#if editingChannelId === channel.id}
										<form
											class="channel-edit"
											onsubmit={(event) => {
												event.preventDefault();
												void renameChannel(channel);
											}}
										>
											<label for={`rename-channel-${channel.id}`}>Channel name</label>
											<input
												id={`rename-channel-${channel.id}`}
												bind:this={renameInput}
												required
												pattern="[a-z0-9][a-z0-9-]*"
												maxlength="50"
												bind:value={renameValue}
											/>
											<div class="form-actions">
												<button class="primary">Save name</button>
												<button type="button" onclick={() => void cancelChannelRename(channel.id)}
													>Cancel</button
												>
												<button
													type="button"
													onclick={() =>
														void updateChannel(channel.id, { archived: !channel.archived })}
													>{channel.archived ? 'Restore channel' : 'Archive channel'}</button
												>
												<button
													type="button"
													class="destructive"
													onclick={() => void confirmChannelDelete(channel)}>Delete channel</button
												>
											</div>
										</form>
									{/if}
									{#if copyStatus}<p class="copy-status" role="status">{copyStatus}</p>{/if}
									{#if shareLink}<input
											class="share-link"
											readonly
											aria-label="Channel invite link"
											value={shareLink}
											onclick={(event) => event.currentTarget.select()}
										/>{/if}
									{#if selected.role === 'visitor'}<div class="join-prompt">
											<h4>Join to take part</h4>
											<p>
												Join this public community to read and send messages in #{channel.name}.
											</p>
											<button
												class="primary"
												onclick={() => void action(`/communities/${activeCommunityId()}/join`)}
												>Join community</button
											>
										</div>
									{:else}<ChannelChat
											communityId={selected.id}
											{channel}
											role={selected.role}
											onDirectMessage={openDM}
										/>{/if}
								</div>
							{:else}
								<div class="channel-empty">
									<h3>No channels yet</h3>
									<p>Create a channel to start organizing conversations.</p>
									{#if selected.role === 'owner'}<button
											class="primary"
											onclick={() => void openChannelCreate()}>Add channel</button
										>{/if}
								</div>
							{/each}
						</div>
						<aside class="member-rail" aria-label={`Members of ${selected.name}`}>
							<button
								class="member-heading"
								onclick={() => {
									tab = 'members';
									void loadMembers();
								}}>Members <span>{selected.member_count}</span></button
							>
							{#if membersLoading && !members.length && !guestMembers.length}<p class="muted">
									Loading members…
								</p>{/if}
							{#each members as member (member.user_id)}
								<div class="member-mini">
									<strong>{member.is_me ? 'You' : member.display_name}</strong><span
										>{member.user_id === String(selected.owner_id) ? 'Owner' : member.role}</span
									>
									{#if !member.is_me && selected.role !== 'visitor'}<button
											onclick={() => void startMemberDM(member.user_id)}>Message</button
										>{/if}
								</div>
							{/each}
							{#each guestMembers as guest (guest.id)}
								<div class="member-mini">
									<strong>{guest.is_me ? 'You' : guest.display_name}</strong><span
										>{guest.role === 'owner' ? 'Owner' : 'Guest member'}</span
									>
									{#if !guest.is_me && selected.role !== 'visitor'}<button
											onclick={() => void startGuestDM(guest.id)}>Message</button
										>{/if}
								</div>
							{/each}
							{#if hasMoreMembers}<button
									class="more-members"
									onclick={() => void loadMembers(true)}>Show more members</button
								>{/if}
						</aside>
					</div>
				{:else if tab === 'members'}
					<h3>Members · {selected.member_count}</h3>
					<p class="muted">
						Everyone in this community, including {guestCount}
						{guestCount === 1 ? 'guest member' : 'guest members'}.
					</p>
					{#if membersLoading && !members.length && !guestMembers.length}<p class="muted">
							Loading members…
						</p>{/if}
					{#each members as member (member.user_id)}<div class="row">
							<span
								>{member.is_me ? 'You' : member.display_name}
								{member.user_id === String(selected.owner_id)
									? '· Owner'
									: `· ${member.role}`}</span
							>
							{#if !member.is_me && selected.role !== 'visitor'}<button
									onclick={() => void startMemberDM(member.user_id)}>Message privately</button
								>{/if}
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
					{#each guestMembers as guest (guest.id)}
						<div class="row">
							<span
								>{guest.is_me ? 'You' : guest.display_name} · {guest.role === 'owner'
									? 'Owner'
									: 'Guest member'}</span
							>
							{#if !guest.is_me && selected.role !== 'visitor'}<button
									onclick={() => void startGuestDM(guest.id)}>Message privately</button
								>{/if}
						</div>
					{/each}
					{#if hasMoreMembers}<button onclick={() => void loadMembers(true)}
							>Show more members</button
						>{/if}
					{#if selected.role === 'owner' && transferableMembers.length}<p class="muted">
							Transfer ownership to an account member:
						</p>
						<form
							onsubmit={(event) => {
								event.preventDefault();
								const target = event.currentTarget.querySelector('select');
								if (target)
									void action(`/communities/${activeCommunityId()}/transfer`, 'POST', {
										user_id: target.value
									});
							}}
						>
							<select required aria-label="New owner">
								<option value="" disabled selected>Choose a member</option>
								{#each transferableMembers as member (member.user_id)}<option value={member.user_id}
										>{member.display_name}</option
									>{/each}
							</select><button>Transfer ownership</button>
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
							><Autocomplete
								id="edit-school"
								label="School"
								bind:value={school}
								options={schools}
								popular={popularSchools}
								placeholder="Search US schools"
								help="Choose a school or type another name."
								onOpen={() => void loadSchools()}
							/><Autocomplete
								id="edit-course"
								label="Course"
								bind:value={course}
								options={courseOptions}
								popular={courseOptions}
								placeholder="Search courses or enter a code"
								help="Course codes vary by school; you can enter yours."
							/><button>Save details</button>
						</form>
						<button class="danger" onclick={() => void deleteCommunity()}>Delete community</button>
					{/if}
				{/if}
			{:else}
				<div class="landing">
					<p class="eyebrow">StudySpot communities</p>
					<h2>Find your people. Make progress together.</h2>
					<p class="landing-lead">
						Join a public study group, pick a channel, and start talking. Or make a space for the
						course you are working through.
					</p>
					<div class="landing-actions">
						<button class="primary" onclick={showCreate}>Create a community</button><button
							onclick={() => document.getElementById('community-search')?.focus()}
							>Search communities</button
						>
					</div>
					<div class="landing-feature">
						<span aria-hidden="true">#</span>
						<div>
							<strong>One place for every conversation</strong>
							<p>
								Keep homework, exam prep, and plans in separate channels. Share a link so classmates
								can join.
							</p>
						</div>
					</div>
					<h3>Explore communities</h3>
					<div class="community-grid">
						{#each communities.slice(0, 6) as community (community.id)}
							<button onclick={() => void choose(community.id)}>
								<span class="community-mark" aria-hidden="true">#</span>
								<strong>{community.name}</strong>
								<span
									>{[community.school, community.course].filter(Boolean).join(' · ') ||
										'Open study community'}</span
								>
								<small
									>{community.member_count}
									{community.member_count === 1 ? 'member' : 'members'} · Public</small
								>
							</button>
						{:else}<p class="muted">No communities match yet. Start one for your class.</p>{/each}
					</div>
				</div>
			{/if}
		</section>
	</main>
</div>

<style>
	.shell {
		min-height: 100vh;
		background: #f8f5f6;
		color: #262526;
		--accent: #a51d3d;
	}
	main {
		max-width: 1440px;
		height: calc(100vh - 76px);
		min-height: 620px;
		margin: auto;
		display: grid;
		grid-template-columns: 280px minmax(0, 1fr);
		background: white;
		border: 1px solid #eadfe3;
		border-radius: 16px 16px 0 0;
		box-shadow: 0 12px 40px rgb(45 22 31 / 5%);
	}
	.sidebar {
		background: #fcf7f8;
		padding: 32px 22px;
		border-right: 1px solid #eadfe3;
		overflow-y: auto;
	}
	h1 {
		font-size: 29px;
		line-height: 1.1;
		letter-spacing: -0.05em;
		margin: 0 0 12px;
	}
	.home-link {
		border: 0;
		background: transparent;
		padding: 0;
		min-height: 0;
		font: inherit;
		letter-spacing: inherit;
		text-align: left;
	}
	h2 {
		font-size: 33px;
		letter-spacing: -0.05em;
		margin: 0 0 8px;
	}
	.dm-heading {
		font-size: 18px;
		margin: 30px 0 12px;
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
	textarea,
	select {
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
		min-height: 40px;
		font: inherit;
		font-weight: 650;
	}
	button:hover {
		border-color: var(--accent);
	}
	button:focus-visible,
	input:focus-visible,
	textarea:focus-visible,
	select:focus-visible {
		outline: 3px solid #2458a6;
		outline-offset: 2px;
	}
	button:disabled {
		cursor: default;
		opacity: 0.55;
	}
	button:disabled:hover {
		border-color: #ddd2d5;
	}
	.primary {
		background: var(--accent);
		color: white;
		border-color: var(--accent);
	}
	.sidebar > .primary {
		width: 100%;
		margin: 14px 0 20px;
		white-space: nowrap;
		font-size: 14px;
		padding-inline: 8px;
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
		background: #f8e0e7;
	}
	.list span {
		font-size: 13px;
		color: #746c70;
		font-weight: 400;
	}
	.content {
		display: flex;
		flex-direction: column;
		padding: 36px;
		min-width: 0;
		min-height: 0;
		overflow-y: auto;
	}
	.title {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 16px;
	}
	.eyebrow {
		color: var(--accent);
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
		color: var(--accent);
		border-color: var(--accent);
	}
	.workspace {
		display: grid;
		grid-template-columns: 190px minmax(0, 1fr) 190px;
		flex: 1;
		min-height: 0;
		margin-top: 24px;
		border: 1px solid #eadfe3;
		border-radius: 14px;
	}
	.channel-rail {
		min-width: 0;
		padding: 16px 10px;
		background: #fbf7f8;
		border-right: 1px solid #eadfe3;
		border-radius: 14px 0 0 14px;
	}
	.rail-heading {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 7px;
	}
	.rail-heading h3 {
		display: flex;
		gap: 4px;
		white-space: nowrap;
		font-size: 12px;
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: #56464e;
	}
	.rail-heading h3 span {
		font-weight: 500;
		font-size: 11px;
		color: #82727a;
	}
	.icon-button {
		display: inline-grid;
		place-items: center;
		min-width: 40px;
		padding: 0;
		font-size: 22px;
		line-height: 1;
	}
	.channel-list {
		list-style: none;
		display: grid;
		gap: 4px;
		margin: 12px 0 0;
		padding: 0;
	}
	.rail-note {
		padding: 0 8px;
		color: #746c70;
		font-size: 12px;
	}
	.channel-item {
		position: relative;
		min-width: 0;
	}
	.channel-row {
		display: flex;
		align-items: center;
		border-radius: 8px;
	}
	.channel-row:hover,
	.channel-row.active {
		background: #f6dfe6;
	}
	.channel-select {
		flex: 1;
		display: flex;
		gap: 6px;
		align-items: center;
		min-width: 0;
		text-align: left;
		background: transparent;
		border: 0;
		font-weight: 600;
		font-size: 14px;
	}
	.channel-select span:last-child {
		overflow-wrap: anywhere;
	}
	.channel-select span:first-child {
		color: #866e77;
		font-size: 19px;
	}
	.options-trigger {
		flex: 0 0 40px;
		border: 0;
		background: transparent;
		font-size: 20px;
		letter-spacing: 1px;
	}
	.channel-options {
		position: absolute;
		top: 42px;
		right: 0;
		z-index: 5;
		display: grid;
		width: 174px;
		padding: 6px;
		background: white;
		border: 1px solid #d9cbd0;
		border-radius: 10px;
		box-shadow: 0 12px 28px rgb(43 20 30 / 16%);
	}
	.channel-options button {
		min-height: 40px;
		text-align: left;
		border: 0;
		background: transparent;
	}
	.channel-options button:hover {
		background: #f8e9ed;
	}
	.destructive {
		color: #a31630;
	}
	.channel-form {
		margin: 12px 4px;
		padding: 12px;
		border: 1px solid #e3d5da;
		border-radius: 10px;
		background: white;
	}
	.channel-form label {
		margin: 0 0 6px;
	}
	.channel-form p {
		margin: 6px 0 0;
		font-size: 12px;
		color: #65585d;
	}
	.form-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-top: 12px;
	}
	.workspace-main {
		display: flex;
		flex-direction: column;
		min-width: 0;
		min-height: 0;
		padding: 16px;
		overflow-y: auto;
	}
	.channel-pane {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
	}
	.channel-empty {
		margin: auto;
		text-align: center;
	}
	.channel-empty p {
		color: #65585d;
	}
	.channel-intro {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 14px;
	}
	.channel-intro h3 {
		margin: 0;
		font-size: 24px;
	}
	.channel-intro p {
		margin: 5px 0 0;
		color: #665b60;
	}
	.channel-intro .eyebrow {
		margin: 0 0 4px;
		color: var(--accent);
	}
	.channel-intro button {
		white-space: nowrap;
	}
	.channel-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.channel-edit {
		padding: 12px;
		margin-top: 12px;
		background: #fff9fa;
		border: 1px solid #e8d7dd;
		border-radius: 10px;
	}
	.channel-edit label {
		margin-top: 0;
	}
	.member-rail {
		min-width: 0;
		padding: 16px 12px;
		overflow-y: auto;
		border-left: 1px solid #eadfe3;
		background: #fcfafb;
		border-radius: 0 14px 14px 0;
	}
	.member-heading {
		width: 100%;
		padding: 4px;
		border: 0;
		background: transparent;
		text-align: left;
		text-transform: uppercase;
		font-size: 13px;
		letter-spacing: 0.06em;
	}
	.member-heading span {
		color: #746c70;
	}
	.member-mini {
		display: grid;
		gap: 4px;
		padding: 12px 4px;
		border-bottom: 1px solid #eee4e7;
		font-size: 13px;
	}
	.member-mini strong {
		overflow-wrap: anywhere;
	}
	.member-mini span {
		color: #746c70;
	}
	.member-mini button,
	.more-members {
		justify-self: start;
		min-height: 32px;
		padding: 4px 8px;
		font-size: 12px;
	}
	.more-members {
		margin-top: 10px;
	}
	.copy-status {
		color: #285736;
		font-size: 14px;
	}
	.share-link {
		margin-top: 8px;
	}
	.join-prompt {
		margin-top: 24px;
		padding: 24px;
		background: #fbf5f7;
		border: 1px solid #eadfe3;
		border-radius: 12px;
	}
	.join-prompt h4 {
		margin: 0;
		font-size: 19px;
	}
	.join-prompt p {
		color: #65585d;
	}
	.confirm-dialog {
		width: min(420px, calc(100vw - 32px));
		padding: 24px;
		border: 1px solid #decfd4;
		border-radius: 16px;
		box-shadow: 0 20px 60px rgb(32 13 22 / 24%);
	}
	.confirm-dialog::backdrop {
		background: rgb(31 18 24 / 55%);
	}
	.confirm-dialog h2 {
		font-size: 24px;
	}
	.confirm-dialog p {
		color: #65585d;
	}
	.confirm-dialog .destructive {
		background: #a31630;
		border-color: #a31630;
		color: white;
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
	.landing {
		max-width: 960px;
		margin: auto 0;
	}
	.landing h2 {
		max-width: 690px;
		font-size: clamp(38px, 5vw, 62px);
		line-height: 1.05;
	}
	.landing-lead {
		max-width: 620px;
		color: #65585d;
		font-size: 17px;
	}
	.landing-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
		margin: 22px 0;
	}
	.landing-feature {
		display: flex;
		gap: 16px;
		padding: 18px;
		background: #fbf4f6;
		border: 1px solid #eadfe3;
		border-radius: 12px;
	}
	.landing-feature > span {
		color: var(--accent);
		font-size: 32px;
	}
	.landing-feature p {
		margin: 4px 0 0;
		color: #65585d;
	}
	.community-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
	}
	.community-grid button {
		display: grid;
		gap: 6px;
		text-align: left;
		padding: 16px;
	}
	.community-grid button:hover {
		background: #fff7f9;
	}
	.community-mark {
		color: var(--accent);
		font-size: 25px;
	}
	.community-grid button span:not(.community-mark),
	.community-grid small {
		color: #65585d;
		font-size: 13px;
	}
	@media (max-width: 1200px) {
		main {
			grid-template-columns: 240px minmax(0, 1fr);
		}
		.workspace {
			grid-template-columns: 165px minmax(0, 1fr) 160px;
		}
	}
	@media (max-width: 1050px) {
		.content {
			padding: 24px;
		}
	}
	@media (max-width: 980px) {
		.workspace {
			grid-template-columns: 180px minmax(0, 1fr);
		}
		.member-rail {
			display: none;
		}
	}
	@media (max-width: 850px) {
		main {
			height: auto;
		}
		.workspace {
			display: block;
			flex: none;
			min-height: 480px;
		}
		.channel-rail {
			border-right: 0;
			border-bottom: 1px solid #eadfe3;
			border-radius: 14px 14px 0 0;
		}
		.channel-intro {
			flex-wrap: wrap;
		}
		.workspace-main {
			min-height: 400px;
		}
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
		.title {
			flex-wrap: wrap;
		}
		.tabs {
			overflow-x: auto;
		}
		.workspace-main {
			padding: 14px;
		}
		.community-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
