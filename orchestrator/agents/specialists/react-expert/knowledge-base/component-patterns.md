# React Component Patterns

## Functional Components

All components are functions. No class components.

```tsx
interface UserCardProps {
  name: string;
  email: string;
  onEdit?: () => void;
}

export function UserCard({ name, email, onEdit }: UserCardProps) {
  return (
    <div className="user-card">
      <h3>{name}</h3>
      <p>{email}</p>
      {onEdit && <button onClick={onEdit}>Edit</button>}
    </div>
  );
}
```

### Rules

- Export the props interface alongside the component.
- Use destructuring in the parameter list.
- Do not use `React.FC` — it adds `children` implicitly and complicates generics.
- Default props use JavaScript default parameters, not `defaultProps`.

## Custom Hooks

Extract reusable stateful logic into hooks:

```tsx
function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}

// Usage
function SearchInput() {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 300);

  useEffect(() => {
    search(debouncedQuery);
  }, [debouncedQuery]);

  return <input value={query} onChange={(e) => setQuery(e.target.value)} />;
}
```

### Rules

- Prefix with `use`.
- Return a single value, a tuple, or a named object. Not positional arrays
  beyond 2 elements.
- Custom hooks can call other hooks. They follow the Rules of Hooks.

## Composition Over Inheritance

### Children composition

```tsx
interface PanelProps {
  title: string;
  children: React.ReactNode;
}

function Panel({ title, children }: PanelProps) {
  return (
    <section>
      <h2>{title}</h2>
      <div className="panel-body">{children}</div>
    </section>
  );
}

// Usage
<Panel title="Settings">
  <SettingsForm />
</Panel>
```

### Render props

For components that need to share computed values:

```tsx
interface DataFetcherProps<T> {
  url: string;
  children: (data: T, loading: boolean) => React.ReactNode;
}

function DataFetcher<T>({ url, children }: DataFetcherProps<T>) {
  const { data, loading } = useFetch<T>(url);
  return <>{children(data, loading)}</>;
}
```

Prefer custom hooks over render props when possible. Render props are
useful when the parent needs to control rendering based on child state.

## Compound Components

Components that share implicit state:

```tsx
interface TabsContextValue {
  activeTab: string;
  setActiveTab: (id: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext() {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error("Tab components must be used within <Tabs>");
  return ctx;
}

function Tabs({ defaultTab, children }: { defaultTab: string; children: React.ReactNode }) {
  const [activeTab, setActiveTab] = useState(defaultTab);
  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      {children}
    </TabsContext.Provider>
  );
}

function TabButton({ id, children }: { id: string; children: React.ReactNode }) {
  const { activeTab, setActiveTab } = useTabsContext();
  return (
    <button
      role="tab"
      aria-selected={activeTab === id}
      onClick={() => setActiveTab(id)}
    >
      {children}
    </button>
  );
}

function TabPanel({ id, children }: { id: string; children: React.ReactNode }) {
  const { activeTab } = useTabsContext();
  if (activeTab !== id) return null;
  return <div role="tabpanel">{children}</div>;
}

Tabs.Button = TabButton;
Tabs.Panel = TabPanel;
```

## Controlled Inputs

Controlled components are the default. The parent owns the state:

```tsx
interface TextInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
}

function TextInput({ label, value, onChange, error }: TextInputProps) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id}>{label}</label>
      <input id={id} value={value} onChange={(e) => onChange(e.target.value)}
        aria-invalid={!!error} aria-describedby={error ? `${id}-error` : undefined} />
      {error && <span id={`${id}-error`} role="alert">{error}</span>}
    </div>
  );
}
```

## Anti-Patterns

- **Prop drilling**: Passing props through 3+ levels. Use context or
  composition instead.
- **God components**: Components over 200 lines. Extract sub-components
  and hooks.
- **useEffect for derived state**: If a value can be computed from props
  or state, compute it during render. Do not sync with useEffect.
- **Index as key**: Only use array index as key for static lists that
  never reorder. Use stable IDs for dynamic lists.
