"""Query security validator for the sandbox.

Blocks dangerous operations like file reads, system commands,
privilege escalation, and server configuration changes.
Returns friendly messages for blocked queries.
"""

import re

# ── Friendly rejection messages ─────────────────────────────────
MESSAGES = {
    'file_read': "Nice try! Reading server files is not allowed in the sandbox.",
    'file_write': "Nope! Writing files to the server is off limits here.",
    'system_cmd': "Good attempt, but executing system commands is blocked.",
    'privilege': "Access denied! You can only work with your sandbox data.",
    'server_config': "Sorry, server configuration changes are not permitted.",
    'destructive': "Whoa there! Destructive server operations are blocked.",
    'info_leak': "Sneaky! But accessing server internals is not allowed.",
    'extension': "Extensions and plugins are disabled in the sandbox.",
    'network': "Network operations from the sandbox? Not today!",
    'auth': "Authentication and user management is off limits.",
    'replication': "Replication commands are not available in the sandbox.",
    'admin': "Admin commands are blocked. This is a learning sandbox!",
}


class QueryBlockedError(Exception):
    """Raised when a query is blocked by security rules."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# ═══════════════════════════════════════════════════════════════
#  SQL (PostgreSQL, MariaDB, SQLite) validators
# ═══════════════════════════════════════════════════════════════

# Patterns are matched against the query with comments stripped,
# collapsed whitespace, and case-insensitive matching.

_SQL_RULES = [
    # ── File system access ──────────────────────────────────
    (r'\bpg_read_file\b', MESSAGES['file_read']),
    (r'\bpg_read_binary_file\b', MESSAGES['file_read']),
    (r'\bpg_stat_file\b', MESSAGES['file_read']),
    (r'\blo_import\b', MESSAGES['file_read']),
    (r'\blo_export\b', MESSAGES['file_write']),
    (r'\bload_file\b', MESSAGES['file_read']),
    (r'\binto\s+outfile\b', MESSAGES['file_write']),
    (r'\binto\s+dumpfile\b', MESSAGES['file_write']),
    (r'\battach\s+database\b', MESSAGES['file_read']),

    # ── System command execution ────────────────────────────
    (r'\bcopy\b.*\bto\s+program\b', MESSAGES['system_cmd']),
    (r'\bcopy\b.*\bfrom\s+program\b', MESSAGES['system_cmd']),
    (r'\bpg_execute_server_program\b', MESSAGES['system_cmd']),

    # ── Privilege escalation / user info ────────────────────
    (r'\bpg_shadow\b', MESSAGES['privilege']),
    (r'\bpg_authid\b', MESSAGES['privilege']),
    (r'\bpg_auth_members\b', MESSAGES['privilege']),
    (r'\bpg_roles\b', MESSAGES['privilege']),
    (r'\bpg_user\b', MESSAGES['privilege']),
    (r'\binformation_schema\.user_privileges\b', MESSAGES['privilege']),
    (r'\bmysql\.user\b', MESSAGES['privilege']),
    (r'\bmysql\.db\b', MESSAGES['privilege']),
    (r'\bmysql\.tables_priv\b', MESSAGES['privilege']),
    (r'\bmysql\.columns_priv\b', MESSAGES['privilege']),
    (r'\bmysql\.global_priv\b', MESSAGES['privilege']),
    (r'\bperformance_schema\b', MESSAGES['privilege']),

    # ── Server configuration ────────────────────────────────
    (r'\bset\s+global\b', MESSAGES['server_config']),
    (r'\balter\s+system\b', MESSAGES['server_config']),
    (r'\bpg_reload_conf\b', MESSAGES['server_config']),
    (r'\bpg_terminate_backend\b', MESSAGES['server_config']),
    (r'\bpg_cancel_backend\b', MESSAGES['server_config']),
    (r'\bpg_sleep\b', MESSAGES['server_config']),

    # ── Dangerous DDL / admin ───────────────────────────────
    (r'\bcreate\s+role\b', MESSAGES['auth']),
    (r'\bcreate\s+user\b', MESSAGES['auth']),
    (r'\balter\s+role\b', MESSAGES['auth']),
    (r'\balter\s+user\b', MESSAGES['auth']),
    (r'\bdrop\s+role\b', MESSAGES['auth']),
    (r'\bdrop\s+user\b', MESSAGES['auth']),
    (r'\bgrant\b', MESSAGES['auth']),
    (r'\brevoke\b', MESSAGES['auth']),
    (r'\bcreate\s+extension\b', MESSAGES['extension']),
    (r'\bcreate\s+(?:or\s+replace\s+)?function\b', MESSAGES['system_cmd']),
    (r'\bcreate\s+(?:or\s+replace\s+)?procedure\b', MESSAGES['system_cmd']),
    (r'\bcreate\s+trigger\b', MESSAGES['system_cmd']),
    (r'\bcreate\s+event\b', MESSAGES['system_cmd']),
    (r'\bdo\s*\$', MESSAGES['system_cmd']),

    # ── Session isolation (prevent schema/db escape) ────────
    (r'\bcreate\s+schema\b', MESSAGES['destructive']),
    (r'\bdrop\s+schema\b', MESSAGES['destructive']),
    (r'\bset\s+search_path\b', MESSAGES['server_config']),
    (r'\buse\s+\w', MESSAGES['server_config']),

    # ── Destructive server-wide operations ──────────────────
    (r'\bdrop\s+database\b', MESSAGES['destructive']),
    (r'\bcreate\s+database\b', MESSAGES['destructive']),
    (r'\bdrop\s+tablespace\b', MESSAGES['destructive']),

    # ── Network / external access ───────────────────────────
    (r'\bdblink\b', MESSAGES['network']),
    (r'\bpostgres_fdw\b', MESSAGES['network']),
    (r'\bcreate\s+server\b', MESSAGES['network']),
    (r'\bcreate\s+foreign\b', MESSAGES['network']),

    # ── Information leaking ─────────────────────────────────
    (r'\bpg_ls_dir\b', MESSAGES['info_leak']),
    (r'\bpg_ls_logdir\b', MESSAGES['info_leak']),
    (r'\bpg_ls_waldir\b', MESSAGES['info_leak']),
    (r'\bcurrent_setting\b', MESSAGES['info_leak']),
    (r'\bpg_hba_file_rules\b', MESSAGES['info_leak']),
    (r'\bshow\s+variables\b', MESSAGES['info_leak']),
    (r'\bshow\s+grants\b', MESSAGES['info_leak']),
    (r'\bshow\s+(?:master|slave|replica)\b', MESSAGES['replication']),
]

# Pre-compile all SQL patterns
_COMPILED_SQL_RULES = [(re.compile(pat, re.IGNORECASE), msg) for pat, msg in _SQL_RULES]


def _strip_sql_comments(query: str) -> str:
    """Remove SQL comments (-- line and /* block */) to prevent bypass."""
    # Remove block comments
    query = re.sub(r'/\*.*?\*/', ' ', query, flags=re.DOTALL)
    # Remove line comments
    query = re.sub(r'--[^\n]*', ' ', query)
    # Collapse whitespace
    query = re.sub(r'\s+', ' ', query).strip()
    return query


def validate_sql(query: str) -> None:
    """Validate SQL query for PostgreSQL, MariaDB, and SQLite.

    Raises QueryBlockedError if the query contains dangerous patterns.
    """
    cleaned = _strip_sql_comments(query)

    for pattern, message in _COMPILED_SQL_RULES:
        if pattern.search(cleaned):
            raise QueryBlockedError(message)


# ═══════════════════════════════════════════════════════════════
#  MongoDB validator
# ═══════════════════════════════════════════════════════════════

_MONGO_BLOCKED_PATTERNS = [
    # Admin commands
    (r'\badminCommand\b', MESSAGES['admin']),
    (r'\brunCommand\b', MESSAGES['admin']),
    (r'\bgetSiblingDB\b', MESSAGES['admin']),
    (r'\bgetMongo\b', MESSAGES['admin']),
    (r'\bshutdownServer\b', MESSAGES['destructive']),
    (r'\bfsyncLock\b', MESSAGES['destructive']),
    (r'\bfsyncUnlock\b', MESSAGES['destructive']),

    # Code execution
    (r'\b\$where\b', MESSAGES['system_cmd']),
    (r'\beval\b', MESSAGES['system_cmd']),
    (r'\bsystem\b', MESSAGES['system_cmd']),
    (r'\b\$function\b', MESSAGES['system_cmd']),
    (r'\b\$accumulator\b', MESSAGES['system_cmd']),
    (r'\bmapReduce\b', MESSAGES['system_cmd']),

    # Auth / users
    (r'\bcreateUser\b', MESSAGES['auth']),
    (r'\bdropUser\b', MESSAGES['auth']),
    (r'\bupdateUser\b', MESSAGES['auth']),
    (r'\bgrantRolesToUser\b', MESSAGES['auth']),
    (r'\brevokeRolesFromUser\b', MESSAGES['auth']),
    (r'\bcreateRole\b', MESSAGES['auth']),

    # Database-level destructive
    (r'\bdropDatabase\b', MESSAGES['destructive']),

    # Server info
    (r'\bserverStatus\b', MESSAGES['info_leak']),
    (r'\bhostInfo\b', MESSAGES['info_leak']),
    (r'\blistDatabases\b', MESSAGES['info_leak']),
    (r'\bcurrentOp\b', MESSAGES['info_leak']),
    (r'\bgetCmdLineOpts\b', MESSAGES['info_leak']),
    (r'\bgetLog\b', MESSAGES['info_leak']),

    # Replication
    (r'\breplSetGetStatus\b', MESSAGES['replication']),
    (r'\breplSetInitiate\b', MESSAGES['replication']),
    (r'\bisMaster\b', MESSAGES['replication']),

    # Arbitrary JS in string
    (r'\bprocess\s*\.', MESSAGES['system_cmd']),
    (r'\brequire\s*\(', MESSAGES['system_cmd']),
    (r'\bchild_process\b', MESSAGES['system_cmd']),
    (r'\bspawn\s*\(', MESSAGES['system_cmd']),
    (r'\bexec\s*\(', MESSAGES['system_cmd']),
]

_COMPILED_MONGO_RULES = [(re.compile(pat, re.IGNORECASE), msg) for pat, msg in _MONGO_BLOCKED_PATTERNS]


def validate_mongodb(query: str) -> None:
    """Validate MongoDB query.

    Raises QueryBlockedError if the query contains dangerous patterns.
    """
    for pattern, message in _COMPILED_MONGO_RULES:
        if pattern.search(query):
            raise QueryBlockedError(message)


# ═══════════════════════════════════════════════════════════════
#  Redis validator
# ═══════════════════════════════════════════════════════════════

# Whitelist approach: only allow safe, learning-relevant commands
_REDIS_ALLOWED_COMMANDS = {
    # Strings
    'SET', 'GET', 'MSET', 'MGET', 'APPEND', 'STRLEN',
    'INCR', 'INCRBY', 'INCRBYFLOAT', 'DECR', 'DECRBY',
    'SETNX', 'SETEX', 'PSETEX', 'GETSET', 'GETRANGE', 'SETRANGE',
    'GETDEL',

    # Keys
    'DEL', 'EXISTS', 'EXPIRE', 'EXPIREAT', 'TTL', 'PTTL',
    'PERSIST', 'TYPE', 'RENAME', 'RENAMENX', 'RANDOMKEY',
    'SCAN', 'OBJECT',
    'KEYS',  # allowed — sandbox is isolated and small

    # Hashes
    'HSET', 'HGET', 'HMSET', 'HMGET', 'HGETALL', 'HDEL',
    'HEXISTS', 'HKEYS', 'HVALS', 'HLEN', 'HINCRBY', 'HINCRBYFLOAT',
    'HSETNX', 'HSCAN',

    # Lists
    'LPUSH', 'RPUSH', 'LPOP', 'RPOP', 'LRANGE', 'LLEN',
    'LINDEX', 'LSET', 'LINSERT', 'LREM', 'LTRIM',
    'RPOPLPUSH', 'LMOVE', 'LPOS',

    # Sets
    'SADD', 'SREM', 'SMEMBERS', 'SISMEMBER', 'SCARD',
    'SUNION', 'SINTER', 'SDIFF',
    'SUNIONSTORE', 'SINTERSTORE', 'SDIFFSTORE',
    'SRANDMEMBER', 'SPOP', 'SMOVE', 'SSCAN',

    # Sorted sets
    'ZADD', 'ZREM', 'ZSCORE', 'ZRANK', 'ZREVRANK',
    'ZRANGE', 'ZREVRANGE', 'ZRANGEBYSCORE', 'ZREVRANGEBYSCORE',
    'ZCARD', 'ZCOUNT', 'ZINCRBY',
    'ZUNIONSTORE', 'ZINTERSTORE',
    'ZRANGEBYLEX', 'ZLEXCOUNT', 'ZSCAN',
    'ZPOPMIN', 'ZPOPMAX', 'ZRANGESTORE', 'ZMSCORE',

    # HyperLogLog
    'PFADD', 'PFCOUNT', 'PFMERGE',

    # Streams
    'XADD', 'XLEN', 'XRANGE', 'XREVRANGE', 'XREAD',
    'XINFO', 'XTRIM',

    # Pub/Sub (read-only-ish, useful for learning)
    'PUBLISH', 'SUBSCRIBE', 'UNSUBSCRIBE',

    # Geo
    'GEOADD', 'GEODIST', 'GEOHASH', 'GEOPOS',
    'GEORADIUS', 'GEORADIUSBYMEMBER', 'GEOSEARCH', 'GEOSEARCHSTORE',

    # Utility (safe)
    'PING', 'ECHO', 'DBSIZE', 'TIME',
    'MULTI', 'EXEC', 'DISCARD', 'WATCH', 'UNWATCH',
    'SORT',

    # Info (read-only, useful for learning)
    'INFO',
}


def validate_redis(query: str) -> None:
    """Validate Redis command using whitelist approach.

    Raises QueryBlockedError if the command is not in the allowed list.
    """
    parts = query.strip().split()
    if not parts:
        return

    command = parts[0].upper()

    if command not in _REDIS_ALLOWED_COMMANDS:
        # Provide specific messages for commonly attempted dangerous commands
        dangerous_map = {
            'CONFIG': MESSAGES['server_config'],
            'FLUSHALL': MESSAGES['destructive'],
            'FLUSHDB': MESSAGES['destructive'],
            'SHUTDOWN': MESSAGES['destructive'],
            'SLAVEOF': MESSAGES['replication'],
            'REPLICAOF': MESSAGES['replication'],
            'DEBUG': MESSAGES['system_cmd'],
            'MODULE': MESSAGES['extension'],
            'ACL': MESSAGES['auth'],
            'AUTH': MESSAGES['auth'],
            'BGSAVE': MESSAGES['server_config'],
            'BGREWRITEAOF': MESSAGES['server_config'],
            'SAVE': MESSAGES['server_config'],
            'MIGRATE': MESSAGES['network'],
            'CLUSTER': MESSAGES['server_config'],
            'CLIENT': MESSAGES['info_leak'],
            'COMMAND': MESSAGES['info_leak'],
            'LATENCY': MESSAGES['info_leak'],
            'MEMORY': MESSAGES['info_leak'],
            'SLOWLOG': MESSAGES['info_leak'],
            'SWAPDB': MESSAGES['destructive'],
            'SELECT': MESSAGES['server_config'],
            'MONITOR': MESSAGES['info_leak'],
            'WAIT': MESSAGES['server_config'],
            'RESTORE': MESSAGES['server_config'],
            'DUMP': MESSAGES['info_leak'],
            'SCRIPT': MESSAGES['system_cmd'],
            'EVAL': MESSAGES['system_cmd'],
            'EVALSHA': MESSAGES['system_cmd'],
            'FUNCTION': MESSAGES['system_cmd'],
            'FCALL': MESSAGES['system_cmd'],
        }
        msg = dangerous_map.get(command, f"The command '{command}' is not available in the sandbox. Stick to data commands like GET, SET, HSET, LPUSH, ZADD, etc.")
        raise QueryBlockedError(msg)
