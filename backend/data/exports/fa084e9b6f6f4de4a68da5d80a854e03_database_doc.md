# 数据库结构文档

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
