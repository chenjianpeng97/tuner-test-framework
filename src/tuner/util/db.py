from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from tuner.util.log import get_logger

log = get_logger("MySQLHelper")


class MySQLHelper:
    """
    A simple wrapper for MySQL database operations using pymysql.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize with database configuration.

        :param config: Dictionary containing 'host', 'port',
        'user', 'password', 'database', etc.
        """
        self.host = config.get("host", "localhost")
        self.port = int(config.get("port", 3306))
        self.user = config.get("user", "root")
        self.password = config.get("password", "")
        self.database = config.get("database", "")
        self.charset = config.get("charset", "utf8mb4")
        self.autocommit = config.get("autocommit", True)
        self.conn = None

    def connect(self):
        """Establish a connection to the database."""
        try:
            self.conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset=self.charset,
                cursorclass=DictCursor,
                autocommit=self.autocommit,
            )
        except pymysql.MySQLError as e:
            log.error("Failed to connect to database: {error}", error=str(e))
            raise

    def close(self):
        """Close the connection."""
        if self.conn and self.conn.open:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def fetch_all(
        self, sql: str, params: tuple | list | dict = None
    ) -> list[dict[str, Any]]:
        """
        Execute a SELECT query and return all results.
        """
        if not self.conn or not self.conn.open:
            self.connect()

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        except pymysql.MySQLError as e:
            log.error(
                "Error executing fetch_all: {error} | SQL: {sql} | Params: {params}",
                error=str(e),
                sql=sql,
                params=params,
            )
            raise

    def fetch_one(
        self, sql: str, params: tuple | list | dict = None
    ) -> dict[str, Any] | None:
        """
        Execute a SELECT query and return the first result.
        """
        if not self.conn or not self.conn.open:
            self.connect()

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()
        except pymysql.MySQLError as e:
            log.error(
                "Error executing fetch_one: {error} | SQL: {sql} | Params: {params}",
                error=str(e),
                sql=sql,
                params=params,
            )
            raise

    def execute(self, sql: str, params: tuple | list | dict = None) -> int:
        """
        Execute an INSERT, UPDATE, or DELETE query.
        Returns the number of affected rows.
        """
        if not self.conn or not self.conn.open:
            self.connect()

        try:
            with self.conn.cursor() as cursor:
                result = cursor.execute(sql, params)
                if not self.autocommit:
                    self.conn.commit()
                return result
        except pymysql.MySQLError as e:
            if not self.autocommit:
                self.conn.rollback()
            log.error(
                "Error executing execute: {error} | SQL: {sql} | Params: {params}",
                error=str(e),
                sql=sql,
                params=params,
            )
            raise
