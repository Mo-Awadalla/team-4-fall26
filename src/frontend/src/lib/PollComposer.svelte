<script lang="ts">
	import { communityRequest } from './communities';
	let { url, onsent }: { url: string; onsent: () => void } = $props();
	let question = $state(''),
		choices = $state(''),
		error = $state(''),
		busy = $state(false),
		opened = $state(false);
	async function create() {
		if (busy) return;
		busy = true;
		try {
			await communityRequest(url, 'POST', {
				content: question,
				options: choices
					.split('\n')
					.map((s) => s.trim())
					.filter(Boolean)
			});
			question = choices = error = '';
			opened = false;
			onsent();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Poll failed';
		} finally {
			busy = false;
		}
	}
</script>

<details bind:open={opened}>
	<summary>Create poll</summary><label
		>Question<input bind:value={question} maxlength="2000" /></label
	><label>Choices (one per line)<textarea bind:value={choices}></textarea></label><button
		type="button"
		disabled={busy || !question.trim()}
		onclick={create}>Post poll</button
	>{#if error}<span role="alert">{error}</span>{/if}
</details>
