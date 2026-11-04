import MarkdownIt from 'markdown-it';

const markdown = new MarkdownIt({ html: false, breaks: true }).disable('image');
markdown.inline.ruler.before('emphasis', 'spoiler', (state, silent) => {
	if (!state.src.startsWith('||', state.pos)) return false;
	const end = state.src.indexOf('||', state.pos + 2);
	if (end <= state.pos + 2 || end >= state.posMax) return false;
	if (!silent) {
		const token = state.push('spoiler', '', 0);
		token.content = state.src.slice(state.pos + 2, end);
	}
	state.pos = end + 2;
	return true;
});
markdown.renderer.rules.spoiler = (tokens, index) =>
	'<details class="spoiler"><summary>Spoiler</summary>' +
	markdown.utils.escapeHtml(tokens[index].content) +
	'</details>';
export const renderMessage = (content: string) => markdown.render(content);
