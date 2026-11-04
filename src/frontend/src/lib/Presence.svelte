<script lang="ts">
	import { onMount } from 'svelte';
	import { communityRequest } from './communities';
	let {
		url,
		onread,
		ontyping
	}: { url: string; onread?: (id: number) => void; ontyping: (names: string[]) => void } = $props();
	let mode = $state('all'),
		notice = $state('');
	async function setMode(alerts: string) {
		try {
			await communityRequest(url.replace(/presence$/, 'alerts'), 'PUT', { alerts });
			mode = alerts;
			notice = '';
		} catch (e) {
			notice = e instanceof Error ? e.message : 'Save failed';
		}
	}
	let lastSignal = 0,
		lastActive = 0;
	export function typing() {
		if (Date.now() - lastSignal < 3000) return;
		lastSignal = Date.now();
		void signal({ typing: true });
	}
	async function signal(body: object) {
		try {
			await communityRequest(url, 'POST', body);
		} catch {
			ontyping([]);
		}
	}
	onMount(() => {
		let busy = false,
			closed = false;
		async function poll() {
			if (document.hidden || busy) return;
			busy = true;
			try {
				if (Date.now() - lastActive > 30000) {
					lastActive = Date.now();
					await signal({});
				}
				const data = await communityRequest<{
					typing: string[];
					alerts: string;
					last_read: number;
				}>(url);
				if (!closed) {
					ontyping(data.typing);
					mode = data.alerts;
					onread?.(data.last_read);
				}
			} catch {
				ontyping([]);
			} finally {
				busy = false;
			}
		}
		void poll();
		const timer = setInterval(poll, 3000);
		return () => {
			closed = true;
			clearInterval(timer);
		};
	});
</script>

<label
	>Notifications<select value={mode} onchange={(e) => void setMode(e.currentTarget.value)}
		><option value="all">All messages</option><option value="mentions">Mentions only</option><option
			value="muted">Muted</option
		></select
	></label
>{#if notice}<span role="alert">{notice}</span>{/if}
