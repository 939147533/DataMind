# 数据库结构文档

## 表：categories

| 列名 | 类型 | 可空 | 默认值 | 主键 | 自增 | 注释 |
| --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | 是 |  | ✓ | ✓ |  |
| name | TEXT | 否 |  |  |  |  |
| description | TEXT | 是 |  |  |  |  |

```sql
CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
```

## 表：order_logs

| 列名 | 类型 | 可空 | 默认值 | 主键 | 自增 | 注释 |
| --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | 是 |  | ✓ | ✓ |  |
| order_id | INTEGER | 否 |  |  |  |  |
| action | TEXT | 否 |  |  |  |  |
| created_at | TEXT | 否 |  |  |  |  |

```sql
CREATE TABLE order_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
```

## 表：orders

| 列名 | 类型 | 可空 | 默认值 | 主键 | 自增 | 注释 |
| --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | 是 |  | ✓ | ✓ |  |
| user_id | INTEGER | 否 |  |  |  |  |
| product_id | INTEGER | 否 |  |  |  |  |
| quantity | INTEGER | 否 | 1 |  |  |  |
| amount | REAL | 否 | 0 |  |  |  |
| status | TEXT | 否 | 'pending' |  |  |  |
| created_at | TEXT | 否 |  |  |  |  |

```sql
CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL DEFAULT 1,
            amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
```

## 表：products

| 列名 | 类型 | 可空 | 默认值 | 主键 | 自增 | 注释 |
| --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | 是 |  | ✓ | ✓ |  |
| name | TEXT | 否 |  |  |  |  |
| category_id | INTEGER | 是 |  |  |  |  |
| price | REAL | 否 | 0 |  |  |  |
| stock | INTEGER | 否 | 0 |  |  |  |

```sql
CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category_id INTEGER REFERENCES categories(id),
            price REAL NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0
        )
```

## 表：users

| 列名 | 类型 | 可空 | 默认值 | 主键 | 自增 | 注释 |
| --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | 是 |  | ✓ | ✓ |  |
| username | TEXT | 否 |  |  |  |  |
| email | TEXT | 否 |  |  |  |  |
| age | INTEGER | 是 |  |  |  |  |
| created_at | TEXT | 否 |  |  |  |  |

```sql
CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL,
            age INTEGER,
            created_at TEXT NOT NULL
        )
```
