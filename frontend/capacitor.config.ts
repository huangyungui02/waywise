import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
	appId: 'com.travelagent.personal',
	appName: '知途',
	webDir: 'build',
	// SvelteKit 的根路由需要显式路径，避免无路径入口在加载失败时反复刷新。
	server: { appStartPath: '/' }
};

export default config;
