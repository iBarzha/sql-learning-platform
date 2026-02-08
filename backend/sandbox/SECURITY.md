# Sandbox Security — Query Validator

The sandbox uses a multi-layer query validator (`query_validator.py`) that inspects every query **before** it reaches the database engine. SQL comments (`--`, `/* */`) are stripped before validation to prevent bypass attempts.

---

## PostgreSQL

### Blocked

| Category | Blocked pattern | Response |
|---|---|---|
| File read | `pg_read_file()` | Nice try! Reading server files is not allowed in the sandbox. |
| File read | `pg_read_binary_file()` | Nice try! Reading server files is not allowed in the sandbox. |
| File read | `pg_stat_file()` | Nice try! Reading server files is not allowed in the sandbox. |
| File read | `lo_import()` | Nice try! Reading server files is not allowed in the sandbox. |
| File write | `lo_export()` | Nope! Writing files to the server is off limits here. |
| System cmd | `COPY ... TO PROGRAM` | Good attempt, but executing system commands is blocked. |
| System cmd | `COPY ... FROM PROGRAM` | Good attempt, but executing system commands is blocked. |
| System cmd | `pg_execute_server_program()` | Good attempt, but executing system commands is blocked. |
| System cmd | `CREATE FUNCTION` | Good attempt, but executing system commands is blocked. |
| System cmd | `CREATE PROCEDURE` | Good attempt, but executing system commands is blocked. |
| System cmd | `CREATE TRIGGER` | Good attempt, but executing system commands is blocked. |
| System cmd | `DO $$ ... $$` | Good attempt, but executing system commands is blocked. |
| Privilege | `pg_shadow` | Access denied! You can only work with your sandbox data. |
| Privilege | `pg_authid` | Access denied! You can only work with your sandbox data. |
| Privilege | `pg_auth_members` | Access denied! You can only work with your sandbox data. |
| Privilege | `pg_roles` | Access denied! You can only work with your sandbox data. |
| Privilege | `pg_user` | Access denied! You can only work with your sandbox data. |
| Privilege | `information_schema.user_privileges` | Access denied! You can only work with your sandbox data. |
| Server config | `ALTER SYSTEM` | Sorry, server configuration changes are not permitted. |
| Server config | `pg_reload_conf()` | Sorry, server configuration changes are not permitted. |
| Server config | `pg_terminate_backend()` | Sorry, server configuration changes are not permitted. |
| Server config | `pg_cancel_backend()` | Sorry, server configuration changes are not permitted. |
| Server config | `pg_sleep()` | Sorry, server configuration changes are not permitted. |
| Auth | `CREATE ROLE / USER` | Authentication and user management is off limits. |
| Auth | `ALTER ROLE / USER` | Authentication and user management is off limits. |
| Auth | `DROP ROLE / USER` | Authentication and user management is off limits. |
| Auth | `GRANT` | Authentication and user management is off limits. |
| Auth | `REVOKE` | Authentication and user management is off limits. |
| Extension | `CREATE EXTENSION` | Extensions and plugins are disabled in the sandbox. |
| Destructive | `DROP DATABASE` | Whoa there! Destructive server operations are blocked. |
| Destructive | `CREATE DATABASE` | Whoa there! Destructive server operations are blocked. |
| Destructive | `DROP TABLESPACE` | Whoa there! Destructive server operations are blocked. |
| Network | `dblink` | Network operations from the sandbox? Not today! |
| Network | `postgres_fdw` | Network operations from the sandbox? Not today! |
| Network | `CREATE SERVER` | Network operations from the sandbox? Not today! |
| Network | `CREATE FOREIGN` | Network operations from the sandbox? Not today! |
| Info leak | `pg_ls_dir()` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `pg_ls_logdir()` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `pg_ls_waldir()` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `current_setting()` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `pg_hba_file_rules` | Sneaky! But accessing server internals is not allowed. |

### Allowed

All standard DML and DDL for learning:

- `SELECT`, `INSERT`, `UPDATE`, `DELETE`
- `CREATE TABLE`, `ALTER TABLE`, `DROP TABLE`
- `CREATE INDEX`, `DROP INDEX`
- `CREATE VIEW`, `DROP VIEW`
- `JOIN`, `UNION`, `SUBQUERY`, `CTE (WITH)`
- `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`
- `CASE`, `COALESCE`, `CAST`
- Aggregate functions: `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`
- Window functions: `ROW_NUMBER`, `RANK`, `DENSE_RANK`, `LAG`, `LEAD`
- `EXPLAIN`, `EXPLAIN ANALYZE`
- `BEGIN`, `COMMIT`, `ROLLBACK`
- System catalog: `pg_tables`, `pg_indexes`, `information_schema.tables`, `information_schema.columns`

---

## MariaDB

### Blocked

| Category | Blocked pattern | Response |
|---|---|---|
| File read | `LOAD_FILE()` | Nice try! Reading server files is not allowed in the sandbox. |
| File write | `INTO OUTFILE` | Nope! Writing files to the server is off limits here. |
| File write | `INTO DUMPFILE` | Nope! Writing files to the server is off limits here. |
| Privilege | `mysql.user` | Access denied! You can only work with your sandbox data. |
| Privilege | `mysql.db` | Access denied! You can only work with your sandbox data. |
| Privilege | `mysql.tables_priv` | Access denied! You can only work with your sandbox data. |
| Privilege | `mysql.columns_priv` | Access denied! You can only work with your sandbox data. |
| Privilege | `mysql.global_priv` | Access denied! You can only work with your sandbox data. |
| Privilege | `performance_schema` | Access denied! You can only work with your sandbox data. |
| Server config | `SET GLOBAL` | Sorry, server configuration changes are not permitted. |
| Auth | `CREATE USER` | Authentication and user management is off limits. |
| Auth | `DROP USER` | Authentication and user management is off limits. |
| Auth | `GRANT` | Authentication and user management is off limits. |
| Auth | `REVOKE` | Authentication and user management is off limits. |
| System cmd | `CREATE FUNCTION` | Good attempt, but executing system commands is blocked. |
| System cmd | `CREATE PROCEDURE` | Good attempt, but executing system commands is blocked. |
| System cmd | `CREATE TRIGGER` | Good attempt, but executing system commands is blocked. |
| System cmd | `CREATE EVENT` | Good attempt, but executing system commands is blocked. |
| Destructive | `DROP DATABASE` | Whoa there! Destructive server operations are blocked. |
| Destructive | `CREATE DATABASE` | Whoa there! Destructive server operations are blocked. |
| Info leak | `SHOW VARIABLES` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `SHOW GRANTS` | Sneaky! But accessing server internals is not allowed. |
| Replication | `SHOW MASTER / SLAVE / REPLICA` | Replication commands are not available in the sandbox. |

### Allowed

Same as PostgreSQL — all standard DML/DDL for learning.

---

## SQLite

### Blocked

| Category | Blocked pattern | Response |
|---|---|---|
| File read | `ATTACH DATABASE` | Nice try! Reading server files is not allowed in the sandbox. |

SQLite runs in `:memory:` mode — each request gets a completely isolated in-memory database that is destroyed after the response. Multi-statement execution (`;`-separated) is blocked at the driver level (`cursor.execute` only runs one statement).

### Allowed

All standard SQLite SQL. The `sqlite_master` table is readable (useful for learning schema introspection).

---

## MongoDB

### Blocked

| Category | Blocked pattern | Response |
|---|---|---|
| Admin | `adminCommand()` | Admin commands are blocked. This is a learning sandbox! |
| Admin | `runCommand()` | Admin commands are blocked. This is a learning sandbox! |
| Admin | `getSiblingDB()` | Admin commands are blocked. This is a learning sandbox! |
| Admin | `getMongo()` | Admin commands are blocked. This is a learning sandbox! |
| Destructive | `shutdownServer()` | Whoa there! Destructive server operations are blocked. |
| Destructive | `fsyncLock()` | Whoa there! Destructive server operations are blocked. |
| Destructive | `fsyncUnlock()` | Whoa there! Destructive server operations are blocked. |
| Destructive | `dropDatabase()` | Whoa there! Destructive server operations are blocked. |
| System cmd | `$where` | Good attempt, but executing system commands is blocked. |
| System cmd | `eval()` | Good attempt, but executing system commands is blocked. |
| System cmd | `system()` | Good attempt, but executing system commands is blocked. |
| System cmd | `$function` | Good attempt, but executing system commands is blocked. |
| System cmd | `$accumulator` | Good attempt, but executing system commands is blocked. |
| System cmd | `mapReduce()` | Good attempt, but executing system commands is blocked. |
| System cmd | `process.` | Good attempt, but executing system commands is blocked. |
| System cmd | `require()` | Good attempt, but executing system commands is blocked. |
| System cmd | `child_process` | Good attempt, but executing system commands is blocked. |
| System cmd | `spawn()` | Good attempt, but executing system commands is blocked. |
| System cmd | `exec()` | Good attempt, but executing system commands is blocked. |
| Auth | `createUser()` | Authentication and user management is off limits. |
| Auth | `dropUser()` | Authentication and user management is off limits. |
| Auth | `updateUser()` | Authentication and user management is off limits. |
| Auth | `grantRolesToUser()` | Authentication and user management is off limits. |
| Auth | `revokeRolesFromUser()` | Authentication and user management is off limits. |
| Auth | `createRole()` | Authentication and user management is off limits. |
| Info leak | `serverStatus` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `hostInfo` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `listDatabases` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `currentOp` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `getCmdLineOpts` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `getLog` | Sneaky! But accessing server internals is not allowed. |
| Replication | `replSetGetStatus` | Replication commands are not available in the sandbox. |
| Replication | `replSetInitiate` | Replication commands are not available in the sandbox. |
| Replication | `isMaster` | Replication commands are not available in the sandbox. |

### Allowed

Operations whitelisted in the executor:

- `db.collection.find()` / `findOne()`
- `db.collection.insertOne()` / `insertMany()`
- `db.collection.updateOne()` / `updateMany()`
- `db.collection.deleteOne()` / `deleteMany()`
- `db.collection.aggregate()`
- `db.collection.countDocuments()`
- `db.collection.distinct()`

---

## Redis

Redis uses a **whitelist** approach — only explicitly allowed commands can run. Everything else is blocked by default.

### Blocked (explicit messages)

| Category | Blocked command | Response |
|---|---|---|
| Server config | `CONFIG` | Sorry, server configuration changes are not permitted. |
| Server config | `BGSAVE` | Sorry, server configuration changes are not permitted. |
| Server config | `BGREWRITEAOF` | Sorry, server configuration changes are not permitted. |
| Server config | `SAVE` | Sorry, server configuration changes are not permitted. |
| Server config | `CLUSTER` | Sorry, server configuration changes are not permitted. |
| Server config | `SELECT` | Sorry, server configuration changes are not permitted. |
| Server config | `WAIT` | Sorry, server configuration changes are not permitted. |
| Server config | `RESTORE` | Sorry, server configuration changes are not permitted. |
| Destructive | `FLUSHALL` | Whoa there! Destructive server operations are blocked. |
| Destructive | `FLUSHDB` | Whoa there! Destructive server operations are blocked. |
| Destructive | `SHUTDOWN` | Whoa there! Destructive server operations are blocked. |
| Destructive | `SWAPDB` | Whoa there! Destructive server operations are blocked. |
| System cmd | `DEBUG` | Good attempt, but executing system commands is blocked. |
| System cmd | `EVAL` | Good attempt, but executing system commands is blocked. |
| System cmd | `EVALSHA` | Good attempt, but executing system commands is blocked. |
| System cmd | `SCRIPT` | Good attempt, but executing system commands is blocked. |
| System cmd | `FUNCTION` | Good attempt, but executing system commands is blocked. |
| System cmd | `FCALL` | Good attempt, but executing system commands is blocked. |
| Auth | `ACL` | Authentication and user management is off limits. |
| Auth | `AUTH` | Authentication and user management is off limits. |
| Extension | `MODULE` | Extensions and plugins are disabled in the sandbox. |
| Network | `MIGRATE` | Network operations from the sandbox? Not today! |
| Replication | `SLAVEOF` | Replication commands are not available in the sandbox. |
| Replication | `REPLICAOF` | Replication commands are not available in the sandbox. |
| Info leak | `CLIENT` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `COMMAND` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `MONITOR` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `LATENCY` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `MEMORY` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `SLOWLOG` | Sneaky! But accessing server internals is not allowed. |
| Info leak | `DUMP` | Sneaky! But accessing server internals is not allowed. |

Any command not in the allowed list gets a generic message:
> The command 'X' is not available in the sandbox. Stick to data commands like GET, SET, HSET, LPUSH, ZADD, etc.

### Allowed

| Group | Commands |
|---|---|
| Strings | `SET` `GET` `MSET` `MGET` `APPEND` `STRLEN` `INCR` `INCRBY` `INCRBYFLOAT` `DECR` `DECRBY` `SETNX` `SETEX` `PSETEX` `GETSET` `GETRANGE` `SETRANGE` `GETDEL` |
| Keys | `DEL` `EXISTS` `EXPIRE` `EXPIREAT` `TTL` `PTTL` `PERSIST` `TYPE` `RENAME` `RENAMENX` `RANDOMKEY` `SCAN` `OBJECT` `KEYS` |
| Hashes | `HSET` `HGET` `HMSET` `HMGET` `HGETALL` `HDEL` `HEXISTS` `HKEYS` `HVALS` `HLEN` `HINCRBY` `HINCRBYFLOAT` `HSETNX` `HSCAN` |
| Lists | `LPUSH` `RPUSH` `LPOP` `RPOP` `LRANGE` `LLEN` `LINDEX` `LSET` `LINSERT` `LREM` `LTRIM` `RPOPLPUSH` `LMOVE` `LPOS` |
| Sets | `SADD` `SREM` `SMEMBERS` `SISMEMBER` `SCARD` `SUNION` `SINTER` `SDIFF` `SUNIONSTORE` `SINTERSTORE` `SDIFFSTORE` `SRANDMEMBER` `SPOP` `SMOVE` `SSCAN` |
| Sorted Sets | `ZADD` `ZREM` `ZSCORE` `ZRANK` `ZREVRANK` `ZRANGE` `ZREVRANGE` `ZRANGEBYSCORE` `ZREVRANGEBYSCORE` `ZCARD` `ZCOUNT` `ZINCRBY` `ZUNIONSTORE` `ZINTERSTORE` `ZRANGEBYLEX` `ZLEXCOUNT` `ZSCAN` `ZPOPMIN` `ZPOPMAX` `ZRANGESTORE` `ZMSCORE` |
| HyperLogLog | `PFADD` `PFCOUNT` `PFMERGE` |
| Streams | `XADD` `XLEN` `XRANGE` `XREVRANGE` `XREAD` `XINFO` `XTRIM` |
| Pub/Sub | `PUBLISH` `SUBSCRIBE` `UNSUBSCRIBE` |
| Geo | `GEOADD` `GEODIST` `GEOHASH` `GEOPOS` `GEORADIUS` `GEORADIUSBYMEMBER` `GEOSEARCH` `GEOSEARCHSTORE` |
| Transactions | `MULTI` `EXEC` `DISCARD` `WATCH` `UNWATCH` |
| Utility | `PING` `ECHO` `DBSIZE` `TIME` `SORT` `INFO` |

---

## Anti-bypass measures

- **SQL comments stripped** — `--` line comments and `/* */` block comments are removed before pattern matching, so `SELECT pg_read_file/**/('/etc/passwd')` is still caught
- **Case-insensitive** — all patterns match regardless of casing
- **Whitespace-collapsed** — extra spaces/newlines between keywords don't help
- **Redis whitelist** — unknown commands are blocked by default, not just known-bad ones
- **MongoDB operation whitelist** — only `find`, `findOne`, `insertOne`, `insertMany`, `updateOne`, `updateMany`, `deleteOne`, `deleteMany`, `aggregate`, `countDocuments`, `distinct` are executable at the executor level
