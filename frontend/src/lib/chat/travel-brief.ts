const marker = '这次旅行的想法：';
export function travelPrompt(values: Record<string, string>, text: string) {
	const entries = Object.entries(values).filter(([, value]) => value.trim());
	if (!entries.length) return text.trim();
	if (text.trim()) entries.push(['补充想法', text.trim().replace(/\n/g, ' ')]);
	return marker + '\n' + entries.map(([key, value]) => `${key}：${value.trim()}`).join('\n');
}
