<script lang="ts">
	import { communityRequest } from './communities';
	let {
		url,
		onresults,
		onerror
	}: {
		url: string;
		onresults: (
			items: { id: number; created_at: string; author_name: string; content: string }[]
		) => void;
		onerror: (message: string) => void;
	} = $props();
	let keyword = $state(''),
		sender = $state(''),
		date = $state('');
	async function search() {
		const params = new URLSearchParams();
		if (keyword.trim()) params.set('q', keyword.trim());
		if (sender.trim()) params.set('sender', sender.trim());
		if (date) params.set('date', date);
		try {
			const result = await communityRequest<{
				items: { id: number; created_at: string; author_name: string; content: string }[];
			}>(url + '?' + params);
			onresults(result.items);
		} catch (e) {
			onerror(e instanceof Error ? e.message : 'Search failed.');
		}
	}
</script>

<form
	onsubmit={(e) => {
		e.preventDefault();
		void search();
	}}
>
	<input aria-label="Keyword" placeholder="Keyword" minlength="2" bind:value={keyword} />
	<input aria-label="Sender" placeholder="Exact sender name" bind:value={sender} />
	<input aria-label="Date (UTC)" type="date" bind:value={date} />
	<button disabled={!keyword.trim() && !sender.trim() && !date}>Search</button>
</form>
