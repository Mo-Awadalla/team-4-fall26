<script lang="ts">
	let {
		names,
		groups = false,
		onpick
	}: { names: string[]; groups?: boolean; onpick: (text: string) => void } = $props();
</script>

<label
	>Mention
	<select
		onchange={(e) => {
			const s = e.currentTarget;
			if (s.value) onpick(s.value);
			s.selectedIndex = 0;
		}}
	>
		<option value="">@</option>
		{#each [...new Set(names)] as name (name)}<option value={'@[' + name + ']'}>{name}</option
			>{/each}
		{#if groups}{#each ['owner', 'moderator', 'member', 'here', 'everyone'] as role (role)}<option
					value={'@' + role}>@{role}</option
				>{/each}{/if}
	</select></label
>
