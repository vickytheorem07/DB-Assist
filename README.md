# DB-Assist

DB-Assist is an AI-powered database assistant. It uses LangChain, Groq, PostgreSQL, and a Chroma vector store to answer natural-language questions about a database. A SQL agent uses database tools, while retrieved database documentation provides schema context. Conversation messages are stored by conversation ID.

## Features

- Upload a Word `.docx` database guide and chunk its table documentation into Chroma.
- Ask natural-language questions that the SQL agent answers with database tools.
- Load recent conversation messages by `conversation_id` and persist each user/assistant exchange.
- Log request IDs, retrieval and agent metrics, errors, and request duration.

## Database setup

The example PostgreSQL database is named `sales_management`. In pgAdmin, first run this command separately while connected to a maintenance database such as `postgres`:

```sql
CREATE DATABASE sales_management;
```

Then connect pgAdmin to `sales_management` and create the business tables:

```sql
CREATE TABLE customers (
    customer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE,
    phone       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE employees (
    employee_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    job_title   TEXT,
    hired_at    DATE
);

CREATE TABLE products (
    product_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    unit_price  NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    stock_qty   INTEGER NOT NULL DEFAULT 0 CHECK (stock_qty >= 0)
);

CREATE TABLE orders (
    order_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customers(customer_id),
    employee_id BIGINT REFERENCES employees(employee_id),
    order_date  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN (
                    'pending', 'processing', 'shipped', 'delivered', 'cancelled'
                ))
);

CREATE TABLE order_items (
    order_id   BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(product_id),
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    PRIMARY KEY (order_id, product_id)
);

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_employee_id ON orders(employee_id);
```

### Populate sample data

Run the following in the `sales_management` database. It creates 10,000 customers, 500 employees, 1,000 products, 50,000 orders, and three order items per order.

```sql
BEGIN;

INSERT INTO customers (name, email, phone)
SELECT
    'Customer ' || n,
    'customer' || n || '@example.com',
    '555-' || LPAD(n::text, 7, '0')
FROM generate_series(1, 10000) AS g(n);

INSERT INTO employees (name, email, job_title, hired_at)
SELECT
    'Employee ' || n,
    'employee' || n || '@example.com',
    CASE n % 4
        WHEN 0 THEN 'Sales Associate'
        WHEN 1 THEN 'Account Manager'
        WHEN 2 THEN 'Sales Representative'
        ELSE 'Support Specialist'
    END,
    DATE '2018-01-01' + (n % 2500)
FROM generate_series(1, 500) AS g(n);

INSERT INTO products (name, description, unit_price, stock_qty)
SELECT
    'Product ' || n,
    'Sample product description for product ' || n,
    ROUND((5 + (n % 996) * 1.25)::numeric, 2),
    (n * 17) % 500
FROM generate_series(1, 1000) AS g(n);

INSERT INTO orders (customer_id, employee_id, order_date, status)
SELECT
    1 + (n % 10000),
    1 + (n % 500),
    NOW() - ((n % 730) * INTERVAL '1 day'),
    CASE n % 5
        WHEN 0 THEN 'pending'
        WHEN 1 THEN 'processing'
        WHEN 2 THEN 'shipped'
        WHEN 3 THEN 'delivered'
        ELSE 'cancelled'
    END
FROM generate_series(1, 50000) AS g(n);

INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT
    o.order_id,
    1 + ((o.order_id * 3 + item_no) % 1000),
    1 + ((o.order_id + item_no) % 5),
    p.unit_price
FROM orders AS o
CROSS JOIN generate_series(1, 3) AS item(item_no)
JOIN products AS p
    ON p.product_id = 1 + ((o.order_id * 3 + item_no) % 1000)
WHERE o.order_id <= 50000;

COMMIT;
```

### Conversation history table

The app stores each user and assistant message as a separate row. Create the table and index in `sales_management`:

```sql
CREATE TABLE conversation_messages (
    message_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversation_messages_conversation_id
    ON conversation_messages (conversation_id, message_id);
```

## Database role and privileges

Create a login role (replace the example password):

```sql
CREATE ROLE sales_readonly
    LOGIN
    PASSWORD 'ReplaceWithAStrongPassword';

GRANT CONNECT ON DATABASE sales_management TO sales_readonly;
GRANT USAGE ON SCHEMA public TO sales_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sales_readonly;
```

The agent needs to save conversation messages. Grant this role `INSERT` only on the history table; its business-table privileges remain `SELECT` only:

```sql
GRANT SELECT, INSERT ON TABLE public.conversation_messages TO sales_readonly;
```

Configure the app’s `back_end/.env` with a URL for the role above:

```env
DATABASE_URL=postgresql+psycopg://sales_readonly:YOUR_PASSWORD@localhost:5432/sales_management
```

Replace `YOUR_PASSWORD` with the role password. Keep real credentials out of source control.

## Database guide YAML

The SQL agent reads its allowed schema and table list from `back_end/db_assist.yaml`:

```yaml
database:
  schema: public
  tables:
    - customers
    - employees
    - products
    - orders
    - order_items
```

## Word guide loading and chunking

The document loader accepts Word `.docx` files and creates one LangChain `Document` per manually paginated page. Use a Heading 1 style for each table name. The table name, page number, and source filename are stored in metadata.

The upload endpoint allows `.docx` files up to 10 MB and 10 pages by default. Configure `MAX_UPLOAD_SIZE_MB` and `MAX_DOCUMENT_PAGES` in application settings to change those limits. Each page is kept as one chunk unless it exceeds `CHUNK_SIZE_TOKENS` (default `500`); oversized pages are split with `CHUNK_OVERLAP_TOKENS` (default `250`). The encoding defaults to `cl100k_base` and is configured by `TIKTOKEN_ENCODING`.

When a new guide is uploaded, the existing Chroma collection is cleared before the new chunks are added. IDs start at `1` for each replacement.

To generate the optional JSONL chunk file from the source guide:

```powershell
uv sync
uv run python back_end/chunk_database_guide.py --max-tokens 500 --overlap-tokens 250 --encoding cl100k_base
```

By default, the JSONL output is `back_end/data/sales_management_chunks.jsonl`.

## API endpoints

The API is mounted under `/api/v1`.

### `POST /api/v1/load_doc`

Upload a Word document as multipart form data using the `file` field. The document should contain database and table descriptions. Success returns the filename, page and chunk counts, and table names.

### `POST /api/v1/interact_agent`

Submit JSON with a non-empty query and conversation ID:

```json
{
  "user_query": "How many customers are in the database?",
  "conversation_id": "conversation-123"
}
```

The query is checked against retrieved documentation and the SQL tools. The agent fetches up to the configured number of recent conversation messages and stores the new user query and assistant answer. The response contains `agent_response`, `user_query`, and `req_id`.

### `GET /api/v1/conversations/{conversation_id}/history?limit=10`

Retrieve up to `limit` user/assistant messages for a conversation. `limit` defaults to `10` and must be between `1` and `100`. The returned messages are ordered oldest-to-newest within the selected most recent messages.

### Health checks

- `GET /health` is available.
- `/ready` is currently commented out in `back_end/main.py` and is not registered.

## Run the backend

From the `back_end` directory:

```powershell
uv run --project .. uvicorn app.main:app --reload
```
