const marker = '这次旅行的想法：';
export function travelPrompt(values: Record<string, string>, text: string) {
	const entries = Object.entries(values).filter(([, value]) => value.trim());
	if (!entries.length) return text.trim();
	if (text.trim()) entries.push(['补充想法', text.trim().replace(/\n/g, ' ')]);
	return marker + '\n' + entries.map(([key, value]) => `${key}：${value.trim()}`).join('\n');
}
export function readBrief(text: string): Record<string, string> | undefined {
	if (!text.startsWith(marker)) return;
	return Object.fromEntries(
		text
			.slice(marker.length)
			.trim()
			.split('\n')
			.flatMap((line) => {
				const index = line.indexOf('：');
				return index < 0 ? [] : [[line.slice(0, index), line.slice(index + 1)]];
			})
	);
}
