import { useEffect, useState } from 'react'

// Маленький помощник для запросов к бэкенду
async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Ошибка запроса')
  return data
}

const money = (v) => `${Number(v).toLocaleString('ru-RU')} ₸`

// Универсальная таблица: рисует любой массив объектов
function Table({ rows }) {
  if (!rows?.length) return <p className="muted">Нет данных</p>
  const cols = Object.keys(rows[0])
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{cols.map((c) => <td key={c}>{String(r[c] ?? '')}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Dashboard() {
  const [s, setS] = useState(null)
  useEffect(() => { api('/stats').then(setS) }, [])
  if (!s) return <p className="muted">Загрузка…</p>
  return (
    <>
      <div className="cards">
        <div className="card"><span>Выручка</span><b>{money(s.revenue)}</b></div>
        <div className="card"><span>Заказов</span><b>{s.orders}</b></div>
        <div className="card"><span>Клиентов</span><b>{s.customers}</b></div>
      </div>
      <h3>Заканчивается на складе</h3>
      <Table rows={s.low_stock} />
    </>
  )
}

function Products() {
  const [items, setItems] = useState([])
  const [form, setForm] = useState({ name: '', category: '', price: '', stock: '' })
  const load = () => api('/products').then(setItems)
  useEffect(() => { load() }, [])

  const add = async (e) => {
    e.preventDefault()
    await api('/products', { method: 'POST', body: { ...form, price: +form.price, stock: +form.stock } })
    setForm({ name: '', category: '', price: '', stock: '' })
    load()
  }
  const field = (key, placeholder, type = 'text') => (
    <input required={key !== 'category'} type={type} placeholder={placeholder} value={form[key]}
      onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
  )
  return (
    <>
      <form className="row" onSubmit={add}>
        {field('name', 'Название')}{field('category', 'Категория')}
        {field('price', 'Цена', 'number')}{field('stock', 'Остаток', 'number')}
        <button>Добавить</button>
      </form>
      <Table rows={items} />
    </>
  )
}

function Orders() {
  const [orders, setOrders] = useState([])
  const [products, setProducts] = useState([])
  const [customers, setCustomers] = useState([])
  const [form, setForm] = useState({ customer_id: '', product_id: '', quantity: 1 })
  const [error, setError] = useState('')
  const load = () => api('/orders').then(setOrders)
  useEffect(() => {
    load()
    api('/products').then(setProducts)
    api('/customers').then(setCustomers)
  }, [])

  const add = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api('/orders', { method: 'POST', body: {
        customer_id: +form.customer_id, product_id: +form.product_id, quantity: +form.quantity } })
      load()
    } catch (err) { setError(err.message) }
  }
  return (
    <>
      <form className="row" onSubmit={add}>
        <select required value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
          <option value="">Клиент…</option>
          {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select required value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value })}>
          <option value="">Товар…</option>
          {products.map((p) => <option key={p.id} value={p.id}>{p.name} (ост. {p.stock})</option>)}
        </select>
        <input type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
        <button>Создать заказ</button>
      </form>
      {error && <p className="error">{error}</p>}
      <Table rows={orders} />
    </>
  )
}

function AskAI() {
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const examples = ['Выручка по месяцам', 'Топ клиентов по сумме заказов', 'Какие товары почти закончились?']

  const ask = async (q) => {
    setLoading(true); setError(''); setResult(null)
    try { setResult(await api('/ask', { method: 'POST', body: { question: q } })) }
    catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }
  return (
    <>
      <form className="row" onSubmit={(e) => { e.preventDefault(); ask(question) }}>
        <input className="grow" placeholder="Спроси у базы на русском…" value={question}
          onChange={(e) => setQuestion(e.target.value)} />
        <button disabled={loading || !question}>{loading ? 'Думаю…' : 'Спросить'}</button>
      </form>
      <div className="row">
        {examples.map((ex) => (
          <button key={ex} className="chip" onClick={() => { setQuestion(ex); ask(ex) }}>{ex}</button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      {result && (
        <>
          <h3>SQL, который сгенерировал AI</h3>
          <pre>{result.sql}</pre>
          <h3>Результат</h3>
          <Table rows={result.rows} />
        </>
      )}
    </>
  )
}

const TABS = { 'Дашборд': Dashboard, 'Товары': Products, 'Заказы': Orders, 'AI-аналитик': AskAI }

export default function App() {
  const [tab, setTab] = useState('Дашборд')
  const Page = TABS[tab]
  return (
    <div className="app">
      <header>
        <h1>Mini AI ERP</h1>
        <nav>
          {Object.keys(TABS).map((t) => (
            <button key={t} className={t === tab ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>
          ))}
        </nav>
      </header>
      <main><Page key={tab} /></main>
    </div>
  )
}
