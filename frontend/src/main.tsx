import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider, Outlet, NavLink, useLoaderData, useNavigate, useRevalidator, useRouteError, useNavigation } from 'react-router';
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport, isToolUIPart } from 'ai';
import type { UIMessage } from 'ai';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from './api';
import type { Conversation, Detail, Trip } from './api';
import './style.css';

function Layout() {
  const conversations = useLoaderData() as Conversation[];
  const navigate = useNavigate();
  const revalidator = useRevalidator();
  const navigation = useNavigation();
  const [error, setError] = useState('');
  async function create() {
    try {
      const conversation = await api<Conversation>('/conversations', { method: 'POST' });
      await navigate(`/chat/${conversation.id}`);
      revalidator.revalidate();
    } catch (e) { setError(String(e)); }
  }
  async function remove(id: string) {
    if (!window.confirm('删除这次旅行和聊天记录？')) return;
    try {
      await api(`/conversations/${id}`, { method: 'DELETE' });
      await navigate('/');
      revalidator.revalidate();
    } catch (e) { setError(String(e)); }
  }
  return <div className="app">
    <aside className="sidebar">
      <NavLink to="/" className="brand"><span className="brand-mark">山</span><span>山行<small>把下一站，慢慢安排好</small></span></NavLink>
      <button className="new-trip" onClick={create}>＋ 开始一段旅行</button>
      <div className="section-label">我的旅行 <span>{conversations.length.toString().padStart(2, '0')}</span></div>
      <nav className="conversations">{conversations.map(c => <div className="conversation" key={c.id}>
        <NavLink to={`/chat/${c.id}`}><span>↗</span><div>{c.title}<small>{new Date(c.updated_at).toLocaleDateString('zh-CN')}</small></div></NavLink>
        <button title="删除旅行" aria-label={`删除 ${c.title}`} onClick={() => remove(c.id)}>×</button>
      </div>)}</nav>
      {error && <p role="alert" className="error">{error}<button onClick={() => setError('')}>关闭</button></p>}
      <div className="sidebar-foot"><span className="status-dot"/> 你的旅行，从这里出发<small>车票 · 酒店 · 每日行程</small></div>
    </aside>
    <main className="main">{navigation.state === 'loading' && <div className="loading-bar"/>}<Outlet/></main>
  </div>;
}

function Welcome() {
  const navigate = useNavigate();
  const revalidator = useRevalidator();
  const [error, setError] = useState('');
  async function start() {
    try {
      const c = await api<Conversation>('/conversations', { method: 'POST' });
      await navigate(`/chat/${c.id}`);
      revalidator.revalidate();
    }
    catch (e) { setError(String(e)); }
  }
  return <section className="welcome">
    <span className="eyebrow">YOUR NEXT CHAPTER</span><div className="landscape" aria-hidden="true"><span>山</span></div>
    <h1>下一站，<br/>想去哪里走走？</h1>
    <p>聊聊你的期待。一起选好往返交通和住宿，<br/>再把每一天安排得刚刚好。</p>
    <button className="primary" onClick={start}>开始规划 <span>↗</span></button>
    <div className="steps"><span>01 说说想法</span><span>02 确认交通与住宿</span><span>03 带上每日行程</span></div>
    {error && <p role="alert" className="error">{error}</p>}
  </section>;
}

const toolNames: Record<string, string> = {
  current_time: '核对北京时间', confirm_trip: '检查并保存交通和住宿',
  load_capability: '准备旅行查询', read_file: '查阅旅行查询说明', run_command: '查询旅行信息',
  web_search: '搜索旅行资讯',
};
function Message({ message }: { message: UIMessage }) {
  return <article className={`message ${message.role}`}>
    <div className="avatar">{message.role === 'user' ? '你' : '山'}</div>
    <div className="message-body"><div className="message-author">{message.role === 'user' ? '你' : '山行 · 旅行助手'}</div>
      {message.parts.map((part, i) => {
        if (part.type === 'text') return <div className="markdown" key={i}><Markdown remarkPlugins={[remarkGfm]} components={{ a: props => <a {...props} target="_blank" rel="noreferrer"/> }}>{part.text}</Markdown></div>;
        if (isToolUIPart(part)) {
          const name = part.type === 'dynamic-tool' ? part.toolName : part.type.slice(5);
          const finished = part.state === 'output-available';
          const failed = part.state === 'output-error';
          return <details className="tool" key={i}><summary><span>{failed ? '!' : finished ? '✓' : '◌'}</span>{toolNames[name] || (name.startsWith('amap') ? '查询地点与路线' : name)}<small>{failed ? '未完成' : finished ? '已返回' : '进行中'}</small></summary>
            <pre>{JSON.stringify('output' in part ? part.output : 'errorText' in part ? part.errorText : part.input, null, 2)}</pre>
          </details>;
        }
        return null;
      })}
    </div>
  </article>;
}

function TripPanel({ trip }: { trip: Trip | null }) {
  return <details className="trip-panel" open={!!trip}>
    <summary>基础安排 <span>{trip ? '已确认方案' : '待确认'}</span></summary>
    {!trip ? <p>选好往返交通和住宿后，确认的安排会出现在这里。</p> : <>
      <p className="trip-note">最近确认的安排；如需更改，请在聊天中重新确认。</p>
      {([['去程', trip.outbound], ['回程', trip.inbound]] as const).map(([label, leg]) => <section key={label}>
        <small>{label} · {leg.type === 'train' ? '火车' : '飞机'}</small><strong>{leg.number}</strong>
        <p>{leg.departure_station} → {leg.arrival_station}</p><time>{leg.departure_time.replace('T', ' ')}<br/>抵达 {leg.arrival_time.replace('T', ' ')}</time>
        <div>{leg.purchased ? <span className="booked">已购买</span> : leg.purchase_url && <a href={leg.purchase_url} target="_blank" rel="noreferrer">前往购买 ↗</a>}</div>
      </section>)}
      {trip.stays.map((stay, i) => <section key={i}><small>住宿</small><strong>{stay.hotel}</strong><p>{stay.address}</p><time>{stay.check_in} 入住<br/>{stay.check_out} 退房</time><div>{stay.booked ? <span className="booked">已预订</span> : stay.purchase_url && <a href={stay.purchase_url} target="_blank" rel="noreferrer">前往预订 ↗</a>}</div></section>)}
      {!trip.stays.length && <p>同日往返，无酒店住宿。</p>}
    </>}
  </details>;
}

function ChatRoute() {
  const detail = useLoaderData() as Detail;
  return <Chat key={detail.summary.id} detail={detail}/>;
}
function Chat({ detail }: { detail: Detail }) {
  const revalidator = useRevalidator();
  const [text, setText] = useState('');
  const bottom = useRef<HTMLDivElement>(null);
  const [transport] = useState(() => new DefaultChatTransport({
    api: `/api/conversations/${detail.summary.id}/chat`,
    prepareSendMessagesRequest: ({ id, messages }) => ({ body: { id, trigger: 'submit-message', messages: messages.slice(-1) } }),
  }));
  const { messages, sendMessage, stop, status, error } = useChat({
    id: detail.summary.id, messages: detail.messages, transport,
    onFinish: () => { revalidator.revalidate(); },
  });
  const running = status === 'submitted' || status === 'streaming';
  useEffect(() => () => { void stop(); }, [stop]);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim() || running) return;
    const input = text.trim(); setText(''); await sendMessage({ text: input });
  }
  return <>
    <header className="chat-header"><div><span className="eyebrow">TRAVEL NOTEBOOK</span><h2>{detail.summary.title}</h2></div><span className="header-tag">一起，把旅行安排好</span></header>
    <div className="chat-layout"><div className="chat-column">
      <div className="messages">
        {!messages.length && <div className="chat-intro"><span>↗</span><h2>说说这次旅行吧。</h2><p>从哪里出发，想去哪个城市，准备什么时候去？<br/>已经订好的车票和酒店，也可以一起告诉我。</p><button onClick={() => setText('我想规划一次周末旅行，车票和酒店还没订。')}>还没有具体计划，帮我一起想想 →</button></div>}
        {messages.map(message => <Message message={message} key={message.id}/>)}
        {status === 'submitted' && <p className="thinking">正在整理你的旅行需求…</p>}
        {error && <p role="alert" className="error">{error.message}。已保存的记录可重新打开查看，或继续发送消息。</p>}
        {detail.summary.outcome === 'cancelled' && !running && <p className="notice">上次回复已中断，已保留可恢复的记录，可以继续咨询。</p>}
        <div ref={bottom}/>
      </div>
      <form className="composer" onSubmit={submit}>
        <textarea aria-label="旅行需求" placeholder="聊聊目的地、日期，或你想怎么度过这段旅程…" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }}/>
        <div className="composer-foot"><small>交通与住宿确认后，再安排每日行程</small>{running ? <button type="button" onClick={() => void stop()}>停止 ■</button> : <button type="submit" disabled={!text.trim()}>发送 ↑</button>}</div>
      </form><p className="disclaimer">报价与库存以预订页面为准 · 购买需由你自行完成</p>
    </div><TripPanel trip={detail.trip}/></div>
  </>;
}

function RouteError() {
  const error = useRouteError();
  return <div className="welcome"><h1>暂时无法打开</h1><p>{error instanceof Error ? error.message : '会话不存在或服务不可用'}</p><a href="/">返回首页</a></div>;
}
const router = createBrowserRouter([{
  path: '/', element: <Layout/>, errorElement: <RouteError/>, loader: () => api<Conversation[]>('/conversations'),
  children: [
    { index: true, element: <Welcome/> },
    { path: 'chat/:id', element: <ChatRoute/>, loader: ({ params }) => api<Detail>(`/conversations/${params.id}`) },
  ],
}]);
createRoot(document.getElementById('root')!).render(<RouterProvider router={router}/>);
