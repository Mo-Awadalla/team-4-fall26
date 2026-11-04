import MarkdownIt from 'markdown-it';

const markdown = new MarkdownIt({ html: false, breaks: true }).disable('image');
// Transform only ordinary text tokens. Code spans and fenced blocks keep literal pipes.
markdown.renderer.rules.text = (tokens, index) =>
	markdown.utils
		.escapeHtml(tokens[index].content)
		.replace(
			/\|\|([^|]+?)\|\|/gs,
			(_, hidden: string) =>
				'<details class="spoiler"><summary>Spoiler</summary>' + hidden + '</details>'
		);
export const renderMessage = (content: string) => markdown.render(content);
