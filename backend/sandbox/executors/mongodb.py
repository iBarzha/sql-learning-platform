"""MongoDB query executor."""

import json
from pymongo import MongoClient
from pymongo.errors import (
    ConnectionFailure,
    OperationFailure,
    ExecutionTimeout,
    PyMongoError,
)
from bson import json_util

from .base import BaseExecutor, QueryResult
from ..exceptions import (
    DatabaseConnectionError,
    QueryTimeoutError,
    QuerySyntaxError,
)


class MongoDBExecutor(BaseExecutor):
    """Executor for MongoDB databases."""

    def __init__(self, host: str, port: int, database: str = 'sandbox',
                 user: str = '', password: str = ''):
        # MongoDB sandbox typically runs without auth
        super().__init__(host, port, database, user, password)
        self._client = None
        self._db = None

    def connect(self) -> None:
        """Establish connection to MongoDB."""
        try:
            self._client = MongoClient(
                host=self.host,
                port=self.port,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
            )
            # Force connection check
            self._client.admin.command('ping')
            self._db = self._client[self.database]
        except ConnectionFailure as e:
            raise DatabaseConnectionError(f'Failed to connect to MongoDB: {e}')

    def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
            self._db = None

    def is_connected(self) -> bool:
        """Check if MongoDB connection is active."""
        if not self._client:
            return False
        try:
            self._client.admin.command('ping')
            return True
        except Exception:
            return False

    def execute_query(self, query: str, timeout: int = 10) -> QueryResult:
        """Execute a MongoDB query/command.

        Query format examples:
        - db.users.find({})
        - db.users.insertOne({name: "John"})
        - db.users.aggregate([{$match: {age: {$gt: 18}}}])
        """
        if not self._db:
            raise DatabaseConnectionError('Not connected to database')

        try:
            # Parse the query to extract collection and operation
            parsed = self._parse_query(query)
            collection = self._db[parsed['collection']]

            result, elapsed_ms = self._measure_time(
                self._execute_operation,
                collection,
                parsed['operation'],
                parsed['args'],
                timeout
            )

            return QueryResult(
                success=True,
                columns=['result'],
                rows=[[json.dumps(doc, default=json_util.default)] for doc in result]
                    if isinstance(result, list) else [[json.dumps(result, default=json_util.default)]],
                row_count=len(result) if isinstance(result, list) else 1,
                execution_time_ms=elapsed_ms,
            )

        except ExecutionTimeout:
            raise QueryTimeoutError(f'Query exceeded {timeout}s timeout')
        except OperationFailure as e:
            return QueryResult(
                success=False,
                error_message=str(e),
            )
        except ValueError as e:
            raise QuerySyntaxError(str(e))
        except PyMongoError as e:
            return QueryResult(
                success=False,
                error_message=str(e),
            )

    def _parse_query(self, query: str) -> dict:
        """Parse MongoDB query string into components."""
        query = query.strip()

        # Remove 'db.' prefix if present
        if query.startswith('db.'):
            query = query[3:]

        # Find collection name (before first dot)
        parts = query.split('.', 1)
        if len(parts) < 2:
            raise ValueError('Invalid query format. Expected: db.collection.operation(...)')

        collection = parts[0]
        rest = parts[1]

        # Extract operation and arguments
        paren_idx = rest.find('(')
        if paren_idx == -1:
            raise ValueError('Invalid query format. Missing parentheses.')

        operation = rest[:paren_idx]
        args_str = rest[paren_idx + 1:-1]  # Remove parentheses

        # Parse arguments as JSON (with some MongoDB-style relaxation)
        args = self._parse_args(args_str) if args_str.strip() else []

        return {
            'collection': collection,
            'operation': operation,
            'args': args,
        }

    def _parse_args(self, args_str: str) -> list:
        """Parse MongoDB-style arguments to Python objects."""
        if not args_str.strip():
            return []

        # Handle common MongoDB shell formats
        args_str = args_str.strip()

        # Try to parse as JSON array first
        try:
            if not args_str.startswith('['):
                args_str = f'[{args_str}]'
            return json.loads(args_str)
        except json.JSONDecodeError:
            # Try with relaxed JSON (single quotes, unquoted keys)
            import re
            # Replace single quotes with double quotes
            relaxed = re.sub(r"'([^']*)'", r'"\1"', args_str)
            # Quote unquoted keys
            relaxed = re.sub(r'(\w+):', r'"\1":', relaxed)
            try:
                if not relaxed.startswith('['):
                    relaxed = f'[{relaxed}]'
                return json.loads(relaxed)
            except json.JSONDecodeError:
                raise ValueError(f'Failed to parse arguments: {args_str}')

    def _execute_operation(self, collection, operation: str, args: list,
                           timeout: int) -> list | dict:
        """Execute a MongoDB collection operation."""
        timeout_ms = timeout * 1000

        op_map = {
            'find': lambda: list(collection.find(*args).max_time_ms(timeout_ms)),
            'findOne': lambda: collection.find_one(*args, max_time_ms=timeout_ms),
            'insertOne': lambda: {'insertedId': str(collection.insert_one(*args).inserted_id)},
            'insertMany': lambda: {'insertedIds': [str(id) for id in collection.insert_many(*args).inserted_ids]},
            'updateOne': lambda: {'matchedCount': collection.update_one(*args).matched_count,
                                  'modifiedCount': collection.update_one(*args).modified_count},
            'updateMany': lambda: {'matchedCount': collection.update_many(*args).matched_count,
                                   'modifiedCount': collection.update_many(*args).modified_count},
            'deleteOne': lambda: {'deletedCount': collection.delete_one(*args).deleted_count},
            'deleteMany': lambda: {'deletedCount': collection.delete_many(*args).deleted_count},
            'aggregate': lambda: list(collection.aggregate(*args, maxTimeMS=timeout_ms)),
            'countDocuments': lambda: {'count': collection.count_documents(*args, maxTimeMS=timeout_ms)},
            'distinct': lambda: collection.distinct(*args, maxTimeMS=timeout_ms),
        }

        if operation not in op_map:
            raise ValueError(f'Unsupported operation: {operation}')

        result = op_map[operation]()
        return result if result is not None else {}

    def initialize_schema(self, schema_sql: str) -> QueryResult:
        """Initialize MongoDB schema (create collections, indexes)."""
        if not schema_sql.strip():
            return QueryResult(success=True)

        try:
            # Execute schema commands line by line
            for line in schema_sql.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('//'):
                    self.execute_query(line, timeout=30)
            return QueryResult(success=True)
        except Exception as e:
            return QueryResult(
                success=False,
                error_message=f'Schema initialization failed: {e}',
            )

    def load_data(self, seed_sql: str) -> QueryResult:
        """Load seed data into MongoDB."""
        if not seed_sql.strip():
            return QueryResult(success=True)

        try:
            for line in seed_sql.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('//'):
                    self.execute_query(line, timeout=30)
            return QueryResult(success=True)
        except Exception as e:
            return QueryResult(
                success=False,
                error_message=f'Data loading failed: {e}',
            )

    def reset(self) -> None:
        """Reset MongoDB by dropping all collections."""
        if not self._db:
            return

        try:
            for collection_name in self._db.list_collection_names():
                self._db.drop_collection(collection_name)
        except PyMongoError:
            pass  # Ignore reset errors
